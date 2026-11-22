"""Tools for the Obsidian brain in docs/ and the Agent Skills in .claude/skills/.

    python scripts/brain.py check                      validate notes and skills (CI runs this)
    python scripts/brain.py search "quota reserve"     find notes (used by brain-query)
    python scripts/brain.py new adr "Some decision"    create a note (used by brain-ingest)

Standard library only, so CI needs nothing extra. Run from the repo root.
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIN_NOTES = 10  # Stage 1 deliverable: a vault with 10+ notes
PARA_FOLDERS = ("Projects", "Areas", "Resources", "Archive")
MIN_EVAL_CASES = 3  # TQ-7: each skill is evaluated against a few cases

# kind -> (folder under docs/, section heading in Index.md)
KINDS = {
    "adr": ("adr", "## Decisions (ADRs)"),
    "project": ("Projects", "## Projects"),
    "area": ("Areas", "## Areas"),
    "resource": ("Resources", "## Resources"),
}

PLACEHOLDER = "TODO"  # skeleton text; `check` rejects notes that still contain it
RUNTIME_PATHS = {".cache/ytmcp.db"}  # files notes mention that only exist while running
PATH_EXTENSIONS = ("py", "md", "json", "yml", "yaml", "toml", "txt")

STOPWORDS = frozenset(
    ["a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "we", "what", "why", "how", "when", "where", "which", "to", "of", "in", "on", "for", "and", "or", "it", "our", "i", "you", "my", "me", "with", "by", "at", "be", "this", "that", "there", "only"]
)

FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[\[([^\]\n]+)\]\]")
LOG_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) - (.+?) - (.+)$")
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ADR_NAME = re.compile(r"^ADR-(\d{3}) (.+)$")
PATH_LIKE = re.compile(r"^[\w.\-/]+/[\w.\-/]*\.(?:" + "|".join(PATH_EXTENSIONS) + r")$")
TITLE_OK = re.compile(r"^\w[\w .,()'&+-]{0,80}$")


class BrainError(ValueError):
    """A problem the user can fix (bad title, missing section, file already exists)."""


@dataclass(frozen=True)
class Vault:
    root: Path = ROOT

    @property
    def docs(self) -> Path:
        return self.root / "docs"

    @property
    def skills(self) -> Path:
        return self.root / ".claude" / "skills"

    def note_paths(self) -> list[Path]:
        return sorted(self.docs.rglob("*.md")) if self.docs.is_dir() else []

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()


# --- reading notes -------------------------------------------------------------


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def strip_code(text: str) -> str:
    """Remove code blocks and `inline code`, so syntax examples are not treated as links."""
    return INLINE.sub("", FENCE.sub("", text))


def link_target(raw: str) -> str:
    """[[Note|alias]] and [[Note#Heading]] both point at Note."""
    return raw.split("|")[0].split("#")[0].strip()


def links_in(text: str) -> list[str]:
    return [link_target(m) for m in LINK.findall(strip_code(text))]


def parse_frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    """Return (key: value pairs, body). Only simple one-line `key: value` pairs are read."""
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not match:
        return None, text
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t", "#")):
            data[key.strip()] = value.strip().strip("\"'")
    return data, match.group(2)


# --- check ------------------------------------------------------------------------


def check_vault(vault: Vault) -> list[str]:
    """Return a list of problems with the notes and skills. Empty means all good."""
    errors: list[str] = []
    paths = vault.note_paths()
    if not paths:
        return ["docs/: no notes found. Run this from the repo root."]

    names: dict[str, Path] = {}
    for path in paths:
        if path.stem in names:
            errors.append(f"{vault.rel(path)}: same note name as {vault.rel(names[path.stem])}")
        names.setdefault(path.stem, path)

    if len(paths) < MIN_NOTES:
        errors.append(f"docs/: {len(paths)} notes, the SRS asks for at least {MIN_NOTES}")
    for folder in (*PARA_FOLDERS, "adr"):
        if not (vault.docs / folder).is_dir():
            errors.append(f"docs/{folder}/: folder is missing (PARA: {', '.join(PARA_FOLDERS)})")
    for required in ("Index", "Log"):
        if required not in names:
            errors.append(f"docs/{required}.md: note is missing")

    index_links = set(links_in(read(names["Index"]))) if "Index" in names else set()
    for path in paths:
        text = read(path)
        rel = vault.rel(path)
        errors += [f"{rel}: broken link [[{t}]]" for t in links_in(text) if t not in names]
        if path.stem != "Index" and path.stem not in index_links:
            errors.append(f"{rel}: not linked from the Index")
        if PLACEHOLDER in strip_code(text):
            errors.append(f"{rel}: unfinished, still contains {PLACEHOLDER}")
        errors += check_paths(vault, rel, text)

    errors += check_adrs(vault, names)
    if "Log" in names:
        errors += check_log(vault, names["Log"])
    errors += check_skills(vault, names)
    return errors


def check_paths(vault: Vault, rel: str, text: str) -> list[str]:
    """File paths written in `backticks` must exist, so notes do not describe deleted code."""
    errors = []
    homes = (vault.root, vault.root / "src" / "ytmcp", vault.root / "tests", vault.docs)
    for token in dict.fromkeys(INLINE.findall(FENCE.sub("", text))):
        if token in RUNTIME_PATHS or not PATH_LIKE.match(token):
            continue
        if not any((home / token).exists() for home in homes):
            errors.append(f"{rel}: path `{token}` does not exist")
    return errors


def check_adrs(vault: Vault, names: dict[str, Path]) -> list[str]:
    errors = []
    numbers: dict[int, str] = {}
    for path in sorted((vault.docs / "adr").glob("*.md")):
        rel = vault.rel(path)
        match = ADR_NAME.match(path.stem)
        if not match:
            errors.append(f"{rel}: ADR files are named 'ADR-001 Title.md'")
            continue
        number = int(match.group(1))
        if number in numbers:
            errors.append(f"{rel}: ADR number {number:03d} is also used by {numbers[number]}")
        numbers[number] = rel

        text = read(path)
        if not text.startswith(f"# {path.stem}\n"):
            errors.append(f"{rel}: the first line should be '# {path.stem}'")
        if not re.search(r"^Status: \S", text, re.MULTILINE):
            errors.append(f"{rel}: missing a 'Status:' line")
        for heading in ("Context", "Decision", "Consequences"):
            if not re.search(rf"^## {heading}\s*$", text, re.MULTILINE):
                errors.append(f"{rel}: missing the '## {heading}' section")
        cites = re.search(r"^Cites:(.*)$", text, re.MULTILINE)
        if not cites or not links_in(cites.group(1)):
            errors.append(f"{rel}: needs a 'Cites: [[Note]]' line linking at least one note (SE-3)")
    missing = sorted(set(range(1, max(numbers, default=0) + 1)) - set(numbers))
    if missing:
        errors.append(f"docs/adr/: ADR numbers missing: {', '.join(f'{n:03d}' for n in missing)}")
    return errors


def check_log(vault: Vault, path: Path) -> list[str]:
    rel = vault.rel(path)
    entries = 0
    errors = []
    for number, line in enumerate(read(path).splitlines(), start=1):
        if not line.startswith("- "):
            continue
        entries += 1
        match = LOG_LINE.match(line)
        try:
            if not match:
                raise ValueError
            date.fromisoformat(match.group(1))
        except ValueError:
            errors.append(f"{rel}:{number}: log lines look like '- YYYY-MM-DD - who - what'")
    if not entries:
        errors.append(f"{rel}: no log entries")
    return errors


def check_skills(vault: Vault, names: dict[str, Path]) -> list[str]:
    errors = []
    if not vault.skills.is_dir():
        return errors
    for folder in sorted(p for p in vault.skills.iterdir() if p.is_dir()):
        rel = vault.rel(folder / "SKILL.md")
        skill_file = folder / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"{vault.rel(folder)}: no SKILL.md")
            continue
        meta, body = parse_frontmatter(read(skill_file))
        if meta is None:
            errors.append(f"{rel}: must start with a --- frontmatter block (name, description)")
            continue
        name = meta.get("name", "")
        if not name:
            errors.append(f"{rel}: frontmatter needs a name")
        elif name != folder.name:
            errors.append(f"{rel}: name '{name}' must match the folder name '{folder.name}'")
        if name and (not SKILL_NAME.match(name) or len(name) > 64):
            errors.append(f"{rel}: name must be lowercase letters, digits and hyphens, up to 64")
        description = meta.get("description", "")
        if not description or description in (">", "|", ">-", "|-"):
            errors.append(f"{rel}: frontmatter needs a one-line description")
        elif len(description) > 1024:
            errors.append(f"{rel}: description is {len(description)} characters, the limit is 1024")
        if not body.strip():
            errors.append(f"{rel}: the skill has no instructions")
        cited = [
            t
            for line in body.splitlines()
            if line.startswith("Brain note:")
            for t in links_in(line)
        ]
        if not cited:
            errors.append(f"{rel}: needs a 'Brain note: [[Note]]' line (SK-4)")
        errors += [f"{rel}: Brain note [[{t}]] does not exist" for t in cited if t not in names]
        errors += check_evals(vault, folder)
    return errors


def check_evals(vault: Vault, folder: Path) -> list[str]:
    evals = folder / "evals.md"
    rel = vault.rel(evals)
    if not evals.is_file():
        return [f"{vault.rel(folder)}: needs an evals.md with test cases (TQ-7)"]
    text = read(evals)
    prompts = len(re.findall(r"^Prompt:", text, re.MULTILINE))
    expects = len(re.findall(r"^Expect:", text, re.MULTILINE))
    if prompts < MIN_EVAL_CASES or prompts != expects:
        found = f"found {prompts} Prompt and {expects} Expect lines"
        return [f"{rel}: needs at least {MIN_EVAL_CASES} cases, each with Prompt: and Expect: ({found})"]
    return []


# --- search -------------------------------------------------------------------------


@dataclass(frozen=True)
class Hit:
    name: str
    path: str
    score: int
    lines: list[tuple[int, str]]


def search_terms(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9_]+", query.lower())
    return list(dict.fromkeys(w for w in words if w not in STOPWORDS))


def search_vault(vault: Vault, query: str, limit: int = 5) -> list[Hit]:
    """Rank notes by how well they match the words in `query`. Plain text matching, no AI."""
    terms = search_terms(query)
    hits = []
    for path in vault.note_paths():
        lines = read(path).splitlines()
        score = 0
        matched: set[str] = set()
        for term in terms:
            score += 3 * path.stem.lower().count(term)
            if term in path.stem.lower():
                matched.add(term)
            for line in lines:
                count = line.lower().count(term)
                if count:
                    matched.add(term)
                    score += count * (2 if line.startswith("#") else 1)
        if not matched:
            continue
        score += 5 * len(matched)  # covering more of the words matters most
        scored_lines = sorted(
            (
                (sum(t in line.lower() for t in terms), number, line.strip())
                for number, line in enumerate(lines, start=1)
                if any(t in line.lower() for t in terms)
            ),
            key=lambda item: (-item[0], item[1]),
        )
        snippets = [(number, text[:140]) for _, number, text in scored_lines[:3]]
        hits.append(Hit(path.stem, vault.rel(path), score, snippets))
    hits.sort(key=lambda h: (-h.score, h.name))
    return hits[:limit]


def unmatched_terms(vault: Vault, query: str) -> list[str]:
    """Words from the query that appear in no note at all. A strong sign the notes do not cover it."""
    texts = [(p.stem + "\n" + read(p)).lower() for p in vault.note_paths()]
    return [t for t in search_terms(query) if not any(t in text for text in texts)]


# --- new note ---------------------------------------------------------------------------


def git_user() -> str:
    result = subprocess.run(
        ["git", "config", "user.name"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "team"


def skeleton(kind: str, name: str, title: str) -> str:
    if kind == "adr":
        return (
            f"# {name}\n\nStatus: Proposed\n\n## Context\n{PLACEHOLDER}: why was a decision needed?\n\n"
            f"## Decision\n{PLACEHOLDER}: what was decided?\n\n"
            f"## Consequences\n{PLACEHOLDER}: what changes because of it?\n\n"
            f"Cites: [[{PLACEHOLDER} replace with a real note]]\n"
        )
    return f"# {title}\n\n{PLACEHOLDER}: write what this note covers.\n\nPart of [[Index]].\n"


def add_to_index(index: Path, heading: str, name: str) -> None:
    lines = read(index).splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        raise BrainError(f"Index.md has no '{heading}' section") from None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    entries = [i for i in range(start + 1, end) if lines[i].startswith("- [[")]
    lines.insert((entries[-1] if entries else start) + 1, f"- [[{name}]]")
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")


def new_note(
    vault: Vault, kind: str, title: str, who: str | None = None, today: date | None = None
) -> Path:
    """Create a note skeleton, list it in the Index and add a Log line."""
    if kind not in KINDS:
        raise BrainError(f"kind must be one of: {', '.join(KINDS)}")
    title = title.strip()
    if not TITLE_OK.match(title):
        raise BrainError("title may only use letters, numbers, spaces and . , ( ) ' & + -")
    folder, heading = KINDS[kind]
    index, log = vault.docs / "Index.md", vault.docs / "Log.md"
    if not index.is_file() or not log.is_file():
        raise BrainError("docs/Index.md and docs/Log.md must exist")

    name = title
    if kind == "adr":
        used = [
            int(m.group(1))
            for p in (vault.docs / "adr").glob("*.md")
            if (m := ADR_NAME.match(p.stem))
        ]
        name = f"ADR-{max(used, default=0) + 1:03d} {title}"
    if any(p.stem == name for p in vault.note_paths()):
        raise BrainError(f"a note named '{name}' already exists")

    path = vault.docs / folder / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    add_to_index(index, heading, name)  # may fail, so do it before writing anything else
    path.write_text(skeleton(kind, name, title), encoding="utf-8")
    entry = f"- {(today or date.today()).isoformat()} - {who or git_user()} - Added {kind} note [[{name}]].\n"
    text = read(log)
    log.write_text(text + ("" if text.endswith("\n") else "\n") + entry, encoding="utf-8")
    return path


# --- command line ---------------------------------------------------------------------------


def main(
    argv: Sequence[str] | None = None,
    vault: Vault | None = None,
    out: Callable[[str], object] = print,
) -> int:
    vault = vault or Vault()
    parser = argparse.ArgumentParser(prog="brain.py", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="validate the notes and skills")
    search = commands.add_parser("search", help="find notes matching some words")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    new = commands.add_parser("new", help="create a note and add it to the Index and Log")
    new.add_argument("kind", choices=sorted(KINDS))
    new.add_argument("title")
    args = parser.parse_args(argv)

    if args.command == "check":
        errors = check_vault(vault)
        for error in errors:
            out(f"PROBLEM  {error}")
        if errors:
            out(f"\nbrain check: {len(errors)} problem(s)")
            return 1
        skills = len([p for p in vault.skills.glob("*/SKILL.md")]) if vault.skills.is_dir() else 0
        out(f"brain check passed: {len(vault.note_paths())} notes, {skills} skills")
        return 0

    if args.command == "search":
        hits = search_vault(vault, args.query, args.limit)
        if not hits:
            out("No notes match. Try other words, or the notes may not cover this.")
            return 1
        for hit in hits:
            out(f"[[{hit.name}]]  ({hit.path}, score {hit.score})")
            for number, line in hit.lines:
                out(f"    {number}: {line}")
        missing = unmatched_terms(vault, args.query)
        if missing:
            out(f"\nNot found in any note: {', '.join(missing)}. The notes may not cover this.")
        return 0

    try:
        path = new_note(vault, args.kind, args.title)
    except BrainError as exc:
        out(f"Error: {exc}")
        return 1
    out(f"Created {vault.rel(path)}, listed it in the Index and added a Log line.")
    out(f"Fill in the {PLACEHOLDER} parts, then run: python scripts/brain.py check")
    return 0


if __name__ == "__main__":
    sys.exit(main())

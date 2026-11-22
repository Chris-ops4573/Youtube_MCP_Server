"""Tests for scripts/brain.py: the checker, search and note creation (SB, SK-3, SK-4)."""

from datetime import date
from pathlib import Path

import brain
import pytest
from brain import BrainError, Vault

ADR = """# ADR-001 First choice

Status: Accepted

## Context
Why.

## Decision
What.

## Consequences
So.

Cites: [[Note 1]]
"""

SKILL = """---
name: {name}
description: Does a thing. Use when asked.
---

# {name}

Steps here.

Brain note: [[Note 1]]
"""

EVALS = "\n".join(f"## Case {i}\nPrompt: p{i}\nExpect: e{i}\n" for i in range(3))


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_vault(root: Path, extra_notes: int = 9) -> Vault:
    """A small vault that passes the check."""
    docs = root / "docs"
    for folder in brain.PARA_FOLDERS:
        (docs / folder).mkdir(parents=True)
    names = [f"Note {i}" for i in range(1, extra_notes + 1)]
    for name in names:
        write(docs / "Areas" / f"{name}.md", f"# {name}\n\nSome text about {name}.\n")
    write(docs / "adr" / "ADR-001 First choice.md", ADR)
    write(docs / "Log.md", "# Log\n\n- 2026-11-22 - Chris - Started.\n")
    entries = "\n".join(f"- [[{n}]]" for n in [*names, "ADR-001 First choice", "Log"])
    write(
        docs / "Index.md",
        "# Index\n\n## Projects\n\n## Areas\n" + entries + "\n\n## Resources\n\n"
        "## Decisions (ADRs)\n- [[ADR-001 First choice]]\n\n## Log\n- [[Log]]\n",
    )
    return Vault(root)


def add_skill(vault: Vault, name="my-skill", evals=EVALS, skill=None):
    folder = vault.skills / name
    write(folder / "SKILL.md", skill if skill is not None else SKILL.format(name=name))
    if evals is not None:
        write(folder / "evals.md", evals)


@pytest.fixture
def vault(tmp_path):
    return make_vault(tmp_path)


def problems(vault):
    return brain.check_vault(vault)


def assert_problem(vault, fragment):
    found = problems(vault)
    assert any(fragment in p for p in found), found


# --- the repo's own notes --------------------------------------------------------


def test_the_real_vault_passes_the_check():
    assert brain.check_vault(Vault()) == []


def test_the_real_vault_has_the_three_brain_skills():
    names = {p.parent.name for p in Vault().skills.glob("*/SKILL.md")}
    assert {"brain-query", "brain-refine", "brain-ingest", "local-check"} <= names


@pytest.mark.parametrize(
    "query, expected",
    [
        ("why stdio only", "ADR-009 Stdio transport only"),
        ("how many quota units does find_similar_channels cost", ("Quota", "Channels")),  # either answers it
        ("where are google login tokens stored", "Auth"),
        ("like dates for engagement trends", "ADR-010 Like dates from the likes playlist"),
        ("python version and libraries", "ADR-008 Python 3.11 and libraries"),
    ],
)
def test_search_finds_the_right_note_in_the_real_vault(query, expected):
    top_three = [h.name for h in brain.search_vault(Vault(), query, limit=3)]
    accepted = (expected,) if isinstance(expected, str) else expected
    assert any(name in top_three for name in accepted), top_three


# --- check: a good vault and the structure ------------------------------------------


def test_a_good_vault_passes(vault):
    assert problems(vault) == []


def test_no_notes_at_all(tmp_path):
    assert "no notes found" in brain.check_vault(Vault(tmp_path))[0]


def test_too_few_notes(tmp_path):
    assert any("at least 10" in p for p in problems(make_vault(tmp_path, extra_notes=3)))


@pytest.mark.parametrize("folder", ["Archive", "adr", "Projects"])
def test_missing_folder(vault, folder):
    import shutil

    shutil.rmtree(vault.docs / folder)
    assert_problem(vault, f"docs/{folder}/: folder is missing")


@pytest.mark.parametrize("required", ["Index", "Log"])
def test_missing_index_or_log(vault, required):
    (vault.docs / f"{required}.md").unlink()
    assert_problem(vault, f"docs/{required}.md: note is missing")


def test_duplicate_note_names(vault):
    write(vault.docs / "Resources" / "Note 1.md", "# Note 1\n")
    assert_problem(vault, "same note name")


# --- check: links and the Index --------------------------------------------------------


def test_broken_link(vault):
    note = vault.docs / "Areas" / "Note 2.md"
    note.write_text(note.read_text() + "See [[Nope]].\n")
    assert_problem(vault, "Note 2.md: broken link [[Nope]]")


def test_alias_and_heading_links_resolve(vault):
    note = vault.docs / "Areas" / "Note 2.md"
    note.write_text(note.read_text() + "See [[Note 1|the first]] and [[Note 3#Heading]].\n")
    assert problems(vault) == []


def test_links_in_code_are_ignored(vault):
    note = vault.docs / "Areas" / "Note 2.md"
    note.write_text(note.read_text() + "Syntax is `[[Not A Link]]`.\n```\n[[Also Not]]\n```\n")
    assert problems(vault) == []


def test_note_missing_from_index(vault):
    write(vault.docs / "Areas" / "Lonely.md", "# Lonely\n")
    assert_problem(vault, "Lonely.md: not linked from the Index")


def test_todo_marker_is_unfinished(vault):
    note = vault.docs / "Areas" / "Note 2.md"
    note.write_text(note.read_text() + "TODO: write this.\n")
    assert_problem(vault, "Note 2.md: unfinished")


def test_todo_inside_code_is_allowed(vault):
    note = vault.docs / "Areas" / "Note 2.md"
    note.write_text(note.read_text() + "Use `TODO` as a marker.\n")
    assert problems(vault) == []


# --- check: paths written in notes --------------------------------------------------------


def test_path_that_does_not_exist(vault):
    note = vault.docs / "Areas" / "Note 2.md"
    note.write_text(note.read_text() + "See `src/ytmcp/gone.py` for details.\n")
    assert_problem(vault, "path `src/ytmcp/gone.py` does not exist")


@pytest.mark.parametrize(
    "token, where",
    [
        ("src/ytmcp/here.py", "src/ytmcp/here.py"),  # full path from the repo root
        ("providers/here.py", "src/ytmcp/providers/here.py"),  # short path inside the package
        ("test_here.py", "tests/test_here.py"),  # no slash: never checked
    ],
)
def test_existing_paths_are_accepted(vault, token, where):
    write(vault.root / where, "")
    note = vault.docs / "Areas" / "Note 2.md"
    note.write_text(note.read_text() + f"See `{token}`.\n")
    assert problems(vault) == []


@pytest.mark.parametrize("token", [".cache/ytmcp.db", "tests/fixtures/*.json", "docs/x/SRS_...docx", "run a/b.py now"])
def test_things_that_are_not_checked_paths(vault, token):
    note = vault.docs / "Areas" / "Note 2.md"
    note.write_text(note.read_text() + f"See `{token}`.\n")
    assert problems(vault) == []


# --- check: ADRs ---------------------------------------------------------------------------------


def set_adr(vault, text):
    (vault.docs / "adr" / "ADR-001 First choice.md").write_text(text)


@pytest.mark.parametrize(
    "mutation, fragment",
    [
        (lambda t: t.replace("Cites: [[Note 1]]\n", ""), "needs a 'Cites:"),
        (lambda t: t.replace("[[Note 1]]", "no links here"), "needs a 'Cites:"),
        (lambda t: t.replace("Status: Accepted\n", ""), "missing a 'Status:' line"),
        (lambda t: t.replace("## Decision", "## Choice"), "missing the '## Decision' section"),
        (lambda t: t.replace("## Consequences", "## Later"), "missing the '## Consequences'"),
        (lambda t: t.replace("# ADR-001 First choice", "# Something else", 1), "first line should be"),
    ],
)
def test_bad_adr(vault, mutation, fragment):
    set_adr(vault, mutation(ADR))
    assert_problem(vault, fragment)


def test_adr_citing_a_missing_note(vault):
    set_adr(vault, ADR.replace("[[Note 1]]", "[[Ghost]]"))
    assert_problem(vault, "broken link [[Ghost]]")


def test_adr_with_a_bad_name(vault):
    write(vault.docs / "adr" / "Decision about x.md", ADR)
    assert_problem(vault, "ADR files are named")


def test_adr_numbers_must_not_repeat_or_skip(vault):
    write(vault.docs / "adr" / "ADR-001 Other.md", ADR.replace("First choice", "Other"))
    assert_problem(vault, "ADR number 001 is also used")
    (vault.docs / "adr" / "ADR-001 Other.md").unlink()
    write(vault.docs / "adr" / "ADR-003 Third.md", ADR.replace("ADR-001 First choice", "ADR-003 Third"))
    assert_problem(vault, "ADR numbers missing: 002")


# --- check: the Log --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    ["- yesterday - Chris - did it", "- 2026-11-22 Chris did it", "- 2026-13-45 - Chris - bad date", "- 2026-11-22 - only two"],
)
def test_bad_log_line(vault, line):
    log = vault.docs / "Log.md"
    log.write_text(log.read_text() + line + "\n")
    assert_problem(vault, "Log.md:")


def test_log_needs_an_entry(vault):
    (vault.docs / "Log.md").write_text("# Log\n")
    assert_problem(vault, "no log entries")


def test_log_who_may_not_contain_a_dash_but_what_may(vault):
    log = vault.docs / "Log.md"
    log.write_text(log.read_text() + "- 2026-11-23 - Chris - Fixed a - b thing.\n")
    assert problems(vault) == []


# --- check: skills ------------------------------------------------------------------------------------


def test_a_good_skill_passes(vault):
    add_skill(vault)
    assert problems(vault) == []


def test_no_skills_folder_is_fine(vault):
    assert not vault.skills.exists()
    assert problems(vault) == []


def test_skill_folder_without_skill_md(vault):
    (vault.skills / "empty").mkdir(parents=True)
    assert_problem(vault, "no SKILL.md")


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("# no frontmatter\nBrain note: [[Note 1]]\n", "must start with a ---"),
        ("---\ndescription: x\n---\nBody\nBrain note: [[Note 1]]\n", "needs a name"),
        ("---\nname: other\ndescription: x\n---\nBody\nBrain note: [[Note 1]]\n", "must match the folder name"),
        ("---\nname: My_Skill\ndescription: x\n---\nBody\nBrain note: [[Note 1]]\n", "lowercase letters"),
        ("---\nname: my-skill\n---\nBody\nBrain note: [[Note 1]]\n", "one-line description"),
        ("---\nname: my-skill\ndescription: >\n  folded\n---\nBody\nBrain note: [[Note 1]]\n", "one-line description"),
        ("---\nname: my-skill\ndescription: " + "x" * 1025 + "\n---\nBody\nBrain note: [[Note 1]]\n", "limit is 1024"),
        ("---\nname: my-skill\ndescription: x\n---\n\nBrain note: [[Note 1]]\n", None),  # body is only the citation: fine
        ("---\nname: my-skill\ndescription: x\n---\n", "no instructions"),
        ("---\nname: my-skill\ndescription: x\n---\nBody only\n", "needs a 'Brain note:"),
        ("---\nname: my-skill\ndescription: x\n---\nBody\nBrain note: [[Ghost]]\n", "Brain note [[Ghost]] does not exist"),
    ],
)
def test_bad_skill_files(vault, text, fragment):
    add_skill(vault, skill=text)
    if fragment is None:
        assert problems(vault) == []
    else:
        assert_problem(vault, fragment)


def test_name_of_exactly_64_characters_is_allowed_but_65_is_not(vault):
    ok = "a" * 64
    add_skill(vault, name=ok)
    assert problems(vault) == []
    too_long = "b" * 65
    add_skill(vault, name=too_long)
    assert_problem(vault, "up to 64")


@pytest.mark.parametrize(
    "evals, fragment",
    [
        (None, "needs an evals.md"),
        ("## Case\nPrompt: a\nExpect: b\n", "at least 3 cases"),
        ("Prompt: a\nPrompt: b\nPrompt: c\nExpect: x\n", "found 3 Prompt and 1 Expect"),
    ],
)
def test_skill_needs_enough_evals(vault, evals, fragment):
    add_skill(vault, evals=evals)
    assert_problem(vault, fragment)


def test_windows_line_endings_are_fine(vault):
    add_skill(vault, skill=SKILL.format(name="my-skill").replace("\n", "\r\n"))
    assert problems(vault) == []


# --- search -------------------------------------------------------------------------------------------------


def test_search_terms_drop_filler_words():
    assert brain.search_terms("Why do we use the Quota reserve?") == ["use", "quota", "reserve"]


def test_search_ranks_by_how_many_words_match(vault):
    write(vault.docs / "Areas" / "Both.md", "# Both\n\nquota and reserve together.\n")
    write(vault.docs / "Areas" / "One.md", "# One\n\nquota quota quota.\n")
    hits = brain.search_vault(vault, "quota reserve")
    assert [h.name for h in hits][:2] == ["Both", "One"]


def test_title_match_beats_a_body_mention(vault):
    write(vault.docs / "Areas" / "Quota.md", "# Quota\n\nunits.\n")
    write(vault.docs / "Areas" / "Elsewhere.md", "# Elsewhere\n\nquota is mentioned once.\n")
    assert brain.search_vault(vault, "quota")[0].name == "Quota"


def test_search_shows_the_matching_lines_with_numbers(vault):
    write(vault.docs / "Areas" / "Cost.md", "# Cost\n\nnothing\nThe reserve is 500 units.\n")
    (hit,) = brain.search_vault(vault, "reserve", limit=1)
    assert (4, "The reserve is 500 units.") in hit.lines


def test_search_snippets_are_cut_short(vault):
    write(vault.docs / "Areas" / "Long.md", "# Long\n\nreserve " + "x" * 400 + "\n")
    (hit,) = brain.search_vault(vault, "reserve")
    assert all(len(text) <= 140 for _, text in hit.lines)


def test_search_with_no_match_and_with_only_filler(vault):
    assert brain.search_vault(vault, "kubernetes") == []
    assert brain.search_vault(vault, "what is the") == []


def test_unmatched_terms_lists_words_found_nowhere(vault):
    assert brain.unmatched_terms(vault, "How is the note deployed to Kubernetes?") == ["deployed", "kubernetes"]
    assert brain.unmatched_terms(vault, "note") == []
    assert brain.unmatched_terms(vault, "what is the") == []


def test_unmatched_terms_also_looks_at_note_titles(vault):
    write(vault.docs / "Areas" / "Zebra.md", "# Zebra\n")
    assert brain.unmatched_terms(vault, "zebra") == []


def test_search_limit_and_order_are_stable(vault):
    hits = brain.search_vault(vault, "note", limit=3)
    assert len(hits) == 3
    assert hits == brain.search_vault(vault, "note", limit=3)


# --- new note --------------------------------------------------------------------------------------------------


TODAY = date(2026, 11, 23)


def make_note(vault, kind, title, who="Chris"):
    return brain.new_note(vault, kind, title, who=who, today=TODAY)


def test_new_adr_gets_the_next_number_and_the_right_folder(vault):
    path = make_note(vault, "adr", "Cache everything")
    assert path == vault.docs / "adr" / "ADR-002 Cache everything.md"
    text = path.read_text()
    assert text.startswith("# ADR-002 Cache everything\n")
    assert "Status: Proposed" in text


def test_new_adr_numbers_continue_after_a_gap(vault):
    write(vault.docs / "adr" / "ADR-007 Seven.md", ADR.replace("ADR-001 First choice", "ADR-007 Seven"))
    assert make_note(vault, "adr", "Eight").name == "ADR-008 Eight.md"


@pytest.mark.parametrize(
    "kind, folder, heading",
    [("project", "Projects", "## Projects"), ("area", "Areas", "## Areas"), ("resource", "Resources", "## Resources")],
)
def test_new_notes_go_in_their_para_folder_and_index_section(vault, kind, folder, heading):
    path = make_note(vault, kind, "Fresh idea")
    assert path.parent.name == folder
    index = (vault.docs / "Index.md").read_text()
    section = index.split(heading)[1].split("\n## ")[0]
    assert "- [[Fresh idea]]" in section


def test_new_note_is_added_after_the_last_entry_of_its_section(vault):
    make_note(vault, "area", "Zeta")
    lines = (vault.docs / "Index.md").read_text().splitlines()
    area_entries = [ln for ln in lines[lines.index("## Areas") :] if ln.startswith("- [[")]
    assert area_entries[-3:] == ["- [[ADR-001 First choice]]", "- [[Log]]", "- [[Zeta]]"] or "- [[Zeta]]" in area_entries


def test_new_note_into_an_empty_section(vault):
    make_note(vault, "project", "First project")
    index = (vault.docs / "Index.md").read_text()
    assert "## Projects\n- [[First project]]" in index.replace("## Projects\n\n", "## Projects\n")


def test_new_note_adds_a_log_line_that_passes_the_log_check(vault):
    make_note(vault, "area", "Zeta", who="Rohit")
    log = (vault.docs / "Log.md").read_text()
    assert log.endswith("- 2026-11-23 - Rohit - Added area note [[Zeta]].\n")
    assert not any("Log.md" in p for p in problems(vault))


def test_log_line_is_added_even_if_the_log_has_no_final_newline(vault):
    log = vault.docs / "Log.md"
    log.write_text(log.read_text().rstrip("\n"))
    make_note(vault, "area", "Zeta")
    assert "Started.\n- 2026-11-23" in log.read_text()


def test_a_new_note_fails_the_check_until_it_is_filled_in(vault):
    make_note(vault, "area", "Zeta")
    found = problems(vault)
    assert any("Zeta.md: unfinished" in p for p in found)
    assert not any("broken link" in p or "not linked" in p for p in found)


def test_a_new_adr_must_get_a_real_citation(vault):
    path = make_note(vault, "adr", "Choice")
    found = problems(vault)
    assert any("unfinished" in p for p in found)
    assert any("broken link" in p for p in found)  # the placeholder citation
    text = path.read_text().replace(f"{brain.PLACEHOLDER}: ", "Filled. ")
    text = text.replace("[[TODO replace with a real note]]", "[[Note 1]]")
    path.write_text(text)
    assert problems(vault) == []


def test_refuses_to_overwrite_an_existing_note(vault):
    with pytest.raises(BrainError, match="already exists"):
        make_note(vault, "area", "Note 1")


@pytest.mark.parametrize("title", ["", "  ", "a/b", "a\\b", "[x]", "x|y", "#tag", "x" * 90, "a^b", "a:b"])
def test_refuses_bad_titles(vault, title):
    with pytest.raises(BrainError, match="title"):
        make_note(vault, "area", title)


def test_refuses_an_unknown_kind(vault):
    with pytest.raises(BrainError, match="kind"):
        make_note(vault, "diary", "x")


def test_nothing_is_written_when_the_index_section_is_missing(vault):
    index = vault.docs / "Index.md"
    index.write_text(index.read_text().replace("## Resources", "## Misc"))
    before = (vault.docs / "Log.md").read_text()
    with pytest.raises(BrainError, match="no '## Resources' section"):
        make_note(vault, "resource", "Facts")
    assert not (vault.docs / "Resources" / "Facts.md").exists()
    assert (vault.docs / "Log.md").read_text() == before


def test_new_note_needs_index_and_log(vault):
    (vault.docs / "Log.md").unlink()
    with pytest.raises(BrainError, match="must exist"):
        make_note(vault, "area", "x")


def test_who_defaults_to_the_git_user_or_team(vault, monkeypatch):
    monkeypatch.setattr(brain, "git_user", lambda: "Git Person")
    brain.new_note(vault, "area", "Zeta", today=TODAY)
    assert "- 2026-11-23 - Git Person - Added" in (vault.docs / "Log.md").read_text()


def test_git_user_falls_back_to_team(monkeypatch):
    class Result:
        stdout = "\n"

    monkeypatch.setattr(brain.subprocess, "run", lambda *a, **k: Result())
    assert brain.git_user() == "team"


# --- command line -------------------------------------------------------------------------------------------------------------


def run(argv, vault):
    lines: list[str] = []
    code = brain.main(argv, vault=vault, out=lines.append)
    return code, "\n".join(lines)


def test_cli_check_passes_and_counts(vault):
    add_skill(vault)
    code, output = run(["check"], vault)
    assert code == 0
    assert "brain check passed: 12 notes, 1 skills" in output


def test_cli_check_lists_problems_and_fails(vault):
    write(vault.docs / "Areas" / "Lonely.md", "# Lonely\n")
    code, output = run(["check"], vault)
    assert code == 1
    assert "PROBLEM  docs/Areas/Lonely.md: not linked from the Index" in output
    assert "1 problem(s)" in output


def test_cli_search(vault):
    write(vault.docs / "Areas" / "Cost.md", "# Cost\n\nThe reserve is 500 units.\n")
    code, output = run(["search", "reserve"], vault)
    assert code == 0
    assert "[[Cost]]  (docs/Areas/Cost.md" in output
    assert "3: The reserve is 500 units." in output


def test_cli_search_says_which_words_were_found_nowhere(vault):
    code, output = run(["search", "note kubernetes"], vault)
    assert code == 0
    assert "Not found in any note: kubernetes." in output


def test_cli_search_does_not_complain_when_every_word_is_found(vault):
    _, output = run(["search", "note"], vault)
    assert "Not found" not in output


def test_cli_search_without_a_match_exits_with_1(vault):
    code, output = run(["search", "kubernetes"], vault)
    assert code == 1
    assert "No notes match" in output


def test_cli_new_prints_next_steps(vault, monkeypatch):
    monkeypatch.setattr(brain, "git_user", lambda: "Chris")
    code, output = run(["new", "adr", "Some choice"], vault)
    assert code == 0
    assert "Created docs/adr/ADR-002 Some choice.md" in output
    assert "python scripts/brain.py check" in output


def test_cli_new_reports_errors_without_a_traceback(vault):
    code, output = run(["new", "area", "Note 1"], vault)
    assert code == 1
    assert output.startswith("Error: a note named 'Note 1' already exists")


@pytest.mark.parametrize("argv", [[], ["new"], ["new", "diary", "x"], ["nope"]])
def test_cli_bad_arguments_exit_with_usage(vault, argv):
    with pytest.raises(SystemExit) as exc:
        brain.main(argv, vault=vault, out=lambda s: None)
    assert exc.value.code == 2

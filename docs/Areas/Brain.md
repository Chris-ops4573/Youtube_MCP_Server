# Brain

The Obsidian vault in `docs/` is the project's memory. Agents read it before working and update it after (SB, see AGENTS.md). Open the `docs` folder in Obsidian to browse it. Start at [[Index]].

## PARA: where a note goes
| Folder | What belongs there | Example |
|---|---|---|
| `Projects/` | Work with a stage or an end date | [[Stage 2 Review]], [[Development Plan]] |
| `Areas/` | Ongoing parts of the system we keep up to date | [[Architecture]], [[Auth]], [[Cache]] |
| `Resources/` | Reference material | [[Requirements]], [[Glossary]], [[Traceability]] |
| `Archive/` | Finished or out-of-date notes (move here, do not delete) | empty so far |
| `adr/` | One note per design decision | [[ADR-001 Provider interface]] |

## Rules every note follows
- Linked from [[Index]], so nothing is orphaned.
- Links to other notes use `[[wikilinks]]`, and every link points at a note that exists.
- Every ADR is named `ADR-001 Title`, has Status, Context, Decision and Consequences, and ends with a `Cites:` line that links at least one note (SE-3).
- Every change adds one line to [[Log]]: `- YYYY-MM-DD - who - what`.
- File paths written in `backticks` must exist, so notes cannot describe deleted code.
- No `TODO` left behind.

## The brain skills (SK-3)
The project also has two other skills: `local-check` ([[Testing]]) and `video-to-playlist` ([[Playlist]]). The brain skills live in `.claude/skills/`. Each one has an `evals.md` with test cases (TQ-7). Results are in [[Skill Evaluations]].

| Skill | Use it to |
|---|---|
| `brain-query` | Ask a question and get an answer that cites the notes it used |
| `brain-ingest` | Add a decision, project, area or resource note in the right place |
| `brain-refine` | Find and fix problems: broken links, ADRs without `Cites:`, notes missing from the Index |

## The script behind them
`python scripts/brain.py` (standard library only):
```bash
python scripts/brain.py check                      # validate notes and skills
python scripts/brain.py search "quota reserve"     # find notes
python scripts/brain.py new adr "Some decision"    # create a note, list it in the Index, add a Log line
```
`new` writes a skeleton with `TODO` markers on purpose: `check` fails until they are filled in, so a half-written note cannot be merged by accident.

## What CI checks
On every pull request CI runs `python scripts/brain.py check` (SRS section 6). It checks:
- at least 10 notes, the four PARA folders, `Index` and `Log` exist
- links, Index coverage, ADR format, Log line format, no `TODO`, paths in backticks exist
- every `SKILL.md`: valid frontmatter (`name` matching its folder, a one-line `description` of at most 1024 characters), instructions, a `Brain note:` line citing a real note (SK-4), and an `evals.md` with at least 3 cases

`local-check` runs it too, so you find problems before pushing: see [[Testing]].

Why it is built this way: [[ADR-012 Brain checks in a standard library script]].

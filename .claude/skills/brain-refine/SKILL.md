---
name: brain-refine
description: Check the Obsidian vault in docs/ and the Agent Skills for problems and fix them - broken links, notes missing from the Index, ADRs without a Cites line, bad Log lines, TODO markers, notes that name files that no longer exist. Use before a pull request that touches docs/ or .claude/skills/, or when asked to tidy, review or fix the brain.
---

# brain-refine (SK-3)

Finds problems with the checker and makes the smallest fix for each. The same checker runs in CI, so a clean result here means CI will accept the notes.

## Steps
1. Run the checker:
   ```bash
   source .venv/bin/activate
   python scripts/brain.py check
   ```
   Each `PROBLEM` line names the file and what is wrong.
2. Fix each problem with a small edit to that note:
   - broken link: fix the spelling or point it at the right note
   - not linked from the Index: add `- [[Note]]` under the right section of `docs/Index.md`
   - ADR without `Cites:`: add a `Cites: [[Note]]` line naming a note the decision is really based on
   - path `x` does not exist: find where the file moved to, or remove the mention if the code is gone
   - `TODO`: fill it in from real facts, or ask the user. Never delete it just to pass.
3. Run the checker again until it prints `brain check passed`.
4. Beyond the checker, spot-check one thing: pick a row of `docs/Resources/Traceability.md` and confirm the code and test it names still do what the row says.
5. Add one line to `docs/Log.md` if you changed notes. Report what you fixed and anything you left for a person to decide.

## Never
- Delete a note, or rewrite the SRS in `docs/requirements/`.
- Move a note to `docs/Archive/` without asking.
- Invent facts to fill a gap: ask instead.

Brain note: [[Brain]]

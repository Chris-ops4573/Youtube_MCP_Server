---
name: brain-ingest
description: Add new knowledge to the Obsidian vault in docs/ in the right place - a design decision (ADR), a project note, an area note or a resource - and keep the Index and Log up to date. Use when asked to record, document, note down, save or add something to the brain.
---

# brain-ingest (SK-3)

Puts new knowledge in the right folder, links it, and makes sure the checker still passes.

## Steps
1. Decide what kind of note it is:
   - a decision and its reason: `adr`
   - work with a stage or an end (a stage review, a plan): `project`
   - an ongoing part of the system (how a module works): `area`
   - reference facts (a glossary entry, a list, an API limit): `resource`
2. Search first, so you do not create a duplicate:
   ```bash
   source .venv/bin/activate
   python scripts/brain.py search "words about the topic"
   ```
   If a note already covers it, update that note instead (a new glossary term goes in the Glossary, not a new note).
3. Otherwise create the note. This also lists it in the Index and adds a Log line:
   ```bash
   python scripts/brain.py new adr "Short title of the decision"
   ```
4. Fill in the skeleton using facts from the user, the code or the SRS. Do not guess: ask if something is unknown.
   - ADR: Context, Decision, Consequences, and a `Cites:` line with `[[links]]` to the notes the decision is based on.
   - Other notes: link related notes with `[[wikilinks]]`.
5. If it relates to a requirement, add or update its row in `docs/Resources/Traceability.md`.
6. Run `python scripts/brain.py check` until it prints `brain check passed`.
7. Tell the user which note was created or updated and why it went in that folder.

## Never
- Leave `TODO` markers behind, edit the SRS in `docs/requirements/`, or move notes to `docs/Archive/` without asking first.

Brain note: [[Brain]]

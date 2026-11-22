---
name: brain-query
description: Answer a question about this project from the Obsidian vault in docs/ and cite the notes used. Use when asked what we decided, why something is built a certain way, what a requirement or term means, how a part works, what a cost or limit is, or what is left to do.
---

# brain-query (SK-3)

Answers questions from the notes only, and says which notes each fact came from.

## Steps
1. Read `docs/Index.md` to see what notes exist.
2. Find candidates with the search script, using the key words from the question:
   ```bash
   source .venv/bin/activate
   python scripts/brain.py search "quota reserve"
   ```
   If nothing matches, try other words (synonyms, the requirement ID, a file name). The script also prints `Not found in any note: ...` for words that appear nowhere. If the key words of the question are listed there, the notes probably do not cover it.
3. Read the best 1 to 3 notes in full. Follow a `[[link]]` one step if the answer is in the linked note, for example from an Area note to its ADR.
4. Answer in plain language using only what the notes say. After each fact, cite the note like this: [[Quota]].
5. If the notes do not answer the question, say so plainly. Do not guess and do not cite notes that are unrelated. Suggest running `brain-ingest` to add the missing knowledge.
6. If a note disagrees with the code or looks out of date, say so and name the file. Do not edit anything: that is `brain-refine`'s job. For "what changed lately" questions, read the end of `docs/Log.md`.

Read-only: this skill never changes files.

Brain note: [[Brain]]

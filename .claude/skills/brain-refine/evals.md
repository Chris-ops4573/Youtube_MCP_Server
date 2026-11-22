# brain-refine evals (TQ-7)

Run each case on a throwaway copy of the repo so the real notes are not touched. A person reads the result and marks pass or fail. Record results in docs/Resources/Skill Evaluations.md.

## Case 1: a broken link
Prompt: (add the text [[Quota Limits]] to docs/Areas/Cache.md, then) Run brain-refine.
Expect: The checker reports the broken link in Cache.md. The skill fixes it by pointing it at [[Quota]] (or removing it) and the checker then passes. No other note is changed.

## Case 2: an ADR that cites nothing
Prompt: (delete the Cites: line from an ADR, then) Run brain-refine.
Expect: The checker reports the missing Cites line. The skill adds a Cites line naming a real, related note and the checker passes. It does not cite a random note.

## Case 3: nothing is wrong
Prompt: Run brain-refine.
Expect: The checker passes on the first run. The skill reports that nothing needed fixing and makes no edits, including no Log line.

## Case 4: a TODO it cannot fill in
Prompt: (create a note with python scripts/brain.py new area "Scratch", leave the TODO, then) Run brain-refine.
Expect: The skill does not invent content. It reports that the note is unfinished and asks the user what it should say, or offers to leave it for them.

## Case 5: the checker catches each mistake
Prompt: (automatic) run the tests in tests/test_brain.py
Expect: Tests cover a broken link, a note missing from the Index, a bad ADR, a bad Log line, a TODO, a missing path, and bad skill files, and all pass.

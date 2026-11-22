# brain-ingest evals (TQ-7)

Run each case on a throwaway copy of the repo. A person reads the result and marks pass or fail. Record results in docs/Resources/Skill Evaluations.md.

## Case 1: a new decision
Prompt: Record the decision that find_similar_channels checks 15 candidates by default, because each one needs one more API call.
Expect: Uses `brain.py new adr`, so the next ADR number is used. The ADR has real Context, Decision and Consequences, and a Cites line linking [[Channels]]. The Index and Log have new lines. The checker passes. No TODO is left.

## Case 2: it belongs in an existing note
Prompt: Add what "Testing mode" means for a Google OAuth app.
Expect: Searches first, finds the Glossary or Auth note, and updates it instead of creating a new note. The checker passes.

## Case 3: moving to the Archive needs permission
Prompt: Move the Stage 1 Review note to the Archive.
Expect: Asks the user to confirm before moving anything. Does not move it on its own.

## Case 4: not enough facts
Prompt: Record why we picked the cache expiry times.
Expect: Reads the notes and code, records only what they support (the YouTube terms require refreshing stale data), and asks about anything it cannot support instead of inventing a reason.

## Case 5: the script behaves
Prompt: (automatic) run the tests in tests/test_brain.py
Expect: Tests cover the ADR number, the Index and Log updates, refusing a duplicate, refusing bad titles, and the TODO guard, and all pass.

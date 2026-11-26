# brain-query evals (TQ-7)

Run each prompt in a fresh Claude Code session with the skill. A person reads the answer and marks it pass or fail. Record results in docs/Resources/Skill Evaluations.md.

## Case 1: a number that is in the notes
Prompt: How many quota units does one find_similar_channels request cost?
Expect: Says 119 units. Cites [[Quota]] or [[Channels]]. Does not invent other numbers.

## Case 2: a decision and its reason
Prompt: Why does the server only use stdio?
Expect: Says it is single-user and local, and that HTTP would need its own authentication. Cites [[ADR-009 Stdio transport only]].

## Case 3: a fact spread over two notes
Prompt: Where are the Google login tokens stored, and what happens when they expire?
Expect: Says only in the OS keyring, never in files or the database. Says an expired login that cannot be renewed gives AUTH_REQUIRED and the user signs in again. Cites [[Auth]] (and may cite [[Design Data]]).

## Case 4: something the notes do not cover
Prompt: How is the Redis cluster configured?
Expect: The search prints "Not found in any note: redis, cluster". The answer says the notes do not cover this. It does not make up an answer and does not cite the unrelated notes the search still lists.
Keep this question out of the notes: if a note ever contains these words, the search finds them and this case stops working. (The first version of this case, a question about Kubernetes, broke exactly like that in Stage 3.)

## Case 5: the script finds the right note first
Prompt: (run the script) python scripts/brain.py search "why stdio only"
Expect: The first result is [[ADR-009 Stdio transport only]]. This case is also checked automatically by tests/test_brain.py.

# local-check evals (TQ-7)

Run each case in a fresh Claude Code session with the skill. A person reads the result and marks pass or fail. Record results in docs/Resources/Skill Evaluations.md.

## Case 1: everything is fine
Prompt: Run local-check.
Expect: Runs `python scripts/local_check.py` and reports a PASS or FAIL line for every step: build, lint, tests, the brain and skills check, and the server. Says all steps passed. Changes no files.

## Case 2: a lint error
Prompt: (add an unused import to any file under src/, then) Run local-check.
Expect: The lint step shows FAIL with the ruff message. The skill suggests the fix and does not change code unless the user asks.

## Case 3: a failing test
Prompt: (break an assert in any test, then) Run local-check.
Expect: The tests step shows FAIL with the failing test name. The later steps still run and are reported.

## Case 4: no live calls
Prompt: Run local-check with my YouTube API key in .env.
Expect: Uses fixture data only. No quota is spent and no real YouTube request is made (TQ-5).

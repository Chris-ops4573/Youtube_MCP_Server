# Stage 4 Checklist

Stage 4 = Release: a live demo and the release tag. Written so one person can follow it from top to bottom. Status of everything before it: [[Stage 3 Review]].

## Before the demo
- [ ] `main` is up to date and `python scripts/local_check.py` passes (or `python -m ytmcp local-check`), see [[Testing]]
- [ ] `.env` has the API key and the OAuth client ([[Auth]]), and `python -m ytmcp auth status` says signed in
- [ ] Signed in with write access: `python -m ytmcp auth login --write` (the 7 day Testing-mode limit means signing in again if it was a while ago)
- [ ] `python -m ytmcp quota status` shows plenty of units left; the demo uses about 500 (see the costs in [[Tool Reference]])
- [ ] The AI client is connected to the server with the snippet in the README, and the tools are listed
- [ ] The skill cases in [[Skill Evaluations]] have been judged by a person
- [ ] The open TBDs are closed or written down as open in [[Stage 3 Review]]

## Live demo script
Use a video you know. Each step says what to show and what to say.

1. **Similar videos.** Ask: "Find videos similar to <a video URL>." Show the ranked list with scores. Say: the score is from titles, tags, category, language, channel and length, and there is no related-videos API, so this is built from metadata ([[Similarity]]).
2. **Similar channels.** Ask: "Find channels like <@handle>." Show the subscribers count and the score.
3. **Recommendations.** Ask: "Recommend 5 videos for me." Show the reasons. Say: it only reads your account, read-only ([[Recommendations]]).
4. **Engagement.** Ask: "What do I like? Compare the last 6 months with the 6 before." Show the top channels, the monthly trend, and the note that watch history is not used ([[Engagement]]).
5. **A playlist, with the safety rules.** Ask: "Make a 20 minute playlist from <a video URL>." Show the proposal. Say: nothing has been created yet. Ask for it to be created; show that the client asks **you**, then answer yes. Open the link and show that it is private. Say: the AI has no argument to confirm for itself, and writes are never retried ([[Playlist]]).
6. **Say no.** Ask for another playlist and answer no. Show that nothing is created.
7. **An error.** Ask for a video that does not exist, or run with the quota nearly full. Show the code, message and fix ([[Errors]]).
8. **The checks.** Run `python -m ytmcp local-check` and `python -m ytmcp quota status`. Show the coverage and the quota left.
9. **Clean up.** Delete the demo playlists on YouTube.

## Release
- [ ] The Unreleased section of `CHANGELOG.md` is empty or moved under the new version
- [ ] CI is green on `main`
- [ ] **The tag is created and pushed by a person**, not by an AI agent:
  ```bash
  git checkout main && git pull --ff-only origin main
  git tag v1.0.0
  git push origin v1.0.0
  ```
- [ ] The release notes are the 1.0.0 part of `CHANGELOG.md`

# ADR-013 Playlist creation needs a person's confirmation

Status: Accepted

## Context
Creating a playlist writes to the user's real YouTube account. The SRS says it must
happen only with explicit confirmation, enforced on the server, so video text can
never trigger a write (FR-5.5), and that text from YouTube cannot bypass
confirmation (SRS 5.3). The AI client is only semi-trusted because untrusted video
text can influence it (SRS 2.3). A confirmation the AI supplies itself, such as a
`confirmed=true` argument, would let a fooled AI bypass the rule.

## Decision
- A person must approve, and the AI has **no way to approve**. `create_playlist` takes only `proposal_id` and `content_hash`: there is no confirmation argument.
- **First choice: ask through the client** (MCP elicitation). The server first checks that the client declared support, then asks "Create the PRIVATE playlist ...?". Only an accepted answer with the box ticked counts. Declining, cancelling or an unusable answer ends the proposal with nothing created.
- **If the client cannot ask:** the user confirms in a terminal with `python -m ytmcp playlist confirm <proposal_id>`. It refuses to run unless input and output are a real terminal, so scripts and shell tools cannot answer for the user.
- Every create also needs: a proposal made by the server, not expired (15 minutes), not used before, and a `content_hash` that matches both what was sent and what is stored.
- The server **claims** the proposal in one atomic database step before writing, so only one caller can ever create from it.
- Quota (50 + 50 per video) and write permission are checked **before** the proposal is claimed, so a fixable problem does not use it up.
- Playlists are always **private**. The only YouTube calls are `playlists.insert` and `playlistItems.insert`: nothing can be edited or deleted.
- **Writes are not retried.** A retry after an unclear failure could create a duplicate playlist (this narrows SRS 3.4, which is about reads).
- Write permission is requested only when needed: `python -m ytmcp auth login --write`, not inside the tool call, so no browser opens in the middle of a request.

## Consequences
- A client that answers the question automatically, instead of asking a person, cannot be detected. The MCP library says an agent client may do that. Private, create-only playlists limit the harm.
- An AI that can open a real interactive terminal could run the confirm command. Shell tools without a terminal cannot.
- Under the newer 2026 MCP protocol the server cannot ask mid-call, so the terminal path is always used there. This was seen in testing.
- A failed or partly created playlist is not retried: a new proposal is needed.
- Proposals must be shared with the terminal command, so they are kept in the SQLite file even with the cache off.

Cites: [[Playlist]], [[Auth]], [[Design Sequences]]

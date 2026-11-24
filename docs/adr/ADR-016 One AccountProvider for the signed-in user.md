# ADR-016 One AccountProvider for the signed-in user

Status: Accepted

## Context
FR-3 (recommendations) and FR-4 (engagement analysis) must read the user's likes, subscriptions and playlists with the user's Google login. The existing PlaylistWriter interface only creates playlists. Reads and writes both act as the signed-in user, unlike VideoProvider, which reads public data with an API key.

## Decision
- Rename **PlaylistWriter to AccountProvider** and add the read methods to it: liked videos (newest first, with the date liked), subscriptions, and the video IDs in the user's playlists. The live class is renamed from YouTubePlaylistWriter to YouTubeAccount.
- **Reads** use the read-only scope and are retried like the other reads (the retry loop is shared).
- **Writes** keep their rules: the write-scope check, never retried, private playlists only, create only ([[ADR-013 Playlist creation needs a person's confirmation]]).
- In fixture mode there is **no account** (it is None). The tools then answer ACCOUNT_NOT_AVAILABLE for recommendations and engagement, and PLAYLIST_WRITES_DISABLED for creating a playlist.
- A separate AccountReader interface was considered and rejected: it adds one more interface for what is one idea, "things done as the signed-in user".

## Consequences
- One interface to explain: everything done as the signed-in user.
- The class grows, but its tests use one FakeAccount.
- Reads need only the read scope, so no write permission is needed for FR-3 and FR-4.
- All YouTube access now goes through two interfaces, not one. The notes that say "all YouTube access goes through VideoProvider" are corrected in task R6.
- Reads and writes share one quota counter, built in config.py.

Cites: [[Auth]], [[Playlist]], [[Providers]]

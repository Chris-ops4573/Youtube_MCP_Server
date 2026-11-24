# Auth

Google sign-in (OAuth) so the server can read the user's own YouTube data later (FR-3, FR-4) and create playlists (FR-5). An API key can only read public data: see [[Providers]].
Files: `src/ytmcp/auth/` (`oauth.py`, `pkce.py`, `loopback.py`, `tokens.py`, `service.py`), `src/ytmcp/cli.py`

## Commands (UI-4)
```bash
python -m ytmcp auth login    # opens the browser, asks for read-only access
python -m ytmcp auth login --write   # also allows creating playlists (needed before the first one)
python -m ytmcp auth status   # signed in? what access? (never prints tokens)
python -m ytmcp auth logout   # tells Google to cancel the login, deletes the saved one
```
The same program has three more commands:
```bash
python -m ytmcp quota status   # units used today, reserve, units left, time until the reset (midnight Pacific)
python -m ytmcp serve          # starts the MCP server, the same as python -m ytmcp.server
python -m ytmcp local-check    # runs scripts/local_check.py (build, lint, brain, tests, server)
```
`quota status` only counts calls made by this server ([[Quota]]). `local-check` needs the project folder, and says so if the script is missing ([[Testing]]).

## How login works (FR-6.1)
1. Create a one-time secret (PKCE verifier) and a random `state` in memory.
2. Start a tiny web server on `127.0.0.1` (this computer only, any free port) to catch the redirect.
3. Open Google's sign-in page in the browser; the link is also printed in case it doesn't open.
4. Google sends the browser back to `http://127.0.0.1:<port>/callback?code=...&state=...`.
5. Check `state` matches (stops forged redirects). Then swap the `code` plus the PKCE verifier for tokens.
6. Save the tokens in the OS keyring.

## Access levels
| Scope | Used for |
|---|---|
| `youtube.readonly` (default) | reading likes, subscriptions and playlists, done by `YouTubeAccount` ([[Providers]]); FR-3 and FR-4 are built on it |
| `youtube` (write) | creating playlists only. Request it once with `python -m ytmcp auth login --write`: see [[Playlist]] |

A write login also counts as read access.

## Keeping the login (FR-6.2)
- Tokens go **only** in the OS keyring (one entry, `ytmcp` / `google-oauth-token`). Never in files, the SQLite cache, logs or error messages. A test checks nothing is written to disk.
- Later features call `AuthService.get_access_token()`. It returns a valid token, renewing it when it expires.
- If renewal fails (`invalid_grant`, including Google's **7-day limit for apps in Testing mode**), the saved login is deleted and the user gets `AUTH_REQUIRED`: "Your Google login has expired. Please sign in again."

## Setup (needed once, by the user)
1. Google Cloud Console, same project as the API key -> APIs & Services -> OAuth consent screen: add yourself as a **test user**.
2. Credentials -> Create credentials -> OAuth client ID -> **Desktop app**.
3. Put the client ID and secret in `.env` (`YTMCP_OAUTH_CLIENT_ID`, `YTMCP_OAUTH_CLIENT_SECRET`). For a desktop app the secret is not truly secret, but it still stays out of git.
4. Run `python -m ytmcp auth login`.

## Safety rules (SRS 5.3)
- Only Google's short error code (like `invalid_grant`) is ever shown, never tokens, codes, or response bodies.
- `Token` and `OAuthConfig` hide their values when printed.
- The redirect page doesn't repeat the code and the receiver only listens on `127.0.0.1`.

## Not built yet
- Features that use the token (FR-3, FR-4, FR-5). This branch only gets and keeps the token.
- Real sign-in has not been tried against Google yet: it needs the OAuth client from the setup above. Tests use a fake Google, a fake keyring and no browser.

Why: [[ADR-007 OAuth with PKCE and keyring]]. Part of [[Architecture]].

# ADR-007 OAuth with PKCE and keyring

Status: Accepted

## Context
FR-3, FR-4 and FR-5 need the user's own YouTube data, which an API key cannot
read (see [[Auth]]). The SRS requires OAuth with PKCE, read-only by default
(FR-6.1), tokens only in the OS keyring, and asking the user to sign in again
when the login expires (FR-6.2).

## Decision
- Use Google's OAuth for installed apps: PKCE (S256), a random `state`, and a loopback redirect to `127.0.0.1` on a free port.
- Write the OAuth calls with `urllib`, like the YouTube provider, so tests can pass in a fake `post` function and no OAuth library is needed.
- Store tokens with the `keyring` package, in one entry, as JSON.
- Build `AuthService.get_access_token()` as the single way later features get a token. It renews expired tokens and raises `AUTH_REQUIRED` when the user must sign in again.
- Ship only `auth login | status | logout` now; the rest of the CLI (UI-4) comes later.
- Request `youtube.readonly` by default; the write scope is a parameter that FR-5 will use.

## Consequences
- Needs a Google OAuth client ID from the user, and a working OS keyring (a headless Linux box without one gets a clear `AUTH_FAILED` message).
- Apps in Google's Testing mode lose their refresh token after 7 days, so the user signs in weekly until the app is published.
- The loopback receiver handles one request at a time with no threads, which keeps the code simple and testable.
- Real Google sign-in is untested until the user adds an OAuth client.

Cites: [[Auth]], [[Errors]]

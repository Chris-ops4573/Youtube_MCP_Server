# Design Components

Design document 1 of 4 (SE-2). The others: [[Design Classes]], [[Design Sequences]], [[Design Data]].
The same layers in words: [[Architecture]].

## Components and how they connect
Everything runs as **one local process** on the user's computer. The AI client talks to it over MCP (stdio). Only two things leave the computer: calls to YouTube and calls to Google.

```mermaid
flowchart LR
  Client["AI client"] -->|"MCP over stdio"| Server["server.py"]
  Server --> Tools["tools.py"]
  Tools --> Services["services/"]
  Services --> Sim["similarity.py"]
  Services --> Caching["CachingProvider"]
  Services -.->|"fixture mode and tests"| Fixture["FixtureProvider"]
  Caching --> Live["YouTubeProvider"]
  Caching --> DB[("SQLite database")]
  Live --> Quota["QuotaTracker"]
  Quota --> DB
  Live -->|"HTTPS and API key"| YT["YouTube Data API v3"]
  CLI["cli.py"] --> Auth["AuthService"]
  Auth --> KR[("OS keyring")]
  Auth -->|"HTTPS OAuth with PKCE"| Google["Google OAuth"]
  Auth -.->|"redirect to 127.0.0.1"| Browser["Browser"]
  Services --> Planner["playlist_planner.py"]
  Services --> Store["ProposalStore"]
  Store --> DB
  Services --> Account["YouTubeAccount"]
  Account --> Quota
  Account -->|"HTTPS and your OAuth token"| YT
  Account -.->|"asks for a login token (read or write)"| Auth
  CLI -->|"playlist confirm"| Store
  Server --> Config["config.py (builds the objects)"]
  CLI --> Config
```

## What each part is for
| Part | Job | Code |
|---|---|---|
| MCP server | Registers the tools and asks the user to confirm a playlist | `src/ytmcp/server.py` |
| Config | Reads the settings and builds the objects for the server and the CLI. It imports neither | `src/ytmcp/config.py` |
| Tools | Check arguments, format results and errors (UI-1, UI-3) | `src/ytmcp/tools.py` |
| Services | The feature logic (FR-1, FR-2) | `src/ytmcp/services/` |
| Similarity | Pure scoring maths for videos and channels, no API calls | `similarity.py` |
| Providers | All YouTube access (SE-6) | `src/ytmcp/providers/` |
| Database and quota | The one SQLite file (cache, quota count, proposals) and the daily unit count (FR-7) | `database.py`, `quota.py` |
| Auth | Google sign-in and token storage (FR-6) | `src/ytmcp/auth/` |
| CLI | `auth login`, `status`, `logout` (UI-4, partly) | `cli.py` |

## Rules this design keeps
- Services never call YouTube directly, only through `VideoProvider` ([[ADR-001 Provider interface]]).
- Tools never raise to the client: errors become `{code, message, remediation}` ([[ADR-003 Structured errors]]).
- The cache sits **in front of** the live provider and has the same interface ([[ADR-005 SQLite cache]]).
- Tokens only ever go to the OS keyring ([[ADR-007 OAuth with PKCE and keyring]]).
- Only stdio is used to talk to the AI client ([[ADR-009 Stdio transport only]]).

## Playlists (built)
FR-5 adds `propose_playlist` and `create_playlist`. The account provider is separate from the read providers: reading public data uses the API key, acting as the user (reading likes, subscriptions and playlists, and creating a playlist) uses the user's own login. Only `create_playlist` ever writes, and only after a person confirms: see [[Playlist]] and [[Design Sequences]].

## Not built yet (planned)
FR-3 recommendations and FR-4 engagement analysis will be new **services and tools** in the same layers. The account provider already reads the likes, subscriptions and playlists they need.

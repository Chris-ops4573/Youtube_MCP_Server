# YouTube Video Intelligence MCP Server

An MCP server that lets an AI client (for example Claude) work with YouTube through the **official YouTube Data API v3**. It can:

- find videos and channels similar to one you name,
- recommend videos from your own likes, subscriptions and playlists,
- report statistics about your own engagement,
- plan a playlist of a given length and, **only after you confirm**, create it as a private playlist.

It runs on your own computer and talks to the client over stdio. It never writes to your YouTube account without your explicit yes.

## Setup
Needs Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

1. **API key** (public data: similar videos and channels, playlist planning). In Google Cloud Console enable "YouTube Data API v3", create an API key, and put it in `.env` as `YOUTUBE_API_KEY`.
2. **Google sign-in** (your own data: recommendations, engagement, creating playlists). In the same project, create an OAuth client of type "Desktop app", add yourself as a test user, and put the client ID and secret in `.env` as `YTMCP_OAUTH_CLIENT_ID` and `YTMCP_OAUTH_CLIENT_SECRET`. Then sign in:

```bash
python -m ytmcp auth login            # read-only access
python -m ytmcp auth login --write    # also allows creating playlists (needed once, before the first one)
python -m ytmcp auth status
python -m ytmcp auth logout
```

Your login is kept only in the operating system keyring. While the Google app is in Testing mode, Google ends the login after 7 days: just sign in again.

To try the server without an API key or quota, set `YTMCP_PROVIDER=fixture` (sample data, no account features).

## Connect an AI client
The package is run from the project folder, so the client needs the full paths. Example `.mcp.json` for Claude Code (change the paths):

```json
{
  "mcpServers": {
    "youtube": {
      "command": "/path/to/Youtube_MCP_Server/.venv/bin/python",
      "args": ["-m", "ytmcp.server"],
      "env": { "PYTHONPATH": "/path/to/Youtube_MCP_Server/src" }
    }
  }
}
```

The server finds `.env` in the project folder by itself.

## What you can ask
| Tool | Example prompt |
|---|---|
| `find_similar_videos` | "Find videos similar to https://www.youtube.com/watch?v=..." |
| `describe_video` | "Describe this video: ..." |
| `find_similar_channels` | "Find channels like @fireship" |
| `propose_playlist` | "Plan a 60 minute playlist about rust programming, at most 20 minutes per video, in English" |
| `create_playlist` | "Create that playlist" (you are asked to confirm) |
| `recommend_videos` | "Recommend 10 videos based on what I like" |
| `analyze_engagement` | "What kinds of videos do I like? Compare the last 6 months with the 6 before" |

The `video-to-playlist` skill (in `.claude/skills/`) strings several of these together: "Make a 45 minute playlist from this video".

Every tool, its arguments, results, errors and quota cost: see [Tool Reference](docs/Resources/Tool%20Reference.md). Plain-language steps and what each error means: [User Guide](docs/Resources/User%20Guide.md).

## Commands
```bash
python -m ytmcp auth login|status|logout     # Google sign-in
python -m ytmcp playlist confirm <id>        # confirm a playlist proposal in a terminal
python -m ytmcp quota status                 # today's YouTube quota use
python -m ytmcp serve                        # start the server (same as python -m ytmcp.server)
python -m ytmcp local-check                  # build, lint, brain check, tests, server check
```
When you run these from a terminal, use `PYTHONPATH=src` in front (or set it once in your shell).

## Developing
```bash
pytest            # tests, fixtures only, no live API calls
ruff check .      # lint
python scripts/local_check.py        # everything CI checks, in one go
python scripts/brain.py check        # validates the notes and skills in docs/
```
Tests must keep coverage at 80% or more. Rules for contributors and AI agents are in [AGENTS.md](AGENTS.md).

## Where things are written down
The project's notes live in `docs/` (an Obsidian vault): start with `docs/Index.md`. The requirements are in `docs/requirements/`, design decisions in `docs/adr/`, and what changed in [CHANGELOG.md](CHANGELOG.md).

## Safety in short
- Only the official API is used.
- Nothing is written to your account without your confirmation, and only `create_playlist` writes: it creates a new **private** playlist and never edits or deletes.
- Login tokens live only in the OS keyring and are never printed or logged.
- Quota is checked before work starts, so a request that cannot finish is refused early.

## Known limits
Not built, by decision: scheduled live-API tests, Windows and macOS CI, and automated performance checks. YouTube does not share watch history, so nothing here uses it. See `docs/Projects/Refactor and Feature Plan.md` for the full list.

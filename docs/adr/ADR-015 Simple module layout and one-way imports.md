# ADR-015 Simple module layout and one-way imports

Status: Accepted

## Context
The source grew one feature at a time and became busy. An audit found: server.py imports cli.py; the channel and playlist tool files import shared helpers from the video tool file; server.py registers tools, builds objects and asks the user to confirm, all in one file; cache.py also holds the quota count and the proposals, so its name misleads; scoring is split over two files; the playlist writer copies YouTube helpers; and two `__init__.py` files re-export names. The team must be able to explain every part in a viva, so the layout should be as simple as possible.

## Decision
- **Imports only point down** this list: entry points (server.py, cli.py); config.py and tools.py; services; logic and access (similarity.py, playlist_planner.py, proposals.py, quota.py, providers, auth); database.py; models.py, errors.py, ids.py, durations.py. The one exception: cli.py imports server.py inside its serve command, because both are entry points.
- **config.py** reads settings and builds the objects for both entry points, and imports neither.
- **One tools.py** replaces the tools package, with the shared helpers at the top.
- **One similarity.py** holds video, channel and taste scoring.
- **All YouTube HTTP code** (reads and writes) lives in providers: youtube.
- **cache.py becomes database.py**, with the class Database.
- **No re-export barrels:** a name is imported from the file that defines it.
- **No new layer, base class or abstraction** unless it can be justified in one sentence a student could repeat.
- The refactor must not change behavior: tests only change their import lines.

## Consequences
- Fewer files and one clear job per file, so the whole design fits on [[Architecture Overview]].
- tools.py will be about 350 lines, in one place that shows everything the AI client sees.
- The cleanup is split into small pull requests (R1 to R6 in [[Refactor and Feature Plan]]) so main stays green.
- ADR-001's single provider interface becomes two interfaces: see [[ADR-016 One AccountProvider for the signed-in user]].
- Older notes that mention the old file names are updated task by task.

Cites: [[Architecture Overview]], [[Refactor and Feature Plan]]

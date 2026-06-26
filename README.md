# hawk-scope

Server that slices subsets out of a larger webdataset collection.

## Overview

hawk-scope indexes webdataset shards into a SQLite database and serves scoped subsets as WIDS descriptors and streaming tar archives. It supports:

- **WIDS descriptors** — JSON manifests describing shard layout and sample counts
- **Streaming tar shards** — on-demand range-request fetches from remote webdataset archives
- **CLI tools** — generate descriptors and shards from the command line

## Installation

Requires Python 3.10+ and the [uv](https://github.com/astral-sh/uv) package manager.

```bash
uv sync          # install dependencies from uv.lock
```

## Usage

### CLI

```bash
uv run hawk_scope wids <scope>     # print WIDS descriptor JSON for a scope
uv run hawk_scope shard <scope>    # generate a local tar shard file
uv run hawk_scope serve            # start the web server (port 5000)
```

### Web server

```bash
uv run hawk_scope serve
```

Serves on `0.0.0.0:5000` by default. Three endpoints:

| Endpoint | Description |
|---|---|
| `GET /` | HTML animation page |
| `GET /{scope}.json` | WIDS descriptor JSON |
| `GET /{scope}-{shard}.tar` | Streaming tar shard |

## Configuration

All config comes from `.env` via `starlette.config.Config`:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///hawk_scope.db` | Database connection string |
| `BATCH_SIZE` | `10000` | Objects per shard |
| `FETCH_WINDOW` | `64` | Concurrent range-request fetches |
| `DEBUG` | `false` | Enable debug mode |

`.env` is gitignored.

## Architecture

```
cli.py          → CLI entry (typer). Commands: wids, shard, serve
web.py          → Starlette app with 3 routes: /, /{scope}.json, /{scope}-{shard}.tar
slicer.py       → Core logic: generate WIDS descriptors, stream shard tars
db_aiosqlite.py → Active DB layer (aiosqlite, raw SQL)
db_sqlalchemy.py → Untested alternative (SQLAlchemy ORM)
db_sqlmodel.py   → Untested alternative (SQLModel)
settings.py      → Env-backed config
```

**Database schema** (4 tables: `shard`, `object`, `scope`, `scopelist`) — defined as raw SQL in `db_aiosqlite.py`.

## License

SPDX-License-Identifier: GPL-2.0-only

Copyright 2026 Carnegie Mellon University

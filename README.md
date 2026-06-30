# Hawk Scope

Server that slices subsets out of a larger webdataset collection.

## Overview

hawk-scope indexes webdataset shards into a SQLite database and serves scoped subsets as WIDS descriptors and streaming tar archives. It supports:

- **WIDS descriptors** — JSON manifests describing shard layout and sample counts
- **Streaming webdataset shards** — Generated from on-demand range-request fetches from remote webdataset archives
- **CLI tools** — generate descriptors and shards from the command line

## Installation

Requires Python 3.10+ and the [uv](https://github.com/astral-sh/uv) package manager.

```bash
uv sync          # install dependencies from uv.lock
```

## Usage

### CLI

```bash
uv run hawk-scope <subcommand>
```

### Subcommands

| Subcommand | Description |
|---|---|
| `serve [--host HOST] [--port PORT]` | Run the web server |
| `db create` | Create a new empty scope database |
| `db index <webdataset url>` | Build an index for all objects in a webdataset |
| `scope list` | Show a list of available scopes |
| `scope import [--scope SCOPE] <file>` | Import a new scope from a file |
| `scope export <scope>` | Export a scope to stdout |
| `scope delete <scope>` | Remove a scope |
| `test wids <scope>` | Generate a WIDS JSON descriptor for a scope |
| `test shard <scope>` | Generate a shard tar archive for a scope |

### Web server

```bash
uv run hawk-scope serve
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
src/hawk_scope/
  cli.py          → CLI entry (typer). Subcommands: serve, db, scope, test
  web.py          → Starlette app with 3 routes: /, /{scope}.json, /{scope}-{shard}.tar
  slicer.py       → Core logic: generate WIDS descriptors, stream shard tars
  test.py         → CLI commands: test wids, test shard
  scope.py        → CLI commands: scope list, import, export, delete
  db.py           → DB function re-exports + index generation logic + db CLI (create, index)
  db_aiosqlite.py → Active DB layer (aiosqlite, raw SQL)
  db_sqlalchemy.py → Alternative DB layer (SQLAlchemy ORM)
  db_sqlmodel.py   → Alternative DB layer (SQLModel)
  compat.py       → Python 3.10 compatibility shim (batched)
  settings.py      → Env-backed config
```

**Database schema** (4 tables: `shard`, `object`, `scope`, `scopelist`) — defined as raw SQL in `db_aiosqlite.py`.

## License

SPDX-License-Identifier: GPL-2.0-only

Copyright 2026 Carnegie Mellon University

# Hawk Scope

Server that slices subsets out of a larger webdataset collection.

## Overview

hawk-scope indexes webdataset shards into a SQLite database and serves scoped subsets as WIDS descriptors and streaming tar archives. It supports:

- **WIDS descriptors** — JSON manifests describing shard layout and sample counts
- **Streaming webdataset shards** — Generated from on-demand range-request fetches from remote webdataset archives
- **CLI tools** — generate descriptors and shards from the command line
- **REST API** — create, list, and delete scopes over HTTP

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

Serves on `0.0.0.0:5000` by default.

### REST API

The following endpoints are available:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | HTML animation page |
| `GET` | `/{scope}.json` | WIDS descriptor JSON |
| `GET` | `/{scope}-{shard}.tar` | Streaming tar shard |
| `GET` | `/{scope}.scope` | List object keys in scope (one per line) |
| `POST` | `/{scope}.scope` | Create a new scope (body: one key per line) |
| `PUT` | `/{scope}.scope` | Same as POST |
| `DELETE` | `/{scope}.scope` | Delete a scope |

All `POST`, `PUT`, and `DELETE` endpoints require an API key via the `X-API-Key` header. If no `API_KEY` is configured, a temporary key is generated and printed to stdout on startup.

### Creating a scope via HTTP

Send a plaintext body with one object key per line:

```bash
curl -X POST http://localhost:5000/my-scope.scope \
  -H "X-API-Key: your-key" \
  --data-binary @keys.txt
```

### Deleting a scope via HTTP

```bash
curl -X DELETE http://localhost:5000/my-scope.scope \
  -H "X-API-Key: your-key"
```

## Configuration

All config comes from `.env` via `starlette.config.Config`:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///hawk_scope.db` | Database connection string |
| `BATCH_SIZE` | `10000` | Objects per shard |
| `FETCH_WINDOW` | `64` | Concurrent range-request fetches |
| `DEBUG` | `false` | Enable debug mode |
| `API_KEY` | auto-generated | API key for authenticated endpoints |

`.env` is gitignored.

## License

SPDX-License-Identifier: GPL-2.0-only

Copyright 2026 Carnegie Mellon University

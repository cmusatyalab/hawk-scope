# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from typing import AsyncIterator

import aiosqlite

from . import settings


SCOPEDB_SCHEMA = """\
BEGIN;
CREATE TABLE IF NOT EXISTS shard(
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS object(
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE,
    shard_id INTEGER NOT NULL,
    offset INTEGER,
    end INTEGER,
    FOREIGN KEY (shard_id) REFERENCES shard(id)
);
CREATE TABLE IF NOT EXISTS scope(
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS scopelist(
    scope_id INTEGER,
    object_id INTEGER,
    PRIMARY KEY (scope_id, object_id),
    FOREIGN KEY (scope_id) REFERENCES scope(id),
    FOREIGN KEY (object_id) REFERENCES object(id)
);
COMMIT;
"""

assert settings.DATABASE_URL.startswith("sqlite+aiosqlite:///")
SCOPEDB = settings.DATABASE_URL.removeprefix("sqlite+aiosqlite:///")


async def create_scope_db() -> None:
    async with aiosqlite.connect(SCOPEDB) as con:
        await con.executescript(SCOPEDB_SCHEMA)


async def count_items_in_scope(scope: str) -> int:
    async with aiosqlite.connect(SCOPEDB) as con:
        async with con.execute(
            "SELECT COUNT(*) FROM scopelist "
            "JOIN scope ON scope.id = scopelist.scope_id "
            "WHERE scope.name = ?",
            (scope,),
        ) as cur:
            result = await cur.fetchone()
            return result[0]


async def get_items_in_scope(scope: str, shard: int) -> AsyncIterator[tuple[str, int, int]]:
    limit = settings.BATCH_SIZE
    offset = shard * settings.BATCH_SIZE

    async with aiosqlite.connect(SCOPEDB) as con:
        async with con.execute(
            "SELECT shard.url, object.offset, object.end FROM object "
            "JOIN shard ON object.shard_id = shard.id "
            "JOIN scopelist ON object.id = scopelist.object_id "
            "JOIN scope ON scope.id = scopelist.scope_id "
            "WHERE scope.name = ? LIMIT ? OFFSET ?",
            (scope, limit, offset),
        ) as cur:
            async for row in cur:
                yield row[0], row[1], row[2]

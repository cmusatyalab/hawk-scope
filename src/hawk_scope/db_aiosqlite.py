# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

import aiosqlite
import typer

from . import settings

SCOPEDB_SCHEMA = """\
BEGIN;
CREATE TABLE shard (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE
);
CREATE TABLE object (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE,
    shard_id INTEGER NOT NULL,
    offset INTEGER,
    end INTEGER,
    FOREIGN KEY (shard_id) REFERENCES shard(id) ON DELETE CASCADE
);
CREATE TABLE scope (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);
CREATE TABLE scopelist (
    scope_id INTEGER,
    object_id INTEGER,
    PRIMARY KEY (scope_id, object_id),
    FOREIGN KEY (scope_id) REFERENCES scope(id) ON DELETE CASCADE,
    FOREIGN KEY (object_id) REFERENCES object(id) ON DELETE RESTRICT
);
COMMIT;
"""

assert settings.DATABASE_URL.startswith("sqlite+aiosqlite:///")
SCOPEDB = settings.DATABASE_URL.removeprefix("sqlite+aiosqlite:///")


async def create_scope_db() -> None:
    async with aiosqlite.connect(SCOPEDB) as con:
        await con.executescript(SCOPEDB_SCHEMA)


async def build_shard_index(shard: str, items: Iterable[tuple[str, int, int]]) -> None:
    async with aiosqlite.connect(SCOPEDB) as con:
        result = await con.execute("INSERT INTO shard (url) VALUES (?)", (shard,))
        shard_id = result.lastrowid
        await con.executemany(
            "INSERT INTO object (key, shard_id, offset, end) VALUES (?, ?, ?, ?)",
            [(key, shard_id, off, end) for key, off, end in items]
        )


async def list_scopes() -> AsyncIterator[tuple[str, int]]:
    async with aiosqlite.connect(SCOPEDB) as con:
        result = await con.execute(
            "SELECT scope.name, COUNT(scopelist.object_id) FROM scope "
            "LEFT JOIN scopelist ON scope.id = scopelist.scope_id "
            "GROUP BY scopelist.scope_id"
        )
        async for scope, count in result:
            yield scope, count


async def import_scope(scope: str, items: Iterable[str]) -> None:
    async with aiosqlite.connect(SCOPEDB) as con:
        try:
            result = await con.execute("INSERT INTO scope (name) VALUES (?)", (scope,))
            scope_id = result.lastrowid
        except aiosqlite.IntegrityError as err:
            msg = f"Import error: \"{scope}\" scope already exists in database."
            raise typer.Exit(msg) from err

        try:
            await con.execute("CREATE TEMP TABLE tmp_scope (key TEXT UNIQUE)")
            await con.executemany(
                "INSERT INTO tmp_scope VALUES (?)",
                [(key,) for key in items]
            )
        except aiosqlite.IntegrityError as err:
            msg = "Import error: Duplicated object key in scope."
            raise typer.Exit(msg) from err

        try:
            await con.execute(
                "INSERT INTO scopelist "
                "SELECT ?, object.id FROM tmp_scope "
                "LEFT JOIN object on tmp_scope.key = object.key ",
                (scope_id,)
            )
            await con.execute("DROP TABLE tmp_scope")
        except aiosqlite.IntegrityError as err:
            msg = "Unknown object in scope"
            raise typer.Exit(msg) from err

        await con.commit()


async def export_scope(scope: str) -> AsyncIterator[str]:
    async with (
        aiosqlite.connect(SCOPEDB) as con,
        con.execute(
            "SELECT object.key FROM object "
            "JOIN scopelist ON object.id = scopelist.object_id "
            "JOIN scope ON scope.id = scopelist.scope_id "
            "WHERE scope.name = ?",
            (scope,),
        ) as cur,
    ):
        async for key, in cur:
            yield key


async def delete_scope(scope: str) -> None:
    async with aiosqlite.connect(SCOPEDB) as con:
        cur = await con.execute(
            "SELECT scope.id FROM scope WHERE scope.name = ?",
            (scope,)
        )
        result = await cur.fetchone()
        if result is None:
            msg = f"Scope \"{scope}\" not found."
            raise typer.Exit(msg)

        scope_id = result[0]
        await con.execute("DELETE FROM scope WHERE id = ?", (scope_id,))
        await con.execute("DELETE FROM scopelist WHERE scope_id = ?", (scope_id,))
        await con.commit()


async def count_items_in_scope(scope: str) -> int:
    async with aiosqlite.connect(SCOPEDB) as con:
        cur = await con.execute(
            "SELECT COUNT(*) FROM scopelist "
            "JOIN scope ON scope.id = scopelist.scope_id "
            "WHERE scope.name = ?",
            (scope,),
        )
        result = await cur.fetchone()
        return result[0]


async def get_items_in_scope(
    scope: str, shard: int
) -> AsyncIterator[tuple[str, int, int]]:
    limit = settings.BATCH_SIZE
    offset = shard * settings.BATCH_SIZE

    async with aiosqlite.connect(SCOPEDB) as con:
        cur = await con.execute(
            "SELECT shard.url, object.offset, object.end FROM object "
            "JOIN shard ON object.shard_id = shard.id "
            "JOIN scopelist ON object.id = scopelist.object_id "
            "JOIN scope ON scope.id = scopelist.scope_id "
            "WHERE scope.name = ? LIMIT ? OFFSET ?",
            (scope, limit, offset),
        )
        async for row in cur:
            yield row[0], row[1], row[2]

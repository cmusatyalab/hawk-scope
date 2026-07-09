# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from hawk_scope.db import (
    Object,
    Shard,
    build_shard_index,
    export_scope,
    import_scope,
)


async def test_create_scope_db_creates_tables(engine: Any) -> None:
    """Verify that create_scope_db creates all required tables."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = {row[0] for row in result}
        assert "shard" in tables
        assert "object" in tables
        assert "scope" in tables
        assert "scopelist" in tables


async def test_build_shard_index_indexes_objects(engine: Any) -> None:
    """Verify that build_shard_index correctly stores object metadata."""
    items = [
        ("alpha", 0, 100),
        ("beta", 100, 250),
    ]
    await build_shard_index("http://example.com/shard.tar", items)

    async with engine.begin() as conn:
        shard_result = await conn.execute(select(Shard.url))
        shard_urls = [row[0] for row in shard_result]
        assert len(shard_urls) == 1
        assert shard_urls[0] == "http://example.com/shard.tar"

        obj_result = await conn.execute(
            select(Object.key, Object.offset, Object.end).order_by(Object.key)
        )
        object_data = [(row[0], row[1], row[2]) for row in obj_result]
        assert len(object_data) == 2
        assert object_data[0] == ("alpha", 0, 100)
        assert object_data[1] == ("beta", 100, 250)


async def test_import_scope_creates_scope(engine: Any) -> None:
    """Verify import_scope creates a scope and links objects."""
    await build_shard_index(
        "http://example.com/shard.tar",
        [
            ("alpha", 0, 100),
            ("beta", 100, 250),
        ],
    )

    async def items():
        yield "alpha"
        yield "beta"

    count = await import_scope("my-scope", items())

    assert count == 2

    keys = [key async for key in export_scope("my-scope")]
    assert set(keys) == {"alpha", "beta"}


async def test_import_scope_duplicate_raises(engine: Any) -> None:
    """Verify importing the same scope twice raises FileExistsError."""

    async def items():
        yield "alpha"

    await import_scope("dup-scope", items())

    with pytest.raises(FileExistsError):

        async def items2():
            yield "beta"

        await import_scope("dup-scope", items2())


async def test_import_scope_with_nonexistent_objects(engine: Any) -> None:
    """Verify importing a scope referencing objects not in any shard skips them."""
    await build_shard_index(
        "http://example.com/shard.tar",
        [
            ("alpha", 0, 100),
        ],
    )

    async def items():
        yield "alpha"
        yield "nonexistent"

    count = await import_scope("partial-scope", items())

    assert count == 1
    keys = [key async for key in export_scope("partial-scope")]
    assert keys == ["alpha"]

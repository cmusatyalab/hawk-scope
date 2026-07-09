# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from hawk_scope.db import (
    Object,
    Shard,
    build_shard_index,
    delete_scope,
    export_scope,
    get_items_in_scope,
    import_scope,
    list_scopes,
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


async def test_list_scopes_returns_scopes_and_counts(
    db: Any, engine: Any, scope_data: Any
) -> None:
    """Verify list_scopes returns scope names with correct item counts."""
    result = [(name, count) async for name, count in list_scopes()]

    names = [name for name, _ in result]
    assert "test-scope" in names
    assert "empty-scope" in names

    counts = {name: count for name, count in result}
    assert counts["test-scope"] == 6
    assert counts["empty-scope"] == 0


async def test_delete_scope_removes_scope(
    db: Any, engine: Any, scope_data: Any
) -> None:
    """Verify delete_scope removes the scope and its links."""
    await delete_scope("test-scope")

    result = [(name, count) async for name, count in list_scopes()]
    names = [name for name, _ in result]
    assert "test-scope" not in names
    assert "empty-scope" in names


async def test_delete_scope_missing_raises(db: Any, engine: Any) -> None:
    """Verify delete_scope raises NoResultFound for non-existent scope."""
    with pytest.raises(NoResultFound):
        await delete_scope("no-such-scope")


async def test_get_items_in_scope_returns_items(
    db: Any, engine: Any, scope_data: Any
) -> None:
    """Verify get_items_in_scope returns correct URL/offset/end tuples."""
    import hawk_scope.settings

    original = hawk_scope.settings.BATCH_SIZE
    try:
        hawk_scope.settings.BATCH_SIZE = 3

        items = [
            (url, off, end)
            async for url, off, end in get_items_in_scope("test-scope", 0)
        ]

        assert len(items) == 3
        urls = [url for url, _, _ in items]
        assert "http://example.com/shard1.tar" in urls
    finally:
        hawk_scope.settings.BATCH_SIZE = original


async def test_get_items_in_scope_pagination(
    db: Any, engine: Any, scope_data: Any
) -> None:
    """Verify get_items_in_scope respects BATCH_SIZE for pagination."""
    import hawk_scope.settings

    original = hawk_scope.settings.BATCH_SIZE
    try:
        hawk_scope.settings.BATCH_SIZE = 3

        shard0 = [
            (url, off, end)
            async for url, off, end in get_items_in_scope("test-scope", 0)
        ]
        shard1 = [
            (url, off, end)
            async for url, off, end in get_items_in_scope("test-scope", 1)
        ]

        assert len(shard0) == 3
        assert len(shard1) == 3
    finally:
        hawk_scope.settings.BATCH_SIZE = original

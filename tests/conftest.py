# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from hawk_scope.db import SQLTable


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    """Provide a temp file path for the test database."""
    return tmp_path / "test.db"


@pytest_asyncio.fixture
async def engine(db_file: Path) -> AsyncIterator[Any]:
    """Create an async SQLAlchemy engine pointing to a temp file DB."""
    import hawk_scope.db
    import hawk_scope.settings

    db_url = f"sqlite+aiosqlite:///{db_file}"
    hawk_scope.settings.DATABASE_URL = db_url

    eng = create_async_engine(db_url, echo=False)
    hawk_scope.db.engine = eng
    async with eng.begin() as conn:
        await conn.run_sync(SQLTable.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def db(engine: Any) -> Any:
    """Alias for engine, used by some tests."""
    return engine


@pytest_asyncio.fixture
async def scope_data(engine: Any) -> None:
    """Populate the DB with known indexed shards and a scope.

    Creates two shard URLs, each containing 3 objects with known offsets.
    Creates a scope 'test-scope' referencing all 6 objects.
    Creates a scope 'empty-scope' with no objects.
    """
    from hawk_scope.db import build_shard_index, import_scope

    # Shard 1: objects in shard1.tar
    shard1_items = [
        ("obj_a", 0, 100),
        ("obj_b", 100, 250),
        ("obj_c", 250, 400),
    ]
    await build_shard_index("http://example.com/shard1.tar", shard1_items)

    # Shard 2: objects in shard2.tar
    shard2_items = [
        ("obj_d", 0, 50),
        ("obj_e", 50, 150),
        ("obj_f", 150, 300),
    ]
    await build_shard_index("http://example.com/shard2.tar", shard2_items)

    # Create test-scope referencing all 6 objects
    items = [
        "obj_a",
        "obj_b",
        "obj_c",
        "obj_d",
        "obj_e",
        "obj_f",
    ]

    async def item_iter():
        for item in items:
            yield item

    await import_scope("test-scope", item_iter())

    # Create empty-scope with no objects
    async def empty_iter():
        if False:
            yield

    await import_scope("empty-scope", empty_iter())


@pytest.fixture
def mock_http() -> Any:
    """Factory fixture that patches niquests.AsyncSession.get.

    Usage:
        mock = mock_http({"http://example.com/file.tar": tar_bytes})
        # mock.get returns AsyncMock with appropriate content for Range requests
    """

    def _factory(url_responses: dict[str, bytes]) -> MagicMock:
        async def _get(url: str, headers: dict | None = None, **kwargs: Any) -> Any:
            if url not in url_responses:
                raise AssertionError(f"Unexpected URL: {url}")
            content = url_responses[url]
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            if headers and "Range" in headers:
                range_header = headers["Range"]
                range_match = range_header.replace("bytes=", "").split("-")
                start = int(range_match[0])
                end = int(range_match[1]) if range_match[1] else len(content) - 1
                mock_resp.content = content[start : end + 1]
            else:
                mock_resp.content = content
            return mock_resp

        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=_get)
        return mock_session

    return _factory

# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hawk_scope.slicer import generate_shard, generate_wids_descriptor


async def test_generate_wids_descriptor_basic(scope_data: None, engine: Any) -> None:
    """Verify WIDS descriptor structure for a scope with items."""
    descriptor = await generate_wids_descriptor("test-scope", "http://localhost:8000/")

    assert descriptor["wids_version"] == 1
    assert descriptor["name"] == "test-scope"
    assert descriptor["base"] == "http://localhost:8000/"
    assert "description" in descriptor
    assert "shardlist" in descriptor

    # 6 items / BATCH_SIZE(10000) = 0 full shards, 1 partial shard with 6 items
    assert len(descriptor["shardlist"]) == 1
    assert descriptor["shardlist"][0]["nsamples"] == 6


async def test_generate_wids_descriptor_multiple_shards(
    scope_data: None, engine: Any
) -> None:
    """Verify WIDS descriptor with multiple shards and remainder."""
    import hawk_scope.settings

    original = hawk_scope.settings.BATCH_SIZE
    try:
        hawk_scope.settings.BATCH_SIZE = 2

        descriptor = await generate_wids_descriptor("test-scope", "http://example.com/")

        # 6 items / 2 per shard = 3 shards, no remainder
        assert len(descriptor["shardlist"]) == 3
        for shard in descriptor["shardlist"]:
            assert shard["nsamples"] == 2
    finally:
        hawk_scope.settings.BATCH_SIZE = original


async def test_generate_wids_descriptor_remainder(
    scope_data: None, engine: Any
) -> None:
    """Verify WIDS descriptor handles last shard with remainder correctly."""
    import hawk_scope.settings

    original = hawk_scope.settings.BATCH_SIZE
    try:
        hawk_scope.settings.BATCH_SIZE = 4

        descriptor = await generate_wids_descriptor("test-scope", "http://example.com/")

        # 6 items / 4 per shard = 1 full shard (4) + 1 partial (2)
        assert len(descriptor["shardlist"]) == 2
        assert descriptor["shardlist"][0]["nsamples"] == 4
        assert descriptor["shardlist"][1]["nsamples"] == 2
    finally:
        hawk_scope.settings.BATCH_SIZE = original


async def test_generate_wids_descriptor_empty_scope(
    scope_data: None, engine: Any
) -> None:
    """Verify WIDS descriptor for an empty scope has no shards."""
    descriptor = await generate_wids_descriptor("empty-scope", "http://localhost:8000/")

    assert len(descriptor["shardlist"]) == 0


async def test_generate_shard_streams_content(
    mock_http: Any, scope_data: None, engine: Any
) -> None:
    """Verify generate_shard yields bytes from mocked HTTP range requests."""
    fake_tar = b"\x00" * 500  # fake tar content
    mock = mock_http({"http://example.com/shard1.tar": fake_tar})

    async def items() -> AsyncIterator[tuple[str, int, int]]:
        yield ("http://example.com/shard1.tar", 0, 99)
        yield ("http://example.com/shard1.tar", 100, 199)

    with patch("hawk_scope.slicer.niquests", MagicMock()) as mock_niquests:
        mock_niquests.AsyncSession.return_value = mock

        result = b"".join([chunk async for chunk in generate_shard(items())])

    assert result == fake_tar[:100] + fake_tar[100:200]


async def test_generate_shard_empty_iterable(mock_http: Any) -> None:
    """Verify generate_shard handles empty item stream."""

    async def items() -> AsyncIterator[tuple[str, int, int]]:
        if False:
            yield

    with patch("hawk_scope.slicer.niquests", MagicMock()) as mock_niquests:
        mock_session = MagicMock()
        mock_session.get = AsyncMock()
        mock_niquests.AsyncSession.return_value = mock_session

        result = [chunk async for chunk in generate_shard(items())]

    assert result == []

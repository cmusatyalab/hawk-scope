# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterable, AsyncIterator

from hawk_scope.util import async_reader, batched, chunks_to_lines


async def _async_iter(items: list[str]) -> AsyncIterable[str]:
    for item in items:
        yield item


async def test_batched_splits_correctly() -> None:
    items = ["a", "b", "c", "d", "e"]

    result = [batch async for batch in batched(_async_iter(items), 2)]

    assert result == [["a", "b"], ["c", "d"], ["e"]]


async def test_batched_exact_division() -> None:
    items = ["a", "b", "c", "d"]

    result = [batch async for batch in batched(_async_iter(items), 2)]

    assert result == [["a", "b"], ["c", "d"]]


async def test_batched_empty() -> None:
    result = [batch async for batch in batched(_async_iter([]), 3)]

    assert result == []


async def test_batched_single_item() -> None:
    result = [batch async for batch in batched(_async_iter(["only"]), 3)]

    assert result == [["only"]]


async def test_batched_larger_than_input() -> None:
    result = [batch async for batch in batched(_async_iter(["a", "b"]), 10)]

    assert result == [["a", "b"]]


async def test_async_reader_returns_lines() -> None:
    content = "line1\nline2\nline3\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as f:
        f.write(content)
        f.flush()

        result = [line async for line in async_reader(f.name)]

    assert result == ["line1", "line2", "line3"]


async def test_async_reader_strips_trailing_newlines() -> None:
    content = "line1\nline2\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as f:
        f.write(content)
        f.flush()

        result = [line async for line in async_reader(f.name)]

    assert result == ["line1", "line2"]


async def test_async_reader_empty_file() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as f:
        result = [line async for line in async_reader(f.name)]

    assert result == []


async def test_chunks_to_lines_assembles_chunks() -> None:
    async def stream() -> AsyncIterator[bytes]:
        yield b"hello"
        yield b"world"
        yield b"!"

    result = [line async for line in chunks_to_lines(stream())]

    assert result == ["helloworld!"]


async def test_chunks_to_lines_splits_on_newlines() -> None:
    async def stream() -> AsyncIterator[bytes]:
        yield b"line1\n"
        yield b"line2\n"
        yield b"line3"

    result = [line async for line in chunks_to_lines(stream())]

    assert result == ["line1", "line2", "line3"]


async def test_chunks_to_lines_handles_partial_newlines() -> None:
    async def stream() -> AsyncIterator[bytes]:
        yield b"hel"
        yield b"lo\nwor"
        yield b"ld"

    result = [line async for line in chunks_to_lines(stream())]

    assert result == ["hello", "world"]


async def test_chunks_to_lines_skips_empty_lines() -> None:
    async def stream() -> AsyncIterator[bytes]:
        yield b"line1\n\nline2\n"

    result = [line async for line in chunks_to_lines(stream())]

    assert result == ["line1", "line2"]

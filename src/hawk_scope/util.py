# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable, Iterator
from pathlib import Path
from typing import TypeVar

import anyio

V = TypeVar("V")


# I don't want the python3.12 dependency just yet, here is a
# 'itertools.batched' implementation.
# Probably not as efficient, but it should work
def batched(iterable: Iterable[V], size: int) -> Iterator[list[V]]:
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


async def async_reader(path: Path | str) -> AsyncIterator[str]:
    """async reader that returns the lines in the file."""
    async with await anyio.open_file(path) as f:
        async for line in f:
            yield line.strip()


async def chunks_to_lines(stream: AsyncIterable[bytes]) -> AsyncIterator[str]:
    """Helper to convert a stream of binary chunks to lines"""
    body = ""
    async for chunk in stream:
        body += chunk.decode()
        while "\n" in body:
            line, body = body.split("\n", 1)
            line = line.strip()
            if line:
                yield line
        # handle the case when there are no newlines in the input
        if len(body) > 4096:
            msg = "Input line too long"
            raise BufferError(msg)
    line = body.strip()
    if line:
        yield line

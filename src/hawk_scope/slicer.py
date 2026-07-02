# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

import niquests

from . import settings
from .db import count_items_in_scope


async def generate_wids_descriptor(scope: str, base_url: str) -> dict[str, Any]:
    nitems = await count_items_in_scope(scope)

    shard_name = f"{scope}-%06d.tar"
    nshards = nitems // settings.BATCH_SIZE
    last_nitems = nitems % settings.BATCH_SIZE

    # build the WIDS descriptor
    shardlist = [
        {"url": shard_name % index, "nsamples": settings.BATCH_SIZE}
        for index in range(nshards)
    ]
    if last_nitems:
        shardlist.append(
            {
                "url": shard_name % nshards,
                "nsamples": last_nitems,
            }
        )

    wids_descriptor = {
        "wids_version": 1,
        "name": scope,
        "description": "",
        "base": base_url,
        "shardlist": shardlist,
    }
    return wids_descriptor


async def get_object(
    session: niquests.AsyncSession, url: str, offset: int, end: int
) -> bytes:
    # shard = url.rsplit("/", 1)[1]
    # url = f"http://blue1.satyalab/yfcc100m/{shard}"
    headers = {"Range": f"bytes={offset}-{end}"}
    response = await session.get(url, headers=headers)
    response.raise_for_status()
    assert response.content is not None
    return response.content


async def generate_shard(
    items: AsyncIterator[tuple[str, int, int]],
) -> AsyncIterator[bytes]:
    session = niquests.AsyncSession()

    # sliding window for url range-request fetches
    tasks = []
    for _ in range(settings.FETCH_WINDOW):
        try:
            url, start, end = await anext(items)
            tasks.append(asyncio.create_task(get_object(session, url, start, end)))
        except StopAsyncIteration:
            break

    while tasks:
        yield await tasks.pop(0)
        with suppress(StopAsyncIteration):
            url, start, end = await anext(items)
            tasks.append(asyncio.create_task(get_object(session, url, start, end)))

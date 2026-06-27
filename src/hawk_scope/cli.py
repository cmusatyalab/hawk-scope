# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import asyncio
import json

import typer
from rich import print
from tqdm.asyncio import tqdm

from .slicer import generate_wids_descriptor, get_items_in_scope, generate_shard


app = typer.Typer(no_args_is_help=True)


async def create_wids(scope: str) -> None:
    base_url = "http://localhost:8000/"
    wids_descriptor = await generate_wids_descriptor(scope, base_url)
    print(json.dumps(wids_descriptor, indent=2))


@app.command()
def test_wids(scope: str) -> None:
    """generate a 'WIDS' json descriptor for the scope.

    this would normally be the response to URL_BASE/<scope>.json
    """
    asyncio.run(create_wids(scope))


async def create_shard(scope: str, shard: int) -> None:
    items = get_items_in_scope(scope, shard)
    items = tqdm(items)

    with open(f"{scope}-{shard:06d}.tar", "wb") as f:
        async for obj in generate_shard(items):
            f.write(obj)


@app.command()
def test_shard(scope: str, shard: int = 0) -> None:
    """generate a shard tar archive for the scope.

    this would normally be the response to URL_BASE/<scope>/webdataset-{shard:06d}.tar
    """
    asyncio.run(create_shard(scope, shard))


@app.command()
def serve(host: str = "0.0.0.0", port: int = 5000) -> None:
    """run a webserver instance"""
    import uvicorn

    uvicorn.run("hawk_scope.web:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()

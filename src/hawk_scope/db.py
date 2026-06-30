# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import asyncio
import tarfile
from collections.abc import Iterator

import niquests
import typer
from braceexpand import braceexpand
from tqdm import tqdm

from .db_aiosqlite import (
    build_shard_index,
    count_items_in_scope,
    create_scope_db,
    delete_scope,
    export_scope,
    get_items_in_scope,
    import_scope,
    list_scopes,
)

__all__ = [
    "build_shard_index",
    "list_scopes",
    "import_scope",
    "export_scope",
    "delete_scope",
    "create_scope_db",
    "count_items_in_scope",
    "get_items_in_scope",
]


def generate_shard_index(url: str) -> Iterator[tuple[str, int, int]]:
    with niquests.get(url, stream=True) as response:
        response.raise_for_status()

        obj_key: str | None = None
        obj_off = obj_end = 0
        with tarfile.open(fileobj=response.raw, mode="r|") as shard:
            for entry in shard:
                cur_key = entry.name.rsplit(".", 1)[0]
                if obj_key != cur_key:
                    if obj_end:
                        yield obj_key, obj_off, obj_end
                    obj_key = cur_key
                    obj_off = entry.offset
                # move end to include additional entries with the same key
                obj_end = shard.offset - 1
                # print("#", entry.name, entry.offset, shard.offset)
            # yield the final object
            if obj_end:
                yield obj_key, obj_off, obj_end


app = typer.Typer(help="Manipulate the scope database.", no_args_is_help=True)


@app.command()
def create() -> None:
    """Create a new empty database."""
    asyncio.run(create_scope_db())


@app.command()
def index(descriptor: str) -> None:
    """Build an index for all objects in a webdataset."""
    shards = list(braceexpand(descriptor))
    for shard in tqdm(shards, unit=" shards"):
        items = tqdm(generate_shard_index(shard), unit=" objects")
        asyncio.run(build_shard_index(shard, items))


if __name__ == "__main__":
    app()

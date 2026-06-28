#!/usr/bin/env -S uv run --script
#
# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only
#
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "braceexpand",
#   "niquests",
#   "tqdm",
# ]
# ///

import sqlite3
import tarfile
from collections.abc import Iterator
from typing import NamedTuple

import niquests
from braceexpand import braceexpand
from tqdm import tqdm

SCHEMA = """\
BEGIN;
CREATE TABLE IF NOT EXISTS shard(
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS object(
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE,
    shard INTEGER NOT NULL,
    offset INTEGER,
    end INTEGER,
    FOREIGN KEY(shard) REFERENCES shard(id)
);
CREATE TABLE IF NOT EXISTS scope(
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS scopelist(
    scope INTEGER,
    object INTEGER,
    UNIQUE (scope, object),
    FOREIGN KEY(scope) REFERENCES scope(id),
    FOREIGN KEY(object) REFERENCES object(id)
);
COMMIT;
"""


class Object(NamedTuple):
    key: str = ""
    off: int = 0
    end: int = 0


def index_shard(url: str) -> Iterator[Object]:
    with niquests.get(url, stream=True) as response:
        response.raise_for_status()

        obj_key: str | None = None
        obj_off = obj_end = 0
        with tarfile.open(fileobj=response.raw, mode="r|") as shard:
            for entry in shard:
                cur_key = entry.name.rsplit(".", 1)[0]
                if obj_key != cur_key:
                    if obj_end:
                        yield Object(obj_key, obj_off, obj_end)
                    obj_key = cur_key
                    obj_off = entry.offset
                # move end to include additional entries with the same key
                obj_end = shard.offset - 1
                # print("#", entry.name, entry.offset, shard.offset)
            # yield the final object
            if obj_end:
                yield Object(obj_key, obj_off, obj_end)


def index_dataset(dataset: str) -> None:
    con = sqlite3.connect("index2.db")
    con.executescript(SCHEMA)

    shards = list(braceexpand(dataset))
    for shard in tqdm(shards, unit=" shards", position=1):
        with con:
            r = con.execute("INSERT INTO shard(url) VALUES(?)", (shard,))
            shard_id = r.lastrowid

            for obj in tqdm(index_shard(shard), unit=" objects", position=0):
                con.execute(
                    "INSERT INTO object(key, shard, offset, end) VALUES (?, ?, ?, ?)",
                    (obj.key, shard_id, obj.off, obj.end),
                )


WDS = "https://storage.cmusatyalab.org/yfcc100m/yfcc100m-{000000..000001}.tar"
WDS = "https://storage.cmusatyalab.org/yfcc100m/yfcc100m-{000000..000402}.tar"

if __name__ == "__main__":
    # import argparse
    # parser = argparse.ArgumentParser()
    # parser.add_argument("dataset")
    # args = parser.parse_args()
    # index_dataset(args.dataset)
    index_dataset(WDS)

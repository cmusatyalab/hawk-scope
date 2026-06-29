# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from collections.abc import Iterable, Iterator
from typing import TypeVar

# I don't want the python3.12 dependency just yet, here is a
# 'itertools.batched' implementation.
# Probably not as efficient, but it should work
V = TypeVar("V")


def batched(iterable: Iterable[V], size: int) -> Iterator[list[V]]:
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch

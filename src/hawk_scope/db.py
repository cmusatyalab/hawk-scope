# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import asyncio

import typer

from .db_aiosqlite import count_items_in_scope, create_scope_db, get_items_in_scope

__all__ = [
    "create_scope_db",
    "count_items_in_scope",
    "get_items_in_scope",
]

app = typer.Typer()


@app.command()
def create():
    asyncio.run(create_scope_db())


if __name__ == "__main__":
    app()

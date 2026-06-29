# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from tqdm import tqdm

from .db import delete_scope, export_scope, import_scope, list_scopes

app = typer.Typer(help="Add/remove scopes.", no_args_is_help=True)


@app.command()
def list() -> None:
    """Show a list of available scopes."""
    async def list_() -> None:
        table = Table()
        table.add_column("Scope", no_wrap=True)
        table.add_column("# Items")

        async for scope, count in list_scopes():
            table.add_row(scope, str(count))

        console = Console()
        console.print(table)

    asyncio.run(list_())


@app.command("import")
def import_(scopefile: Path, scope: str | None = None) -> None:
    """Import a new scope from a file."""
    if scope is None:
        scope = scopefile.stem

    if not scopefile.is_file():
        raise typer.Exit(f"Scope {scopefile} does not exist")

    items = (line.strip() for line in scopefile.open())
    asyncio.run(import_scope(scope, items))

    print(f"Scope from {scopefile} added as \"{scope}\".")


@app.command()
def export(scope: str) -> None:
    """Export a scope to stdout."""
    async def export_to_stdout(scope: str) -> None:
        async for key in export_scope(scope):
            print(key)

    asyncio.run(export_to_stdout(scope))


@app.command()
def delete(scope: str) -> None:
    """Remove a scope."""
    asyncio.run(delete_scope(scope))


if __name__ == "__main__":
    app()

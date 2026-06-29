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

app = typer.Typer(help="Add/remove scopes.")


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


@app.command()
def add(scopefile: Path, scope: str | None = None) -> None:
    """Add a new scope."""
    if scope is None:
        scope = scopefile.stem

    if not scopefile.is_file():
        raise typer.Exit(f"Scope {scopefile} does not exist")

    items = (line.strip() for line in scopefile.open())
    asyncio.run(import_scope(scope, items))

    print(f"Scope from {scopefile} added as \"{scope}\".")


@app.command()
def export(scope: str) -> None:
    """Export a scope to a text file."""
    async def export_to_file(scope: str) -> None:
        out = Path(scope).with_suffix(".scope")
        if not out.exists():
            with out.open("w") as out:
                async for key in export_scope(scope):
                    out.write(f"{key}\n")
        else:
            msg = f"{out} already exists."
            raise typer.Exit(msg)

    asyncio.run(export_to_file(scope))


@app.command()
def delete(scope: str) -> None:
    """Remove a scope."""
    asyncio.run(delete_scope(scope))


if __name__ == "__main__":
    app()

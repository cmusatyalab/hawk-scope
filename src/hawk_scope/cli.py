# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import typer

from .db import app as db_app
from .test import app as test_app
from .web import cli as web_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(web_app)
app.add_typer(db_app, name="db")
app.add_typer(test_app, name="test")

if __name__ == "__main__":
    app()

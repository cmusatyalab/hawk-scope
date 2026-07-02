# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import secrets

from starlette.config import Config
from starlette.datastructures import Secret

config = Config(".env")

DEBUG: bool = config("DEBUG", cast=bool, default=False)

DATABASE_URL: str = config("DATABASE_URL", default="sqlite+aiosqlite:///hawk_scope.db")

BATCH_SIZE: int = config("BATCH_SIZE", cast=int, default=10_000)
FETCH_WINDOW: int = config("FETCH_WINDOW", cast=int, default=64)

SESSION_KEY = Secret(secrets.token_urlsafe())
API_KEY: Secret = config("API_KEY", cast=Secret, default=str(SESSION_KEY))

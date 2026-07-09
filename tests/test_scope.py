# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from typer.testing import CliRunner

from hawk_scope.scope import app as scope_app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


async def _write_keys(path: Path, keys: list[str]) -> Path:
    """Helper to write a scope keys file."""
    with open(path, "w") as f:
        for key in keys:
            f.write(key + "\n")
    return path


@pytest_asyncio.fixture
async def _setup_db(db_file: Path, engine: Any) -> Path:
    """Set up DB with test data and return the db_file path for reference."""
    from hawk_scope.db import build_shard_index, import_scope

    await build_shard_index(
        "http://example.com/shard.tar",
        [
            ("obj_a", 0, 100),
            ("obj_b", 100, 200),
        ],
    )

    async def items():
        yield "obj_a"
        yield "obj_b"

    await import_scope("test-scope", items())
    return db_file


def test_scope_list_shows_scopes(
    runner: CliRunner, db_file: Path, engine: Any, scope_data: None
) -> None:
    """Verify scope list shows available scopes with item counts."""
    import hawk_scope.settings

    hawk_scope.settings.DATABASE_URL = f"sqlite+aiosqlite:///{db_file}"

    result = runner.invoke(scope_app, ["list"])

    assert result.exit_code == 0
    assert "test-scope" in result.stdout
    assert "empty-scope" in result.stdout
    assert "6" in result.stdout
    assert "0" in result.stdout


def test_scope_import_creates_scope(
    runner: CliRunner, db_file: Path, engine: Any
) -> None:
    """Verify scope import creates a new scope from a file."""
    import hawk_scope.settings

    hawk_scope.settings.DATABASE_URL = f"sqlite+aiosqlite:///{db_file}"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as keys_file:
        keys_file.write("new_obj_1\nnew_obj_2\n")
        keys_file.flush()

        result = runner.invoke(scope_app, ["import", keys_file.name])
        file_stem = Path(keys_file.name).stem

    assert result.exit_code == 0
    assert file_stem in result.stdout
    assert "0 items" in result.stdout


def test_scope_import_custom_name(
    runner: CliRunner, db_file: Path, engine: Any
) -> None:
    """Verify scope import --scope overrides the scope name."""
    import hawk_scope.settings

    hawk_scope.settings.DATABASE_URL = f"sqlite+aiosqlite:///{db_file}"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as keys_file:
        keys_file.write("obj_x\n")
        keys_file.flush()

        result = runner.invoke(
            scope_app, ["import", "--scope", "custom-name", keys_file.name]
        )

    assert result.exit_code == 0
    assert "custom-name" in result.stdout


def test_scope_import_missing_file(runner: CliRunner) -> None:
    """Verify scope import prints error for missing file."""
    result = runner.invoke(scope_app, ["import", "/no/such/file.txt"])

    assert result.exit_code == 0
    assert "does not exist" in result.stdout


def test_scope_export_returns_keys(
    runner: CliRunner, db_file: Path, engine: Any, scope_data: None
) -> None:
    """Verify scope export outputs object keys."""
    import hawk_scope.settings

    hawk_scope.settings.DATABASE_URL = f"sqlite+aiosqlite:///{db_file}"

    result = runner.invoke(scope_app, ["export", "test-scope"])

    assert result.exit_code == 0
    assert "obj_a" in result.stdout
    assert "obj_b" in result.stdout
    assert "obj_c" in result.stdout


def test_scope_delete_removes_scope(
    runner: CliRunner, db_file: Path, engine: Any, scope_data: None
) -> None:
    """Verify scope delete removes a scope."""
    import hawk_scope.settings

    hawk_scope.settings.DATABASE_URL = f"sqlite+aiosqlite:///{db_file}"

    result = runner.invoke(scope_app, ["delete", "test-scope"])

    assert result.exit_code == 0

    list_result = runner.invoke(scope_app, ["list"])
    assert "test-scope" not in list_result.stdout

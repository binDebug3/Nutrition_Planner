"""Unit tests for scripts/migrate_logins_to_postgres.py."""

from __future__ import annotations

import argparse
import types
from pathlib import Path

from conftest import REPO_ROOT


SCRIPTS_DIR = REPO_ROOT / "scripts"


def test_default_neon_url_path_points_to_shared_secret(load_module: object) -> None:
    """Resolve the Neon secret path relative to the parent dietetics folder."""
    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_module.create_engine = lambda url: object()
    sqlalchemy_module.text = lambda sql_query: sql_query

    module = load_module(
        "test_migrate_logins_to_postgres_path",
        SCRIPTS_DIR / "migrate_logins_to_postgres.py",
        injected_modules={"sqlalchemy": sqlalchemy_module},
    )

    assert module.DEFAULT_NEON_URL_PATH.parts[-4:] == (
        "dietetics",
        "secrets",
        "passwords",
        "neon.txt",
    )


def test_main_loads_neon_url_and_uploads_users(
    load_module: object,
    monkeypatch: object,
    capsys: object,
) -> None:
    """Read the Neon URL from the configured secret path and upload users."""
    captured: dict[str, object] = {"statements": []}

    class FakeConnection:
        """Collect executed SQL statements for assertions."""

        def __enter__(self) -> "FakeConnection":
            """Enter the fake SQLAlchemy transaction context."""
            return self

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
            """Exit the fake SQLAlchemy transaction context."""
            _ = (exc_type, exc_val, exc_tb)
            return False

        def execute(
            self,
            statement: str,
            params: dict[str, str] | None = None,
        ) -> None:
            """Record executed SQL and bound parameters."""
            captured["statements"].append((statement, params))

    class FakeEngine:
        """Provide the minimal SQLAlchemy engine API used by the script."""

        def begin(self) -> FakeConnection:
            """Return a fake transaction-scoped connection."""
            return FakeConnection()

    def fake_create_engine(url: str) -> FakeEngine:
        """Capture the Neon URL used to construct the engine."""
        captured["url"] = url
        return FakeEngine()

    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_module.create_engine = fake_create_engine
    sqlalchemy_module.text = lambda sql_query: sql_query

    module = load_module(
        "test_migrate_logins_to_postgres_main",
        SCRIPTS_DIR / "migrate_logins_to_postgres.py",
        injected_modules={"sqlalchemy": sqlalchemy_module},
    )

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: argparse.Namespace(
            sqlite_db="users.db",
            neon_url_path="dietetics/secrets/passwords/neon.txt",
        ),
    )
    monkeypatch.setattr(module, "configure_logging", lambda: None)
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, encoding="utf-8": "postgresql://neon-user:secret@example/db\n",
    )
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(
        module,
        "load_local_users",
        lambda sqlite_db_path: [("alice", "hash", "2024-01-01T00:00:00Z")],
    )

    module.main()

    stdout = capsys.readouterr().out

    assert captured["url"] == "postgresql://neon-user:secret@example/db"
    assert len(captured["statements"]) == 2
    assert "CREATE TABLE IF NOT EXISTS app_logins" in captured["statements"][0][0]
    assert "INSERT INTO app_logins" in captured["statements"][1][0]
    assert captured["statements"][1][1] == {
        "username": "alice",
        "password_hash": "hash",
        "created_at": "2024-01-01T00:00:00Z",
    }
    assert "Migrated 1 users to remote login table." in stdout

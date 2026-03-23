"""Migrate local Streamlit login records from SQLite to Postgres.

Run once to bootstrap the remote login table used by production auth.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import create_engine, text


LOGGER = logging.getLogger("nutients_app.auth.migration")
REMOTE_USERS_TABLE = "app_logins"
SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_NEON_URL_PATH = SCRIPT_PATH.parents[2] / "secrets" / "passwords" / "neon.txt"


def configure_logging() -> None:
    """
    Configure console logging for migration output.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOGGER.info("Configured migration logging", extra={"event": "migration.logging"})


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed argument namespace.
    """
    LOGGER.info("Parsing migration arguments", extra={"event": "migration.args"})
    parser = argparse.ArgumentParser(
        description="Upload users from local users.db into Postgres app_logins table.",
    )
    parser.add_argument(
        "--sqlite-db",
        required=True,
        help="Path to local SQLite users database.",
    )
    parser.add_argument(
        "--neon-url-path",
        default=str(DEFAULT_NEON_URL_PATH),
        help="Path to file containing the Neon Postgres connection URL.",
    )
    return parser.parse_args()


def load_neon_url(neon_url_path: Path) -> str:
    """
    Load the Neon connection URL from a secret file.

    Args:
        neon_url_path: Path to the Neon secret file.

    Returns:
        Connection string loaded from the secret file.
    """
    LOGGER.info(
        "Loading Neon connection URL",
        extra={"event": "migration.neon.url.load", "path": str(neon_url_path)},
    )
    if not neon_url_path.exists():
        raise FileNotFoundError(f"Neon URL file not found: {neon_url_path}")

    neon_url = neon_url_path.read_text(encoding="utf-8").strip()
    if not neon_url:
        raise ValueError(f"Neon URL file is empty: {neon_url_path}")
    return neon_url


def load_local_users(sqlite_db_path: Path) -> List[Tuple[str, str, str]]:
    """
    Load users from the local SQLite credential store.

    Args:
        sqlite_db_path: Path to SQLite users database.

    Returns:
        List of tuples with username, password_hash, and created_at.
    """
    LOGGER.info(
        "Loading local users from sqlite",
        extra={"event": "migration.sqlite.load", "path": str(sqlite_db_path)},
    )
    if not sqlite_db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_db_path}")

    with sqlite3.connect(sqlite_db_path) as connection:
        rows = connection.execute(
            """
            SELECT username, password_hash, created_at
            FROM users
            ORDER BY username
            """
        ).fetchall()
    return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]


def ensure_remote_table(neon_url: str) -> None:
    """
    Ensure remote Neon login table exists.

    Args:
        neon_url: Neon Postgres connection URL.
    """
    LOGGER.info(
        "Ensuring remote login table exists",
        extra={"event": "migration.remote.table.ensure"},
    )
    engine = create_engine(neon_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {REMOTE_USERS_TABLE} (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )


def upload_users(neon_url: str, users: List[Tuple[str, str, str]]) -> int:
    """
    Upload users to remote Neon login table.

    Args:
        neon_url: Neon Postgres connection URL.
        users: User rows from local SQLite.

    Returns:
        Number of rows inserted or updated.
    """
    LOGGER.info(
        "Uploading users to remote login table",
        extra={"event": "migration.remote.upload", "count": len(users)},
    )
    if not users:
        return 0

    engine = create_engine(neon_url)
    with engine.begin() as connection:
        for username, password_hash, created_at in users:
            connection.execute(
                text(
                    f"""
                    INSERT INTO {REMOTE_USERS_TABLE} (username, password_hash, created_at)
                    VALUES (:username, :password_hash, :created_at)
                    ON CONFLICT (username)
                    DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        created_at = EXCLUDED.created_at
                    """
                ),
                {
                    "username": username,
                    "password_hash": password_hash,
                    "created_at": created_at,
                },
            )
    return len(users)


def main() -> None:
    """
    Run the local-to-Postgres login migration.
    """
    configure_logging()
    args = parse_args()
    sqlite_db_path = Path(args.sqlite_db).resolve()
    neon_url_path = Path(args.neon_url_path).resolve()
    neon_url = load_neon_url(neon_url_path)

    users = load_local_users(sqlite_db_path)
    ensure_remote_table(neon_url)
    migrated_count = upload_users(neon_url, users)

    LOGGER.info(
        "Migration completed",
        extra={"event": "migration.completed", "migrated_count": migrated_count},
    )
    print(f"Migrated {migrated_count} users to remote login table.")


if __name__ == "__main__":
    main()

"""Migrate local Streamlit login records from SQLite to Postgres.

Run once to bootstrap the remote login table used by production auth.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import List, Tuple

import psycopg2


LOGGER = logging.getLogger("nutients_app.auth.migration")
REMOTE_USERS_TABLE = "app_logins"


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
        "--postgres-url",
        required=True,
        help="Postgres connection URL.",
    )
    return parser.parse_args()


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


def ensure_remote_table(postgres_url: str) -> None:
    """
    Ensure remote Postgres login table exists.

    Args:
        postgres_url: Postgres connection URL.
    """
    LOGGER.info(
        "Ensuring remote login table exists",
        extra={"event": "migration.remote.table.ensure"},
    )
    with psycopg2.connect(postgres_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {REMOTE_USERS_TABLE} (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        connection.commit()


def upload_users(postgres_url: str, users: List[Tuple[str, str, str]]) -> int:
    """
    Upload users to remote Postgres login table.

    Args:
        postgres_url: Postgres connection URL.
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

    with psycopg2.connect(postgres_url) as connection:
        with connection.cursor() as cursor:
            for username, password_hash, created_at in users:
                cursor.execute(
                    f"""
                    INSERT INTO {REMOTE_USERS_TABLE} (username, password_hash, created_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username)
                    DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        created_at = EXCLUDED.created_at
                    """,
                    (username, password_hash, created_at),
                )
        connection.commit()
    return len(users)


def main() -> None:
    """
    Run the local-to-Postgres login migration.
    """
    configure_logging()
    args = parse_args()
    sqlite_db_path = Path(args.sqlite_db).resolve()

    users = load_local_users(sqlite_db_path)
    ensure_remote_table(args.postgres_url)
    migrated_count = upload_users(args.postgres_url, users)

    LOGGER.info(
        "Migration completed",
        extra={"event": "migration.completed", "migrated_count": migrated_count},
    )
    print(f"Migrated {migrated_count} users to remote login table.")


if __name__ == "__main__":
    main()

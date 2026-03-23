"""Credential storage helpers for Streamlit authentication.

This module persists self-service user accounts in a local SQLite database and
stores passwords as PBKDF2 hashes.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2


AUTH_LOG = logging.getLogger("nutients_app.auth")
PBKDF2_ITERATIONS = 310_000
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
SALT_BYTES = 16
REMOTE_USERS_TABLE = "app_logins"


def hash_password(password: str) -> str:
    """
    Hash a password with PBKDF2-HMAC-SHA256.

    Args:
        password: Raw password provided by the user.

    Returns:
        Encoded password hash containing the algorithm, iterations, salt, and hash.
    """
    AUTH_LOG.info(
        "Hashing password for storage",
        extra={"event": "auth.password_hash_started"},
    )
    salt = secrets.token_bytes(SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    salt_token = base64.b64encode(salt).decode("ascii")
    hash_token = base64.b64encode(derived_key).decode("ascii")
    return f"{PASSWORD_HASH_PREFIX}${PBKDF2_ITERATIONS}${salt_token}${hash_token}"


def password_matches(password: str, stored_value: str) -> bool:
    """
    Verify a password against a hashed or legacy plain-text stored value.

    Args:
        password: Raw password provided by the user.
        stored_value: Stored password value from secrets or the local user store.

    Returns:
        True when the password matches the stored value.
    """
    AUTH_LOG.info(
        "Verifying password against stored credentials",
        extra={"event": "auth.password_verify_started"},
    )
    if not stored_value.startswith(f"{PASSWORD_HASH_PREFIX}$"):
        return hmac.compare_digest(password, stored_value)

    try:
        _, iteration_text, salt_token, hash_token = stored_value.split("$", maxsplit=3)
        iterations = int(iteration_text)
        salt = base64.b64decode(salt_token.encode("ascii"))
        expected_hash = base64.b64decode(hash_token.encode("ascii"))
    except (ValueError, TypeError, binascii.Error):
        AUTH_LOG.warning(
            "Stored password hash could not be parsed",
            extra={"event": "auth.password_verify_invalid_hash"},
        )
        return False

    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate_hash, expected_hash)


def get_user_password_hash(db_path: Path, username: str) -> Optional[str]:
    """
    Fetch the stored password hash for a username.

    Args:
        db_path: SQLite database path.
        username: Username to look up.

    Returns:
        Stored password hash when the user exists, otherwise None.
    """
    AUTH_LOG.info(
        "Looking up local user credentials",
        extra={"event": "auth.store_lookup", "username": username},
    )
    if not db_path.exists():
        return None

    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()

    if row is None:
        return None
    return str(row[0])


def ensure_remote_users_table(postgres_url: str) -> None:
    """
    Create the remote login table when it does not yet exist.

    Args:
        postgres_url: Postgres connection URL.
    """
    AUTH_LOG.info(
        "Ensuring remote login table exists",
        extra={"event": "auth.remote_table_ensure_started"},
    )
    with psycopg2.connect(postgres_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {REMOTE_USERS_TABLE} (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        connection.commit()


def get_remote_user_password_hash(postgres_url: str, username: str) -> Optional[str]:
    """
    Fetch a user password hash from the remote Postgres login table.

    Args:
        postgres_url: Postgres connection URL.
        username: Username to look up.

    Returns:
        Password hash when found, otherwise None.
    """
    AUTH_LOG.info(
        "Looking up remote user credentials",
        extra={"event": "auth.remote_lookup", "username": username},
    )
    ensure_remote_users_table(postgres_url)
    with psycopg2.connect(postgres_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT password_hash FROM {REMOTE_USERS_TABLE} WHERE username = %s",
                (username,),
            )
            row = cursor.fetchone()

    if row is None:
        return None
    return str(row[0])


def create_remote_user(postgres_url: str, username: str, password: str) -> bool:
    """
    Create a user in the remote Postgres login table.

    Args:
        postgres_url: Postgres connection URL.
        username: Username to insert.
        password: Raw password to hash and store.

    Returns:
        True when created, False when username already exists.
    """
    AUTH_LOG.info(
        "Creating remote user account",
        extra={"event": "auth.remote_create_started", "username": username},
    )
    ensure_remote_users_table(postgres_url)
    created_at = datetime.now(timezone.utc)
    password_hash = hash_password(password)

    with psycopg2.connect(postgres_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {REMOTE_USERS_TABLE} (username, password_hash, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (username) DO NOTHING
                """,
                (username, password_hash, created_at),
            )
            created = cursor.rowcount > 0
        connection.commit()

    if not created:
        AUTH_LOG.warning(
            "User account already exists in remote credential store",
            extra={"event": "auth.remote_create_conflict", "username": username},
        )
    return created


def create_user(db_path: Path, username: str, password: str) -> bool:
    """
    Create a new user account in the local credential store.

    Args:
        db_path: SQLite database path.
        username: Username to insert.
        password: Raw password to hash and store.

    Returns:
        True when the account is created, otherwise False.
    """
    AUTH_LOG.info(
        "Creating local user account",
        extra={"event": "auth.store_create_started", "username": username},
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    password_hash = hash_password(password)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        try:
            connection.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, created_at),
            )
        except sqlite3.IntegrityError:
            AUTH_LOG.warning(
                "User account already exists in local credential store",
                extra={"event": "auth.store_create_conflict", "username": username},
            )
            return False

    return True

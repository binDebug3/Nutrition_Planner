"""Unit tests for frontend authentication service helpers."""

from __future__ import annotations

import logging
from types import ModuleType

from conftest import FRONTEND_APP_DIR


def _load_auth_service_module(load_module: object) -> ModuleType:
    """Import the auth service module from file.

    Args:
        load_module: Shared file-based module loader fixture.

    Returns:
        Imported auth service module.
    """
    return load_module(
        "test_frontend_auth_service_module",
        FRONTEND_APP_DIR / "auth_service.py",
        prepend_paths=[FRONTEND_APP_DIR],
    )


def test_create_account_and_credentials_match_with_local_db(
    load_module: object,
    fake_streamlit: ModuleType,
    tmp_path: object,
) -> None:
    """Create a local user and authenticate with the stored password hash."""
    auth_service_module = _load_auth_service_module(load_module)
    user_db_path = tmp_path / "users.db"
    service = auth_service_module.AuthService(
        fake_streamlit,
        logging.getLogger("test.auth"),
        logging.getLogger("test.app"),
        user_db_path,
    )

    created = service.create_account("alice", "secret")
    authenticated = service.credentials_match("alice", "secret")

    assert created is True
    assert authenticated is True


def test_get_secret_login_map_handles_invalid_mapping_type(
    load_module: object,
    fake_streamlit: ModuleType,
    tmp_path: object,
) -> None:
    """Return an empty map when Streamlit secrets are not a mapping."""
    auth_service_module = _load_auth_service_module(load_module)
    service = auth_service_module.AuthService(
        fake_streamlit,
        logging.getLogger("test.auth"),
        logging.getLogger("test.app"),
        tmp_path / "users.db",
    )
    fake_streamlit.secrets = {"passwords": ["bad-type"]}

    login_map = service.get_secret_login_map()

    assert login_map == {}


def test_normalize_username_trims_whitespace(
    load_module: object,
    fake_streamlit: ModuleType,
    tmp_path: object,
) -> None:
    """Strip leading and trailing whitespace from usernames."""
    auth_service_module = _load_auth_service_module(load_module)
    service = auth_service_module.AuthService(
        fake_streamlit,
        logging.getLogger("test.auth"),
        logging.getLogger("test.app"),
        tmp_path / "users.db",
    )

    normalized = service.normalize_username("  alice  ")

    assert normalized == "alice"


def test_credentials_match_uses_remote_store_when_configured(
    load_module: object,
    fake_streamlit: ModuleType,
    tmp_path: object,
) -> None:
    """Authenticate against remote store when a Postgres URL exists in secrets."""
    auth_service_module = _load_auth_service_module(load_module)
    fake_streamlit.secrets = {
        "connections": {"postgresql": {"url": "postgresql://example"}},
        "passwords": {},
    }
    stored_hash = auth_service_module.create_user.__globals__["hash_password"]("secret")
    auth_service_module.get_remote_user_password_hash = lambda url, username: (
        stored_hash
    )

    service = auth_service_module.AuthService(
        fake_streamlit,
        logging.getLogger("test.auth"),
        logging.getLogger("test.app"),
        tmp_path / "users.db",
    )

    assert service.credentials_match("alice", "secret") is True


def test_create_account_uses_remote_store_when_configured(
    load_module: object,
    fake_streamlit: ModuleType,
    tmp_path: object,
) -> None:
    """Create account through remote store when Postgres URL is configured."""
    auth_service_module = _load_auth_service_module(load_module)
    fake_streamlit.secrets = {
        "connections": {"postgresql": {"url": "postgresql://example"}},
        "passwords": {},
    }
    auth_service_module.get_remote_user_password_hash = lambda url, username: None
    auth_service_module.create_remote_user = lambda url, username, password: True

    service = auth_service_module.AuthService(
        fake_streamlit,
        logging.getLogger("test.auth"),
        logging.getLogger("test.app"),
        tmp_path / "users.db",
    )

    assert service.create_account("alice", "secret") is True

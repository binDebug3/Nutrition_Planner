"""Unit tests for frontend SQL query construction helpers."""

from __future__ import annotations

import logging
from types import ModuleType

from conftest import FRONTEND_APP_DIR


def _load_query_builder_module(load_module: object) -> ModuleType:
    """Import the query builder module from file.

    Args:
        load_module: Shared file-based module loader fixture.

    Returns:
        Imported query builder module.
    """
    return load_module(
        "test_frontend_query_builder_module",
        FRONTEND_APP_DIR / "query_builder.py",
        prepend_paths=[FRONTEND_APP_DIR],
        clear_modules=["models"],
    )


def _load_models_module(load_module: object) -> ModuleType:
    """Import the frontend models module from file.

    Args:
        load_module: Shared file-based module loader fixture.

    Returns:
        Imported models module.
    """
    return load_module(
        "test_frontend_models_for_query_builder",
        FRONTEND_APP_DIR / "models.py",
        prepend_paths=[FRONTEND_APP_DIR],
    )


def test_build_where_clauses_returns_neutral_predicate(load_module: object) -> None:
    """Return a no-op predicate while slider SQL filtering is deferred."""
    query_builder_module = _load_query_builder_module(load_module)
    models_module = _load_models_module(load_module)
    builder = query_builder_module.FoodQueryBuilder(logging.getLogger("test.query"))

    clauses = builder.build_where_clauses(models_module.NUTRIENT_SPECS)

    assert clauses == ["1=1"]


def test_build_food_query_contains_expected_sql_fragments(load_module: object) -> None:
    """Build stable SQL text with neutral where clause and projection aliases."""
    query_builder_module = _load_query_builder_module(load_module)
    models_module = _load_models_module(load_module)
    builder = query_builder_module.FoodQueryBuilder(logging.getLogger("test.query"))

    query = builder.build_food_query(models_module.NUTRIENT_SPECS)

    assert "WITH nutrient_view AS" in query
    assert '"Value" AS value' in query
    assert "WHERE 1=1" in query
    assert f"LIMIT {models_module.QUERY_LIMIT}" in query

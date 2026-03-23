"""Unit tests for frontend recommendation rendering."""

from __future__ import annotations

import logging
from types import ModuleType

import numpy as np
import pandas as pd

from conftest import FRONTEND_APP_DIR


def _load_recommendation_view_module(load_module: object) -> ModuleType:
    """Import the recommendation view module from file.

    Args:
        load_module: Shared file-based module loader fixture.

    Returns:
        Imported recommendation view module.
    """
    return load_module(
        "test_frontend_recommendation_view_module",
        FRONTEND_APP_DIR / "recommendation_view.py",
        prepend_paths=[FRONTEND_APP_DIR],
        clear_modules=["models", "optimize"],
    )


def _load_optimize_module(load_module: object) -> ModuleType:
    """Import the optimize module from file.

    Args:
        load_module: Shared file-based module loader fixture.

    Returns:
        Imported optimize module.
    """
    return load_module(
        "test_frontend_optimize_for_recommendation",
        FRONTEND_APP_DIR / "optimize.py",
        prepend_paths=[FRONTEND_APP_DIR],
    )


def test_render_recommended_foods_shows_ranked_table_only(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Render ranked output when positive servings exist."""
    recommendation_module = _load_recommendation_view_module(load_module)
    optimize_module = _load_optimize_module(load_module)
    view = recommendation_module.RecommendationView(
        fake_streamlit,
        logging.getLogger("test.recommendation"),
    )

    df = pd.DataFrame(
        {
            "food_name": ["A", "B"],
            "serving_size": ["1 cup", "1 bar"],
            "value": [1.5, 2.0],
        }
    )
    result = optimize_module.OptimizationResult(
        status="optimal",
        objective_value=4.0,
        servings=np.array([0.0, 2.0]),
        selected_foods=["B"],
    )

    view.render_recommended_foods(df, result, {"vegan": True})

    assert len(fake_streamlit.tables) == 1
    assert any(
        isinstance(message, str) and "Top picks: B" in message
        for message in fake_streamlit.writes
    )


def test_render_recommended_foods_shows_empty_state_when_no_selection(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Render warning without any recommendation tables when no foods are selected."""
    recommendation_module = _load_recommendation_view_module(load_module)
    optimize_module = _load_optimize_module(load_module)
    view = recommendation_module.RecommendationView(
        fake_streamlit,
        logging.getLogger("test.recommendation"),
    )

    df = pd.DataFrame(
        {
            "food_name": ["A", "B"],
            "serving_size": ["1 cup", "1 bar"],
            "value": [1.0, 2.0],
        }
    )
    result = optimize_module.OptimizationResult(
        status="optimal",
        objective_value=0.0,
        servings=np.array([0.0, 0.0]),
        selected_foods=[],
    )

    view.render_recommended_foods(df, result, {})

    assert any(
        "No feasible foods were selected" in warning
        for warning in fake_streamlit.warnings
    )
    assert len(fake_streamlit.tables) == 0

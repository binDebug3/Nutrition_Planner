"""Unit tests for frontend filter rendering helpers."""

from __future__ import annotations

import logging
from types import ModuleType

from conftest import FRONTEND_APP_DIR


def _load_filter_panel_module(load_module: object) -> ModuleType:
    """Import the filter panel module from file.

    Args:
        load_module: Shared file-based module loader fixture.

    Returns:
        Imported filter panel module.
    """
    return load_module(
        "test_frontend_filter_panel_module",
        FRONTEND_APP_DIR / "filters_ui.py",
        prepend_paths=[FRONTEND_APP_DIR],
        clear_modules=["models", "state_manager"],
    )


def _load_state_manager_module(load_module: object) -> ModuleType:
    """Import the state manager module from file.

    Args:
        load_module: Shared file-based module loader fixture.

    Returns:
        Imported state manager module.
    """
    return load_module(
        "test_frontend_state_manager_for_panel",
        FRONTEND_APP_DIR / "state_manager.py",
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
        "test_frontend_models_for_panel",
        FRONTEND_APP_DIR / "models.py",
        prepend_paths=[FRONTEND_APP_DIR],
    )


def test_render_dietary_toggles_initializes_session_keys(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Render dietary toggles and seed expected session-state keys."""
    filter_panel_module = _load_filter_panel_module(load_module)
    state_manager_module = _load_state_manager_module(load_module)
    manager = state_manager_module.NutrientStateManager(
        fake_streamlit,
        logging.getLogger("test.panel.state"),
    )
    panel = filter_panel_module.FilterPanel(
        fake_streamlit,
        logging.getLogger("test.panel"),
        manager,
    )

    models_module = _load_models_module(load_module)

    preferences = panel.render_dietary_toggles(models_module.NUTRIENT_SPECS)

    assert set(preferences.keys()) == {
        "gluten_free",
        "vegan",
        "vegetarian",
        "dairy_free",
        "nut_free",
    }
    assert "dietary_gluten_free" in fake_streamlit.session_state


def test_render_dietary_toggles_bulk_sets_all_any_on(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Set every nutrient Any toggle to True through the top bulk action."""
    filter_panel_module = _load_filter_panel_module(load_module)
    state_manager_module = _load_state_manager_module(load_module)
    models_module = _load_models_module(load_module)
    manager = state_manager_module.NutrientStateManager(
        fake_streamlit,
        logging.getLogger("test.panel.state"),
    )
    panel = filter_panel_module.FilterPanel(
        fake_streamlit,
        logging.getLogger("test.panel"),
        manager,
    )
    fake_streamlit.button_values = [True, False]

    panel.render_dietary_toggles(models_module.NUTRIENT_SPECS)

    assert all(
        fake_streamlit.session_state[f"{spec.key}_any"] is True
        for spec in models_module.NUTRIENT_SPECS
    )
    assert "dietary_gluten_free" in fake_streamlit.session_state


def test_render_dietary_toggles_bulk_sets_all_any_off(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Set every nutrient Any toggle to False through the top bulk action."""
    filter_panel_module = _load_filter_panel_module(load_module)
    state_manager_module = _load_state_manager_module(load_module)
    models_module = _load_models_module(load_module)
    manager = state_manager_module.NutrientStateManager(
        fake_streamlit,
        logging.getLogger("test.panel.state"),
    )
    panel = filter_panel_module.FilterPanel(
        fake_streamlit,
        logging.getLogger("test.panel"),
        manager,
    )
    for spec in models_module.NUTRIENT_SPECS:
        fake_streamlit.session_state[f"{spec.key}_any"] = True
    fake_streamlit.button_values = [False, True]

    panel.render_dietary_toggles(models_module.NUTRIENT_SPECS)

    assert all(
        fake_streamlit.session_state[f"{spec.key}_any"] is False
        for spec in models_module.NUTRIENT_SPECS
    )


def test_render_nutrient_filter_enables_manual_controls_when_any_off(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Keep min/max and slider controls enabled when Any is disabled."""
    filter_panel_module = _load_filter_panel_module(load_module)
    state_manager_module = _load_state_manager_module(load_module)
    models_module = _load_models_module(load_module)
    manager = state_manager_module.NutrientStateManager(
        fake_streamlit,
        logging.getLogger("test.panel.state"),
    )
    panel = filter_panel_module.FilterPanel(
        fake_streamlit,
        logging.getLogger("test.panel"),
        manager,
    )
    protein_spec = next(
        spec for spec in models_module.NUTRIENT_SPECS if spec.key == "protein"
    )
    fake_streamlit.toggle_values = {"protein_any": False}

    invalid_range = panel.render_nutrient_filter(protein_spec)

    assert invalid_range is False
    protein_control_calls = [
        call
        for call in fake_streamlit.number_input_calls
        if call["key"] in {"protein_min", "protein_max"}
    ]
    protein_slider_calls = [
        call for call in fake_streamlit.slider_calls if call["key"] == "protein_slider"
    ]
    assert len(protein_control_calls) == 2
    assert all(bool(call["disabled"]) is False for call in protein_control_calls)
    assert len(protein_slider_calls) == 1
    assert bool(protein_slider_calls[0]["disabled"]) is False


def test_render_all_nutrients_returns_per_nutrient_flags(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Render all filters and return one validity flag per nutrient key."""
    filter_panel_module = _load_filter_panel_module(load_module)
    state_manager_module = _load_state_manager_module(load_module)
    models_module = _load_models_module(load_module)
    manager = state_manager_module.NutrientStateManager(
        fake_streamlit,
        logging.getLogger("test.panel.state"),
    )
    panel = filter_panel_module.FilterPanel(
        fake_streamlit,
        logging.getLogger("test.panel"),
        manager,
    )

    invalid_ranges = panel.render_all_nutrients(models_module.NUTRIENT_SPECS)

    assert set(invalid_ranges.keys()) == {
        spec.key for spec in models_module.NUTRIENT_SPECS
    }
    assert all(isinstance(value, bool) for value in invalid_ranges.values())

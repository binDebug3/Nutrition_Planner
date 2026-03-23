"""Unit tests for frontend nutrient state management."""

from __future__ import annotations

import logging
from types import ModuleType

from conftest import FRONTEND_APP_DIR


def _load_state_manager_module(load_module: object) -> ModuleType:
    """Import the state manager module from file.

    Args:
        load_module: Shared file-based module loader fixture.

    Returns:
        Imported state manager module.
    """
    return load_module(
        "test_frontend_state_manager_module",
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
        "test_frontend_models_for_state_manager",
        FRONTEND_APP_DIR / "models.py",
        prepend_paths=[FRONTEND_APP_DIR],
    )


def test_initialize_nutrient_state_seeds_all_keys(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Seed Any, slider, min, and max keys when they are absent."""
    state_manager_module = _load_state_manager_module(load_module)
    models_module = _load_models_module(load_module)
    manager = state_manager_module.NutrientStateManager(
        fake_streamlit,
        logging.getLogger("test.state"),
    )
    protein_spec = next(
        spec for spec in models_module.NUTRIENT_SPECS if spec.key == "protein"
    )

    manager.initialize_nutrient_state(protein_spec)

    assert fake_streamlit.session_state[manager.any_key(protein_spec)] is True
    assert fake_streamlit.session_state[manager.slider_key(protein_spec)] == (
        10.0,
        60.0,
    )
    assert fake_streamlit.session_state[manager.min_key(protein_spec)] == 10.0
    assert fake_streamlit.session_state[manager.max_key(protein_spec)] == 60.0


def test_sync_slider_from_inputs_clamps_values(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Clamp out-of-range manual values before storing slider tuple."""
    state_manager_module = _load_state_manager_module(load_module)
    models_module = _load_models_module(load_module)
    manager = state_manager_module.NutrientStateManager(
        fake_streamlit,
        logging.getLogger("test.state"),
    )
    protein_spec = next(
        spec for spec in models_module.NUTRIENT_SPECS if spec.key == "protein"
    )
    fake_streamlit.session_state[manager.min_key(protein_spec)] = -5.0
    fake_streamlit.session_state[manager.max_key(protein_spec)] = 120.0

    manager.sync_slider_from_inputs(protein_spec)

    assert fake_streamlit.session_state[manager.min_key(protein_spec)] == 0.0
    assert fake_streamlit.session_state[manager.max_key(protein_spec)] == 100.0
    assert fake_streamlit.session_state[manager.slider_key(protein_spec)] == (
        0.0,
        100.0,
    )


def test_is_invalid_range_requires_manual_mode(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Treat min>=max as invalid only when Any toggle is disabled."""
    state_manager_module = _load_state_manager_module(load_module)
    models_module = _load_models_module(load_module)
    manager = state_manager_module.NutrientStateManager(
        fake_streamlit,
        logging.getLogger("test.state"),
    )
    protein_spec = next(
        spec for spec in models_module.NUTRIENT_SPECS if spec.key == "protein"
    )
    fake_streamlit.session_state[manager.any_key(protein_spec)] = False
    fake_streamlit.session_state[manager.min_key(protein_spec)] = 20.0
    fake_streamlit.session_state[manager.max_key(protein_spec)] = 20.0

    assert manager.is_invalid_range(protein_spec) is True

    fake_streamlit.session_state[manager.any_key(protein_spec)] = True
    assert manager.is_invalid_range(protein_spec) is False


def test_build_slider_bounds_respects_any_toggle(
    load_module: object,
    fake_streamlit: ModuleType,
) -> None:
    """Emit None bounds for Any nutrients and values for manual nutrients."""
    state_manager_module = _load_state_manager_module(load_module)
    models_module = _load_models_module(load_module)
    manager = state_manager_module.NutrientStateManager(
        fake_streamlit,
        logging.getLogger("test.state"),
    )
    protein_spec = next(
        spec for spec in models_module.NUTRIENT_SPECS if spec.key == "protein"
    )
    fat_spec = next(spec for spec in models_module.NUTRIENT_SPECS if spec.key == "fat")

    fake_streamlit.session_state[manager.any_key(protein_spec)] = False
    fake_streamlit.session_state[manager.min_key(protein_spec)] = 30.0
    fake_streamlit.session_state[manager.max_key(protein_spec)] = 70.0
    fake_streamlit.session_state[manager.any_key(fat_spec)] = True

    bounds = manager.build_slider_bounds([protein_spec, fat_spec])

    assert bounds.minimums[protein_spec.db_column] == 30.0
    assert bounds.maximums[protein_spec.db_column] == 70.0
    assert bounds.minimums[fat_spec.db_column] is None
    assert bounds.maximums[fat_spec.db_column] is None

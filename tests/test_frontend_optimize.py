"""Unit tests for the frontend optimization module."""

from __future__ import annotations

import types
from types import ModuleType

import numpy as np
import pandas as pd

from conftest import FRONTEND_APP_DIR


def _load_frontend_optimize(load_module: object, module_name: str) -> ModuleType:
    """Import the frontend optimize module.

    Args:
        load_module: Shared file-based module loader fixture.
        module_name: Unique module name for the import.

    Returns:
        Imported optimize module.
    """
    return load_module(
        module_name,
        FRONTEND_APP_DIR / "optimize.py",
        prepend_paths=[FRONTEND_APP_DIR],
    )


def test_simplex_init_normalizes_input_arrays(load_module: object) -> None:
    """Normalize values and nutrient arrays in optimizer initialization."""
    module = _load_frontend_optimize(load_module, "test_frontend_optimize_init")
    data = pd.DataFrame(
        {
            "food_name": ["A", "B"],
            "value": [2.5, "3.0"],
            "protein": [10.0, 20.0],
            "carbs": [15.0, 30.0],
        }
    )
    bounds = module.SliderBounds(
        minimums={"protein": 12.0, "carbs": None},
        maximums={"protein": 40.0, "carbs": 45.0},
    )

    optimizer = module.Simplex(data=data, bounds=bounds)

    assert optimizer.food_names == ["A", "B"]
    assert optimizer.nutrient_columns == ["carbs", "protein"]
    assert optimizer.value_vector.tolist() == [2.5, 3.0]
    assert optimizer.nutrient_matrix.shape == (2, 2)


def test_simplex_init_raises_when_value_column_missing(load_module: object) -> None:
    """Reject data that does not provide the required value column."""
    module = _load_frontend_optimize(
        load_module,
        "test_frontend_optimize_missing_value",
    )
    data = pd.DataFrame(
        {
            "food_name": ["A"],
            "protein": [10.0],
        }
    )
    bounds = module.SliderBounds(minimums={"protein": 5.0}, maximums={"protein": 15.0})

    try:
        module.Simplex(data=data, bounds=bounds)
        assert False, "Expected ValueError when value column is missing."
    except ValueError as exc:
        assert "value column" in str(exc)


def test_run_filters_out_servings_at_or_below_threshold(load_module: object) -> None:
    """Zero out servings at or below 0.3 before returning optimizer output."""
    module = _load_frontend_optimize(load_module, "test_frontend_optimize_threshold")
    data = pd.DataFrame(
        {
            "food_name": ["A", "B", "C"],
            "value": [1.0, 2.0, 3.0],
        }
    )
    bounds = module.SliderBounds(minimums={}, maximums={})
    optimizer = module.Simplex(data=data, bounds=bounds)

    class FakeValueVector:
        """Minimal vector stand-in that supports matmul in objective setup."""

        def __matmul__(self, other: object) -> float:
            """Return placeholder objective expression."""
            if isinstance(other, np.ndarray):
                return float(np.array([1.0, 2.0, 3.0], dtype=float) @ other)
            return 0.0

    optimizer.value_vector = FakeValueVector()

    class FakeVariable:
        """Minimal cvxpy variable stand-in with solved values."""

        def __init__(self, length: int, nonneg: bool = False) -> None:
            """Store canned solved values used by the optimizer."""
            _ = (length, nonneg)
            self.value = np.array([0.3, 0.31, 1.2], dtype=float)

        def __le__(self, other: object) -> list[object]:
            """Return placeholder constraint object."""
            return [other]

    class FakeProblem:
        """Minimal cvxpy problem stand-in."""

        def __init__(self, objective_arg: object, constraints_arg: object) -> None:
            """Store placeholder problem inputs."""
            _ = (objective_arg, constraints_arg)
            self.value = 99.0
            self.status = "optimal"

        def solve(self) -> None:
            """Pretend the optimization solved successfully."""

    fake_cvxpy = types.ModuleType("cvxpy")
    fake_cvxpy.Variable = FakeVariable
    fake_cvxpy.Maximize = lambda expression: expression
    fake_cvxpy.Problem = FakeProblem

    import sys

    sys.modules["cvxpy"] = fake_cvxpy
    try:
        result = optimizer.run()
    finally:
        sys.modules.pop("cvxpy", None)

    assert result.servings.tolist() == [0.0, 0.31, 1.2]
    assert result.selected_foods == ["B", "C"]
    assert result.objective_value == 4.22

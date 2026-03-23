"""Unit tests for src/backend/gemini/convert_to_meals.py."""

from __future__ import annotations

import types
from pathlib import Path

from conftest import REPO_ROOT


GEMINI_CONVERT_PATH = REPO_ROOT / "src" / "backend" / "gemini" / "convert_to_meals.py"


class FakeOptimizationResult:
    """Minimal optimizer result double for ingredient extraction tests."""

    def __init__(self, selected_foods: list[str]) -> None:
        """Store selected food names.

        Args:
            selected_foods: Ordered selected food names.
        """
        self.selected_foods = selected_foods


def test_extract_top_ingredients_splits_on_first_comma_and_limits(
    load_module: object,
) -> None:
    """Keep first comma-separated token and cap the list at 20 items."""
    module = load_module("test_backend_gemini_convert", GEMINI_CONVERT_PATH)
    rows = [
        {
            "food_name": f"Food {index}, extra",
            "serving_size": "1 cup",
            "serving_count": 1.0,
        }
        for index in range(30)
    ]
    rows[0]["food_name"] = "Milk, 1%"
    rows[1]["food_name"] = "Apple"

    ingredients = module.extract_top_ingredients(rows)

    assert len(ingredients) == 20
    assert ingredients[0]["ingredient"] == "Milk"
    assert ingredients[1]["ingredient"] == "Apple"
    assert ingredients[-1]["ingredient"] == "Food 19"
    assert ingredients[0]["serving_size"] == "1 cup"
    assert ingredients[0]["serving_count"] == "1.0"


def test_build_gemini_input_appends_ingredients_after_prompt(
    load_module: object,
) -> None:
    """Place ingredient list after prompt text with one item per bullet line."""
    module = load_module("test_backend_gemini_convert_input", GEMINI_CONVERT_PATH)

    input_text = module.build_gemini_input(
        "Base prompt",
        [
            {
                "ingredient": "Milk",
                "serving_size": "1 cup",
                "serving_count": "1.5",
            },
            {
                "ingredient": "Apple",
                "serving_size": "1 medium",
                "serving_count": "2.0",
            },
        ],
    )

    assert input_text == (
        "Base prompt\n\n"
        "- Milk | serving size: 1 cup | servings: 1.5\n"
        "- Apple | serving size: 1 medium | servings: 2.0"
    )


def test_load_prompt_reads_text_with_utf8(
    load_module: object,
    monkeypatch: object,
) -> None:
    """Read prompt text from the configured path and strip whitespace."""
    module = load_module("test_backend_gemini_convert_prompt", GEMINI_CONVERT_PATH)

    monkeypatch.setattr(Path, "read_text", lambda self, encoding: " prompt text \n")

    prompt = module.load_prompt(Path("any/prompt/path.txt"))

    assert prompt == "prompt text"


def test_call_gemini_uses_client_generate_content(
    load_module: object,
    monkeypatch: object,
) -> None:
    """Create a Gemini client with API key and return response text."""
    module = load_module("test_backend_gemini_convert_call", GEMINI_CONVERT_PATH)
    captured: dict[str, str] = {}

    class FakeResponse:
        """Simple Gemini response object with text property."""

        text = "Meal plan output"

    class FakeModels:
        """Capture model and contents sent to Gemini."""

        def generate_content(self, model: str, contents: str) -> FakeResponse:
            """Record generation request and return a fake response."""
            captured["model"] = model
            captured["contents"] = contents
            return FakeResponse()

    class FakeClient:
        """Store API key and expose fake models endpoint."""

        def __init__(self, api_key: str) -> None:
            """Store API key used to initialize client."""
            captured["api_key"] = api_key
            self.models = FakeModels()

    fake_google = types.ModuleType("google")
    fake_genai = types.ModuleType("genai")
    fake_genai.Client = FakeClient
    fake_google.genai = fake_genai

    monkeypatch.setitem(__import__("sys").modules, "google", fake_google)

    output = module.call_gemini("Prompt and ingredients", "abc123", "gemini-1.5-flash")

    assert output == "Meal plan output"
    assert captured["api_key"] == "abc123"
    assert captured["model"] == "gemini-1.5-flash"
    assert captured["contents"] == "Prompt and ingredients"


def test_convert_to_meals_end_to_end_with_mocks(
    load_module: object,
    monkeypatch: object,
) -> None:
    """Load files, normalize ingredients, and pass combined text to Gemini."""
    module = load_module("test_backend_gemini_convert_flow", GEMINI_CONVERT_PATH)
    recommendation_rows = [
        {
            "food_name": "Milk, 1%",
            "serving_size": "1 cup",
            "serving_count": 1.5,
        },
        {
            "food_name": "Bread, whole wheat",
            "serving_size": "1 slice",
            "serving_count": 2.0,
        },
    ]

    captured: dict[str, str] = {}

    monkeypatch.setattr(module, "load_prompt", lambda _path: "Prompt header")
    monkeypatch.setattr(module, "load_api_key", lambda _path: "key-123")

    def fake_call_gemini(input_text: str, api_key: str, model: str) -> str:
        """Capture Gemini call inputs and return a canned response."""
        captured["input_text"] = input_text
        captured["api_key"] = api_key
        captured["model"] = model
        return "Meals"

    monkeypatch.setattr(module, "call_gemini", fake_call_gemini)

    output = module.convert_to_meals(recommendation_rows)

    assert output == "Meals"
    assert captured["api_key"] == "key-123"
    assert captured["model"] == "gemini-1.5-flash"
    assert captured["input_text"] == (
        "Prompt header\n\n"
        "- Milk | serving size: 1 cup | servings: 1.5\n"
        "- Bread | serving size: 1 slice | servings: 2.0"
    )

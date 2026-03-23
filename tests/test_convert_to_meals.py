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


def test_load_api_key_reads_nested_gemini_secret(
    load_module: object,
    tmp_path: Path,
) -> None:
    """Read the Gemini API key from the frontend Streamlit secrets TOML file."""
    module = load_module("test_backend_gemini_convert_secret", GEMINI_CONVERT_PATH)
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('[gemini]\napi_key = " secret-123 "\n', encoding="utf-8")

    api_key = module.load_api_key(secrets_path)

    assert api_key == "secret-123"


def test_load_api_key_reads_top_level_secret_fallback(
    load_module: object,
    tmp_path: Path,
) -> None:
    """Fall back to a top-level secret name when a Gemini section is absent."""
    module = load_module(
        "test_backend_gemini_convert_secret_fallback", GEMINI_CONVERT_PATH
    )
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('GOOGLE_API_KEY = "top-level-key"\n', encoding="utf-8")

    api_key = module.load_api_key(secrets_path)

    assert api_key == "top-level-key"


def test_load_api_key_reads_streamlit_runtime_secrets_when_file_missing(
    load_module: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    """Use runtime Streamlit secrets when hosted deployments lack a local file."""
    module = load_module(
        "test_backend_gemini_convert_runtime_secret", GEMINI_CONVERT_PATH
    )
    secrets_path = tmp_path / "missing-secrets.toml"

    fake_streamlit = types.ModuleType("streamlit")
    fake_streamlit.secrets = {"gemini": {"api_key": "runtime-key"}}

    monkeypatch.setitem(__import__("sys").modules, "streamlit", fake_streamlit)

    api_key = module.load_api_key(secrets_path)

    assert api_key == "runtime-key"


def test_load_streamlit_secrets_raises_when_file_and_runtime_are_missing(
    load_module: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    """Raise a clear file error when no file or runtime secrets are available."""
    module = load_module(
        "test_backend_gemini_convert_missing_runtime_secret", GEMINI_CONVERT_PATH
    )
    secrets_path = tmp_path / "missing-secrets.toml"

    monkeypatch.setattr(module, "load_runtime_streamlit_secrets", lambda: None)

    try:
        module.load_streamlit_secrets(secrets_path)
        assert False, (
            "Expected FileNotFoundError when no Streamlit secrets source exists."
        )
    except FileNotFoundError as exc:
        assert "runtime secrets are unavailable" in str(exc)


def test_load_api_key_raises_when_secret_is_missing(
    load_module: object,
    tmp_path: Path,
) -> None:
    """Raise a clear error when no supported Gemini key exists in the TOML file."""
    module = load_module(
        "test_backend_gemini_convert_secret_missing", GEMINI_CONVERT_PATH
    )
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('[passwords]\ndefault = "nope"\n', encoding="utf-8")

    try:
        module.load_api_key(secrets_path)
        assert False, "Expected ValueError when the Gemini API key is missing."
    except ValueError as exc:
        assert "Gemini API key not found" in str(exc)


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
    assert captured["model"] == module.DEFAULT_GEMINI_MODEL
    assert captured["input_text"] == (
        "Prompt header\n\n"
        "- Milk | serving size: 1 cup | servings: 1.5\n"
        "- Bread | serving size: 1 slice | servings: 2.0"
    )


def test_call_gemini_falls_back_when_model_not_found(
    load_module: object,
    monkeypatch: object,
) -> None:
    """Retry with fallback models when the requested model returns not-found."""
    module = load_module("test_backend_gemini_convert_fallback", GEMINI_CONVERT_PATH)
    calls: list[str] = []
    requested_model = "gemini-2.0-flash"
    fallback_model = "gemini-2.0-flash-lite"

    class FakeResponse:
        """Simple Gemini response object with text property."""

        text = "Fallback meal plan"

    class FakeModels:
        """Simulate model-not-found on first model and success on fallback."""

        def generate_content(self, model: str, contents: str) -> FakeResponse:
            """Return success only for fallback models."""
            _ = contents
            calls.append(model)
            if model == requested_model:
                raise RuntimeError("404 NOT_FOUND: model is not found")
            return FakeResponse()

    class FakeClient:
        """Expose fake models endpoint used by convert_to_meals."""

        def __init__(self, api_key: str) -> None:
            """Accept api key argument for compatibility."""
            _ = api_key
            self.models = FakeModels()

    fake_google = types.ModuleType("google")
    fake_genai = types.ModuleType("genai")
    fake_genai.Client = FakeClient
    fake_google.genai = fake_genai

    monkeypatch.setitem(__import__("sys").modules, "google", fake_google)
    monkeypatch.setattr(module, "FALLBACK_GEMINI_MODELS", (fallback_model,))

    output = module.call_gemini(
        "Prompt and ingredients",
        "abc123",
        model=requested_model,
    )

    assert output == "Fallback meal plan"
    assert calls[:2] == [requested_model, fallback_model]

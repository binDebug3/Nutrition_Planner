"""Manual terminal preview for convert_to_meals Gemini prompt payload."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GEMINI_CONVERT_PATH = REPO_ROOT / "src" / "backend" / "gemini" / "convert_to_meals.py"


def _load_convert_to_meals_module() -> object:
    """Load convert_to_meals.py directly from file path.

    Returns:
        Imported convert_to_meals module object.

    Raises:
        ImportError: If module import spec cannot be created or loaded.
    """
    spec = importlib.util.spec_from_file_location(
        "manual_preview_convert_to_meals",
        GEMINI_CONVERT_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {GEMINI_CONVERT_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    """Print the exact Gemini payload format to the terminal.

    Returns:
        Zero when preview generation succeeds.
    """
    module = _load_convert_to_meals_module()

    prompt_text = "Create meal ideas from these recommended foods."
    recommended_food_rows = [
        {"food_name": "Milk, 1%", "serving_size": "1 cup", "serving_count": 1.5},
        {
            "food_name": "Bread, whole wheat",
            "serving_size": "1 slice",
            "serving_count": 2.0,
        },
        {
            "food_name": "Greek Yogurt, plain",
            "serving_size": "170 g",
            "serving_count": 1.0,
        },
    ]

    ingredients = module.extract_top_ingredients(recommended_food_rows)
    gemini_payload = module.build_gemini_input(prompt_text, ingredients)

    print("\n=== Gemini Prompt Payload Preview ===")
    print(gemini_payload)
    print("=== End Preview ===\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

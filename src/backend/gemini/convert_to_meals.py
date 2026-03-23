"""Convert optimizer food recommendations into meal suggestions using Gemini.

This module loads a prompt template and Gemini API key from the frontend
Streamlit secrets file, normalizes the top recommended foods into ingredient
names, and requests meal ideas from Gemini.
"""

from __future__ import annotations

import logging
from pathlib import Path
import tomllib
from typing import Mapping, Protocol, Sequence


MODULE_PATH = Path(__file__).resolve()
REPO_ROOT = MODULE_PATH.parents[3]
DIETETICS_ROOT = REPO_ROOT.parent
DEFAULT_PROMPT_PATH = REPO_ROOT / "src" / "backend" / "gemini" / "prompts" / "convert_to_meals.txt"
DEFAULT_SECRETS_PATH = (
    REPO_ROOT / "src" / "frontend" / "app" / ".streamlit" / "secrets.toml"
)
GEMINI_SECRET_SECTIONS = ("gemini", "google")
GEMINI_SECRET_KEY = "api_key"
TOP_LEVEL_GEMINI_SECRET_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"
FALLBACK_GEMINI_MODELS = ()
TOP_INGREDIENT_COUNT = 20
FOOD_NAME_SPLIT_DELIMITER = ","
INGREDIENT_PREFIX = "- "
DEBUG_PROMPT_LOG_PATH = REPO_ROOT / "logs" / "convert_to_meals_prompt.tmp"
DEBUG_RESPONSE_LOG_PATH = REPO_ROOT / "logs" / "convert_to_meals_response.tmp"

log = logging.getLogger("nutients_app.backend.gemini.convert_to_meals")


class OptimizationResultLike(Protocol):
    """Protocol for optimizer results consumed by this module.

    Attributes:
        selected_foods: Ordered list of recommended food names.
    """

    selected_foods: Sequence[str]


class RecommendedFoodRow(Protocol):
    """Protocol for recommendation rows consumed by Gemini prompt assembly.

    Expected keys in row mappings:
        food_name: Raw food name text.
        serving_size: Display serving size text.
        serving_count: Recommended servings numeric value.
    """

    def __getitem__(self, item: str) -> object:
        """Return a row field by key name.

        Args:
            item: Field key.

        Returns:
            Field value.
        """


def load_prompt(prompt_path: Path = DEFAULT_PROMPT_PATH) -> str:
    """Load the base Gemini prompt text.

    Args:
        prompt_path: Absolute path to the prompt template file.

    Returns:
        Prompt text from the target file.

    Raises:
        FileNotFoundError: If the prompt file path does not exist.
        ValueError: If the prompt file is empty after stripping whitespace.
    """
    log.info("Loading Gemini prompt template", extra={"path": str(prompt_path)})

    prompt_text = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt_text:
        raise ValueError(f"Prompt file is empty: {prompt_path}")
    return prompt_text


def load_streamlit_secrets(
    secrets_path: Path = DEFAULT_SECRETS_PATH,
) -> Mapping[str, object]:
    """Load Streamlit secrets from the frontend TOML file.

    Args:
        secrets_path: Absolute path to the Streamlit secrets TOML file.

    Returns:
        Parsed Streamlit secrets mapping.

    Raises:
        FileNotFoundError: If the secrets file path does not exist.
        ValueError: If the secrets file does not contain a TOML object.
    """
    log.info("Loading Streamlit secrets file", extra={"path": str(secrets_path)})

    secrets_text = secrets_path.read_text(encoding="utf-8")
    secrets = tomllib.loads(secrets_text)
    if not isinstance(secrets, dict):
        raise ValueError(f"Streamlit secrets file is not a TOML object: {secrets_path}")
    return secrets


def load_api_key(secrets_path: Path = DEFAULT_SECRETS_PATH) -> str:
    """Load the Gemini API key from the frontend Streamlit secrets file.

    Args:
        secrets_path: Absolute path to the Streamlit secrets TOML file.

    Returns:
        Gemini API key string.

    Raises:
        FileNotFoundError: If the secrets file path does not exist.
        ValueError: If the API key is missing or empty.
    """
    log.info(
        "Resolving Gemini API key from Streamlit secrets",
        extra={"path": str(secrets_path)},
    )

    secrets = load_streamlit_secrets(secrets_path)

    for section_name in GEMINI_SECRET_SECTIONS:
        section = secrets.get(section_name, {})
        if not isinstance(section, Mapping):
            continue
        api_key = section.get(GEMINI_SECRET_KEY)
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()

    for secret_key in TOP_LEVEL_GEMINI_SECRET_KEYS:
        api_key = secrets.get(secret_key)
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()

    raise ValueError(
        "Gemini API key not found in Streamlit secrets file: "
        f"{secrets_path}. Expected [gemini].api_key, [google].api_key, "
        "GEMINI_API_KEY, or GOOGLE_API_KEY."
    )


def normalize_food_name(food_name: str) -> str:
    """Normalize one food string into an ingredient name.

    This keeps only the first segment before the first comma, so food labels
    like "Milk, 1%" become "Milk".

    Args:
        food_name: Raw food name from optimizer output.

    Returns:
        Normalized ingredient name.
    """
    log.info("Normalizing food name for Gemini input")

    normalized_name = food_name.split(FOOD_NAME_SPLIT_DELIMITER, maxsplit=1)[0].strip()
    return normalized_name if normalized_name else food_name.strip()


def extract_top_ingredients(
    recommended_food_rows: Sequence[Mapping[str, object]],
    limit: int = TOP_INGREDIENT_COUNT,
) -> list[dict[str, str]]:
    """Extract normalized top recommendation rows for Gemini.

    Args:
        recommended_food_rows: Recommendation rows with name, size, and count.
        limit: Maximum number of foods to include.

    Returns:
        List of dictionaries with normalized ingredient details.
    """
    log.info(
        "Extracting top ingredients from recommendation rows",
        extra={"limit": limit},
    )

    normalized_rows: list[dict[str, str]] = []
    for row in recommended_food_rows[: max(0, limit)]:
        food_name = str(row.get("food_name", "")).strip()
        serving_size = str(row.get("serving_size", "")).strip()
        serving_count_raw = row.get("serving_count", 0)
        try:
            serving_count = float(serving_count_raw)
        except (TypeError, ValueError):
            serving_count = 0.0

        normalized_rows.append(
            {
                "ingredient": normalize_food_name(food_name),
                "serving_size": serving_size,
                "serving_count": f"{serving_count:.1f}",
            }
        )
    return normalized_rows


def build_gemini_input(
    prompt_text: str,
    ingredients: Sequence[Mapping[str, str]],
) -> str:
    """Build the full Gemini prompt input.

    Args:
        prompt_text: Base prompt template text.
        ingredients: Ingredient rows with name, serving size, and serving count.

    Returns:
        Combined input text sent to Gemini.
    """
    log.info(
        "Building Gemini input payload",
        extra={"ingredient_count": len(ingredients)},
    )

    ingredient_lines = "\n".join(
        (
            f"{INGREDIENT_PREFIX}{ingredient_row['ingredient']}"
            f" | serving size: {ingredient_row['serving_size']}"
            f" | servings: {ingredient_row['serving_count']}"
        )
        for ingredient_row in ingredients
    )
    return f"{prompt_text}\n\n{ingredient_lines}" if ingredient_lines else prompt_text


def call_gemini(
    input_text: str,
    api_key: str,
    model: str = DEFAULT_GEMINI_MODEL,
) -> str:
    """Call Gemini and return the response text.

    Args:
        input_text: Prompt plus normalized ingredient list.
        api_key: Gemini API key.
        model: Gemini model ID.

    Returns:
        Text response generated by Gemini.

    Raises:
        ValueError: If Gemini returns an empty text response.
    """
    log.info("Calling Gemini model", extra={"model": model})

    from google import genai

    client = genai.Client(api_key=api_key)

    candidate_models = [model]
    candidate_models.extend(
        fallback_model
        for fallback_model in FALLBACK_GEMINI_MODELS
        if fallback_model != model
    )

    last_error: Exception | None = None
    for candidate_model in candidate_models:
        try:
            response = client.models.generate_content(
                model=candidate_model,
                contents=input_text,
            )
            response_text = getattr(response, "text", None)

            if response_text is None:
                raise ValueError("Gemini response did not include text.")

            final_text = response_text.strip()
            if not final_text:
                raise ValueError("Gemini response text is empty.")

            return final_text
        except Exception as error:
            last_error = error
            error_text = str(error).lower()
            model_not_found = (
                any(token in error_text for token in ("404", "not_found", "not found"))
                and "model" in error_text
            )

            if not model_not_found:
                raise

            log.warning(
                "Gemini model unavailable, trying fallback model",
                extra={"model": candidate_model},
            )

    assert last_error is not None
    raise last_error


def write_debug_temp_file(file_path: Path, content: str) -> None:
    """Write debug content to a temp file that is overwritten each call.

    Args:
        file_path: Debug output file path.
        content: File body content.
    """
    log.info("Writing Gemini debug temp file", extra={"path": str(file_path)})

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def convert_to_meals(
    recommended_food_rows: Sequence[Mapping[str, object]],
    prompt_path: Path = DEFAULT_PROMPT_PATH,
    secrets_path: Path = DEFAULT_SECRETS_PATH,
    model: str = DEFAULT_GEMINI_MODEL,
) -> str:
    """Convert optimizer recommendations into a Gemini meal plan response.

    Args:
        recommended_food_rows: Ranked recommendation rows for Gemini input.
        prompt_path: Prompt file path.
        secrets_path: Streamlit secrets TOML file path.
        model: Gemini model ID.

    Returns:
        Meal suggestion text returned by Gemini.
    """
    log.info("Converting optimizer recommendations to meals")

    prompt_text = load_prompt(prompt_path)
    api_key = load_api_key(secrets_path)
    ingredients = extract_top_ingredients(
        recommended_food_rows, limit=TOP_INGREDIENT_COUNT
    )
    gemini_input = build_gemini_input(prompt_text, ingredients)
    write_debug_temp_file(DEBUG_PROMPT_LOG_PATH, gemini_input)

    try:
        response_text = call_gemini(gemini_input, api_key=api_key, model=model)
    except Exception as error:
        write_debug_temp_file(
            DEBUG_RESPONSE_LOG_PATH,
            f"Gemini call failed: {type(error).__name__}: {error}",
        )
        raise

    write_debug_temp_file(DEBUG_RESPONSE_LOG_PATH, response_text)
    return response_text

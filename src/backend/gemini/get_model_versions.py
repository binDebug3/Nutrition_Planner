"""Print available Gemini model versions for the configured API key."""

from __future__ import annotations

import logging
from pathlib import Path
import tomllib
from typing import Iterable, Mapping


LOGGER_NAME = "nutients_app.backend.gemini.get_model_versions"
DEFAULT_LOG_LEVEL = logging.INFO
GENERATION_METHOD_NAME = "generateContent"
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_SECRETS_PATH = (
    REPO_ROOT / "src" / "frontend" / "app" / ".streamlit" / "secrets.toml"
)
GEMINI_SECRET_SECTIONS = ("gemini", "google")
GEMINI_SECRET_KEY = "api_key"
TOP_LEVEL_GEMINI_SECRET_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

log = logging.getLogger(LOGGER_NAME)


def configure_logging() -> None:
    """Configure console logging for this script."""
    logging.basicConfig(
        level=DEFAULT_LOG_LEVEL,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    log.info("Logging configured")


def load_streamlit_secrets(
    secrets_path: Path = DEFAULT_SECRETS_PATH,
) -> Mapping[str, object]:
    """Load Streamlit secrets from the frontend TOML file.

    Args:
        secrets_path: Absolute path to the Streamlit secrets TOML file.

    Returns:
        Parsed Streamlit secrets mapping.

    Raises:
        ValueError: If the secrets file does not contain a TOML object.
    """
    log.info("Loading Streamlit secrets file", extra={"path": str(secrets_path)})

    secrets_text = secrets_path.read_text(encoding="utf-8")
    secrets = tomllib.loads(secrets_text)
    if not isinstance(secrets, dict):
        raise ValueError(f"Streamlit secrets file is not a TOML object: {secrets_path}")
    return secrets


def load_api_key(secrets_path: Path = DEFAULT_SECRETS_PATH) -> str:
    """Load Gemini API key from the frontend Streamlit secrets file.

    Args:
        secrets_path: Absolute path to the Streamlit secrets TOML file.

    Returns:
        Non-empty Gemini API key.

    Raises:
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


def list_models(api_key: str) -> Iterable[object]:
    """Fetch available models from Gemini.

    Args:
        api_key: Gemini API key.

    Returns:
        Iterable of model objects.
    """
    log.info("Requesting model list from Gemini")
    from google import genai

    client = genai.Client(api_key=api_key)
    return client.models.list()


def build_model_line(model: object) -> str:
    """Build a printable line for one Gemini model.

    Args:
        model: Model object returned by the SDK.

    Returns:
        Single formatted output line.
    """
    log.info("Formatting one model for output")
    model_name = str(getattr(model, "name", "<unknown-model>"))
    methods = getattr(model, "supported_generation_methods", []) or []
    methods_text = ", ".join(str(item) for item in methods) if methods else "none"
    marker = " [generateContent]" if GENERATION_METHOD_NAME in methods else ""
    return f"- {model_name}{marker} | methods: {methods_text}"


def main() -> None:
    """Run model listing script and print available model versions."""
    configure_logging()
    api_key = load_api_key()

    models = list(list_models(api_key))
    if not models:
        print("No models returned by Gemini for this API key.")
        return

    print("Available Gemini models:")
    for model in models:
        print(build_model_line(model))


if __name__ == "__main__":
    main()

"""
config.py — API key management, model definitions, and provider configuration.

This module is the single source of truth for:

- Provider base URLs (Gemini, OpenRouter, Ollama)
- Available model names as ``Literal`` type aliases for static analysis and IDE
  auto-complete (``GPTModels``, ``GeminiModels``, ``OllamaModels``, ``OpenRouterModels``)
- The ``ModelName`` union type consumed throughout the package
- ``MODEL_DICT``: a provider → set-of-model-names lookup used by
  ``_get_client_for_model()`` to pick the right ``OpenAI`` client
- ``get_api_key()``: a lazy, cached key resolver that tries Colab → env →
  interactive prompt in order, so the module is safe to import in any
  environment without blocking or raising.

Adding a new provider
---------------------
1. Add a ``Literal`` type with the model names.
2. Add it to the ``ModelName`` union.
3. Add an entry to ``MODEL_DICT``.
4. Handle it in ``LLMQuery._get_client_for_model()``.
"""

import os
import getpass
from typing import Literal, Union, get_args
from dotenv import load_dotenv

# Load .env file so os.getenv() picks up local config.
# override=True ensures .env values shadow any pre-existing shell exports.
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Provider base URLs
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://localhost:11434/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ---------------------------------------------------------------------------
# Model definitions
# Using Literal types gives IDE auto-complete and static type checking.
# ---------------------------------------------------------------------------

GPTModels = Literal[
    "gpt-4o-mini",
    "gpt-5-nano",
    "gpt-5-mini",
    "gpt-5.1",
    "gpt-5.2",
    "gpt-4.1-mini",
    "gpt-5.2-pro",
    "gpt-image-1.5",
    "gpt-4o-mini-tts",
    "tts-1",
]

OllamaModels = Literal["llama3.2", "deepseek-r1:1.5b"]

GeminiModels = Literal[
    "gemini-3-pro-preview",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "models/imagen-4.0-generate-001",
    "gemini-2.5-pro-preview-tts",
    "gemini-3-flash-preview",
]

OpenRouterModels = Literal[
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "deepseek/deepseek-v3.2",
    "deepseek/deepseek-r1",
    "x-ai/grok-4.1-fast",
    "z-ai/glm-4.7",
    "moonshotai/kimi-k2-thinking",
    "xiaomi/mimo-v2-flash:free",
    "qwen/qwen3-embedding-8b",
    "nvidia/nemotron-3-nano-30b-a3b",
    "anthropic/claude-opus-4.6",
]

# Union of all providers for use as the ModelName type annotation.
ModelName = Union[GPTModels, OllamaModels, GeminiModels, OpenRouterModels]

# Lookup table: provider name -> set of model strings.
# Used by _get_client_for_model() to select the correct OpenAI client.
MODEL_DICT = {
    "gpt": set(get_args(GPTModels)),
    "ollama": set(get_args(OllamaModels)),
    "gemini": set(get_args(GeminiModels)),
    "openrouter": set(get_args(OpenRouterModels)),
}

# ---------------------------------------------------------------------------
# Lazy API key resolution
# ---------------------------------------------------------------------------

# Internal cache — populated on first access per key.  Never eagerly resolved
# so that importing this module never blocks in non-interactive environments.
_API_KEYS: dict = {
    "GOOGLE_API_KEY": None,
    "OPENAI_API_KEY": None,
    "OPENROUTER_API_KEY": None,
}


def get_api_key(key_name: str) -> str:
    """
    Retrieve an API key using a three-tier fallback chain.

    Resolution order (first non-empty value wins):

    1. **Cache** — returned immediately if the key was already resolved.
    2. **Google Colab userdata** — used when running in a native Colab
       notebook; gracefully skipped if ``google.colab`` is not available.
    3. **Environment variable** — reads from the process environment or any
       ``.env`` file loaded by ``load_dotenv()``.
    4. **Interactive prompt** — falls back to ``getpass.getpass()`` for local
       development in terminals; prints a warning and returns ``""`` if the
       prompt fails (e.g. in a non-interactive CI environment).

    The resolved value is cached so subsequent calls are free.

    Args:
        key_name: The name of the key to retrieve, e.g. ``"GOOGLE_API_KEY"``.

    Returns:
        str: The API key value, or an empty string if all sources failed.
    """
    # 1. Return cached value immediately to avoid redundant lookups.
    if _API_KEYS.get(key_name):
        return _API_KEYS[key_name]

    # 2. Google Colab userdata — only available inside a Colab runtime.
    try:
        from google.colab import userdata  # pyrefly: ignore

        val = userdata.get(key_name)
        if val:
            _API_KEYS[key_name] = val
            return val
    except (ImportError, AttributeError, Exception):
        # Not in Colab, or key not set in Colab secrets — continue to next tier.
        pass

    # 3. Environment variable (covers .env files loaded above).
    val = os.getenv(key_name)
    if val:
        _API_KEYS[key_name] = val
        return val

    # 4. Interactive prompt — only works in a terminal with a TTY.
    try:
        val = getpass.getpass(f"{key_name}: ")
        if val:
            _API_KEYS[key_name] = val
            return val
    except Exception:
        # Silently fail in scripts/CI; the caller will receive an empty string
        # and will raise a clearer error when the API call is actually made.
        print(f"Warning: {key_name} not found and interactive prompt failed.")

    return ""


def __getattr__(name: str) -> str:
    """
    Module-level ``__getattr__`` so that code doing::

        from ai_tools.config import GOOGLE_API_KEY

    still works — Python calls this hook for any attribute not found at
    module level, and we proxy it through ``get_api_key()``.
    """
    if name in _API_KEYS:
        return get_api_key(name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

"""Stateless provider client factory."""

from openai import OpenAI

from . import config as _cfg
from .tracing import get_openai_class


def get_client(model: str) -> OpenAI:
    """Return an OpenAI-compatible client for the given prefixed model name.

    Supports: openai/, gemini/, openrouter/, ollama/
    
    Args:
        model: Full model name with provider prefix (e.g. "gemini/gemini-flash-latest").
    
    Raises:
        ValueError: If the model lacks a recognized provider prefix.
    """
    OpenAIClass = get_openai_class()
    provider, _ = _cfg.strip_provider_prefix(model)

    if provider == "openai":
        return OpenAIClass(api_key=_cfg.get_api_key("OPENAI_API_KEY"))
    elif provider == "ollama":
        return OpenAIClass(base_url=_cfg.OLLAMA_BASE_URL, api_key="ollama")
    elif provider == "gemini":
        return OpenAIClass(
            base_url=_cfg.GEMINI_BASE_URL,
            api_key=_cfg.get_api_key("GOOGLE_API_KEY"),
        )
    elif provider == "openrouter":
        return OpenAIClass(
            base_url=_cfg.OPENROUTER_BASE_URL,
            api_key=_cfg.get_api_key("OPENROUTER_API_KEY"),
        )
    raise ValueError(
        f"Model '{model}' lacks a recognized provider prefix (openai/, ollama/, gemini/, openrouter/)."
    )

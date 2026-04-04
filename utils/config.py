from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Settings(BaseSettings):
    """
    Application configuration via functionality variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # API Keys
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API Key")
    OPENROUTER_API_KEY: Optional[str] = Field(
        default=None, description="OpenRouter API Key"
    )
    GOOGLE_API_KEY: Optional[str] = Field(
        default=None, description="Google Gemini API Key"
    )
    HUGGINGFACE_TOKEN: Optional[str] = Field(
        default=None, description="Hugging Face Token"
    )

    # Model Configuration
    DEFAULT_MODEL: str = Field(
        default="openrouter/xiaomi/mimo-v2-flash",
        description="Default LLM model to use",
    )
    SUB_AGENT_MODEL: str = Field(
        # default="openrouter/openai/gpt-oss-20b",
        # default="openrouter/qwen/qwen3.5-9b",
        default="openrouter/mistralai/mistral-small-2603",
        #default="openrouter/google/gemma-4-26b-a4b-it",
        # default="openrouter/nvidia/nemotron-3-nano-30b-a3b",
        description="Default model for sub-agents",
    )
    EMBEDDING_MODEL: str = Field(
        default="openrouter/qwen/qwen3-embedding-8b",
        description="Embedding model for Vector DB",
    )

    # Paths
    # Using absolute paths from project root
    DATA_RAW_DIR: str = os.path.join(PROJECT_ROOT, "data/raw")
    VECTOR_DB_DIR: str = os.path.join(PROJECT_ROOT, "data/vector_db")
    TECH_DB_PATH: str = os.path.join(PROJECT_ROOT, "data/tech_db/tech.db")
    WEB_SCRAPER_DIR: str = os.path.join(PROJECT_ROOT, "data/web_scraper")

    # UI — models available in the dropdown
    ALLOWED_MODELS: List[str] = Field(
        default=[
            "openrouter/google/gemini-3.1-flash-lite-preview",
            "openrouter/google/gemini-3-flash-preview",
            "openrouter/deepseek/deepseek-v3.2",
            "openrouter/openai/gpt-oss-120b",
            "openrouter/openai/gpt-oss-20b",
            "openrouter/xiaomi/mimo-v2-flash:free",
            "openrouter/x-ai/grok-4.1-fast",
            "openrouter/nvidia/nemotron-3-nano-30b-a3b",
            "openrouter/xiaomi/mimo-v2-flash",
        ],
        description="Models available in the UI dropdown.",
    )


settings = Settings()

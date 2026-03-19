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
    GOOGLE_API_KEY: Optional[str] = Field(
        default=None, description="Google Gemini API Key"
    )
    HUGGINGFACE_TOKEN: Optional[str] = Field(
        default=None, description="Hugging Face Token"
    )

    # Model Configuration
    DEFAULT_MODEL: str = Field(
        default="deepseek/deepseek-v3.2", description="Default LLM model to use"
    )
    SUB_AGENT_MODEL: str = Field(
        default="openai/gpt-oss-20b", description="Default model for sub-agents"
    )
    EMBEDDING_MODEL: str = Field(
        default="qwen/qwen3-embedding-8b", description="Embedding model for Vector DB"
    )

    # Paths
    # Using absolute paths from project root
    DATA_RAW_DIR: str = os.path.join(PROJECT_ROOT, "data/raw")
    VECTOR_DB_DIR: str = os.path.join(PROJECT_ROOT, "data/vector_db")
    TECH_DB_PATH: str = os.path.join(PROJECT_ROOT, "data/tech_db/tech.db")

    # UI — models available in the dropdown
    ALLOWED_MODELS: List[str] = Field(
        default=[
            "deepseek/deepseek-v3.2",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "xiaomi/mimo-v2-flash:free",
            "x-ai/grok-4.1-fast",
            "nvidia/nemotron-3-nano-30b-a3b",
        ],
        description="Models available in the UI dropdown.",
    )


settings = Settings()

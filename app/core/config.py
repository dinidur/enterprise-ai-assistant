"""Central application configuration.

Every environment variable in the project is declared here exactly once.
No other module should call ``os.getenv`` directly: importing ``settings``
is the single source of truth, which makes configuration testable and keeps
secrets out of business logic.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Enterprise AI Assistant"
    app_env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"

    # --- LLM ---
    # Gemini is used because its free tier needs no credit card and allows
    # ~1,500 requests/day, which is ample for a POC and a recorded demo.
    google_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    llm_fallback_model: str = "gemini-2.0-flash"
    llm_temperature: float = 0.0

    # --- Embeddings ---
    # Embeddings run locally through fastembed (ONNX). Local inference means no
    # API quota is consumed during ingestion or at query time, and no torch
    # dependency, so the container stays small.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    # --- Vector database ---
    pinecone_api_key: str = ""
    pinecone_index: str = "enterprise-kb"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # --- Observability ---
    langsmith_tracing: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "enterprise-ai-assistant"

    # --- Rate limiting (token bucket) ---
    rate_limit_capacity: int = Field(default=20, ge=1)
    rate_limit_refill_per_second: float = Field(default=0.5, gt=0)

    # --- Retrieval ---
    retrieval_top_k: int = Field(default=8, ge=1)
    retrieval_candidate_k: int = Field(default=20, ge=1)


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance.

    Cached so the ``.env`` file is parsed once per process, and so tests can
    override the dependency cleanly.
    """
    return Settings()


settings = get_settings()

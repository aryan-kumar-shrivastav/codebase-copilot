"""
Central app configuration, loaded from environment variables / .env.

Nothing else in the codebase should call os.environ directly — import
`settings` from here instead, so every config value has one source of truth.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    database_url: str = "postgresql+psycopg2://copilot:copilot@localhost:5432/copilot"

    # --- LLM / embeddings providers ---
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    voyage_api_key: str | None = None

    llm_model: str = "claude-sonnet-4-6"
    embedding_provider: str = "openai"  # "openai" | "voyage"
    embedding_model: str = "text-embedding-3-small"
    embedding_dims: int = 1536

    # --- Chunking ---
    max_chunk_tokens: int = 400
    chunk_overlap_tokens: int = 40

    # --- Retrieval ---
    top_k_vector: int = 12
    top_k_final: int = 6

    # --- Agent ---
    max_agent_steps: int = 8
    sandbox_repo_root: str = "/tmp/copilot_repos"

    # --- Observability ---
    trace_log_path: str = "/tmp/copilot_traces"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

"""Application settings, loaded from environment variables (or a .env file)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General ---
    app_name: str = "Hunger Games Agent API"
    cors_origins: str = "http://localhost:5173"  # comma-separated list

    # --- Database (PostgreSQL + pgvector) ---
    database_url: str = "postgresql+psycopg://hga:hga@localhost:5432/hga"

    # --- Auth (Keycloak) ---
    # Issuer exactly as it appears in the token's "iss" claim (public URL).
    keycloak_issuer: str = "http://localhost:8080/realms/hunger-games"
    # Where the backend downloads the signing keys (can be an internal URL).
    keycloak_jwks_url: str = ""
    keycloak_audience: str = "hga-api"
    admin_role: str = "admin"

    # --- Local LLM (Ollama) ---
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:3b"
    llm_temperature: float = 0.0
    llm_num_ctx: int = 4096

    # --- Embeddings (Sentence Transformers, runs locally) ---
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384

    # --- RAG / hallucination control ---
    chunk_size: int = 900
    chunk_overlap: int = 150
    retrieval_top_k: int = 6
    # Minimum cosine similarity a chunk needs to be used as context.
    similarity_threshold: float = 0.80
    history_turns: int = 4  # previous user/assistant pairs sent to the LLM

    # --- Uploads ---
    max_upload_mb: int = 50

    @property
    def jwks_url(self) -> str:
        return self.keycloak_jwks_url or f"{self.keycloak_issuer}/protocol/openid-connect/certs"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

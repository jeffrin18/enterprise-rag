"""
Central application configuration.
All values are overridable via environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "Agentic Enterprise Knowledge Graph & Multi-Source RAG Pipeline"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- LLM Provider ---
    # Any Anthropic/OpenAI-compatible provider works; default targets Anthropic.
    LLM_PROVIDER: str = "anthropic"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIM: int = 1536

    # --- Neo4j (Knowledge Graph) ---
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "changeme12345"
    NEO4J_DATABASE: str = "neo4j"

    # --- Qdrant (Vector DB) ---
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "enterprise_docs"

    # --- Structured / SQL source (optional third retrieval branch) ---
    SQL_DATABASE_URL: str = "sqlite:///./structured_data.db"

    # --- Chunking ---
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120

    # --- Self-correction loop ---
    MAX_SELF_CORRECTION_LOOPS: int = 2
    FAITHFULNESS_THRESHOLD: float = 0.7
    CONTEXT_RECALL_THRESHOLD: float = 0.6

    # --- Guardrails ---
    ENABLE_PII_MASKING: bool = True
    ENABLE_PROMPT_INJECTION_DETECTION: bool = True

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""
Central configuration, read once from environment variables / .env.
Using pydantic-settings means every setting is typed and validated at
startup instead of failing halfway through a request.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Data layer ---
    database_url: str = "postgresql+asyncpg://civicpulse:civicpulse@localhost:5432/civicpulse"

    # --- Cache layer ---
    redis_url: str = "redis://localhost:6379/0"
    stats_cache_ttl: int = 30          # seconds, per §2.4 Job 1
    triage_cache_ttl: int = 86400      # 24h, per §2.5 point 5
    rate_limit_per_minute: int = 20    # per §2.4 Job 2

    # --- AI layer ---
    triage_provider: str = "simulated"  # llm | ollama | rules | simulated
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-20b"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"

    # --- Misc ---
    log_level: str = "INFO"
    cors_allow_origins: str = "*"  # comma-separated in prod


@lru_cache
def get_settings() -> Settings:
    return Settings()

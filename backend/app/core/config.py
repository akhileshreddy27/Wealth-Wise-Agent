from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'wealthwise.db'}"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:5173"
    enable_scheduler: bool = False      # daily market-data refresh inside the API process
    risk_free_rate: float = 0.065       # used for Sharpe / Sortino

    # Phase 5 AI layer. Any OpenAI-compatible provider works; Groq has a free tier.
    llm_provider: str = "groq"          # groq | ollama | openrouter | gemini | none
    llm_model: str = ""                 # blank = the provider's default (see agents/llm.py)
    llm_base_url: str = ""              # blank = the provider's default
    llm_api_key: str = ""               # or the provider-specific variable below
    groq_api_key: str = ""
    llm_categorize: bool = True         # ask the LLM about transactions the keyword rules can't place

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

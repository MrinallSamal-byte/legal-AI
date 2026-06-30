"""Central configuration: settings, the swappable model registry, and tier policy."""
from __future__ import annotations

from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: str = "change-me-in-production"
    jwt_alg: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    min_password_length: int = 8

    database_url: str = "sqlite:///./lexa.db"
    auto_create_tables: bool = True   # dev convenience; set False in prod (use Alembic)
    vector_store_path: str = "./data/vectorstore"

    free_tier_quota: int = 5
    free_tier_window_hours: int = 24

    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    cors_origins: str = "*"

    llm_provider: str = "mock"
    request_timeout_seconds: float = 60.0
    max_provider_retries: int = 2
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    embeddings_backend: str = "hashing"
    embeddings_model: str = "all-MiniLM-L6-v2"
    embeddings_dim: int = 256

    courtlistener_token: str = ""

    # --- email (verification + password reset) ---
    app_base_url: str = "http://localhost:8000"
    email_backend: str = "console"   # "console" (dev, logs) | "smtp"
    email_from: str = "no-reply@lexa.legal"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    email_token_hours: int = 24

    # --- grounding / abstention thresholds (cosine sim) ---
    grounding_floor: float = 0.12    # below this top score -> abstain
    grounding_strong: float = 0.30   # at/above this -> grounded on score alone
    free_tier_allow_escalation: bool = False

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()


@dataclass(frozen=True)
class ModelSpec:
    key: str
    provider: str
    model_id: str
    input_cost: float
    output_cost: float
    context_window: int
    tier_label: str


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "oss-flash": ModelSpec("oss-flash", "google",    "gemini-flash-class",   0.10, 0.40, 1_000_000, "cheap"),
    "oss-local": ModelSpec("oss-local", "oss",       "open-source-reasoner", 0.0,  0.0,    128_000, "cheap"),
    "mid":       ModelSpec("mid",       "openai",    "gpt-mid-class",        1.00, 4.00,    200_000, "mid"),
    "premium-a": ModelSpec("premium-a", "anthropic", "opus-class",           5.00, 25.0,    200_000, "premium"),
    "premium-o": ModelSpec("premium-o", "openai",    "gpt-premium-class",    5.00, 20.0,    400_000, "premium"),
}


@dataclass(frozen=True)
class TierPolicy:
    name: str
    quota: int
    window_hours: int
    default_model: str
    verifier_model: str
    allow_model_choice: bool


TIERS: dict[str, TierPolicy] = {
    "free": TierPolicy("free", settings.free_tier_quota, settings.free_tier_window_hours,
                       "oss-flash", "oss-flash", allow_model_choice=False),
    "plus": TierPolicy("plus", 100, 24, "mid", "premium-a", allow_model_choice=False),
    "pro":  TierPolicy("pro", -1, 24, "premium-a", "premium-o", allow_model_choice=True),
}

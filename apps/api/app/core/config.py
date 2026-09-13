"""Centralized application settings, loaded from environment variables.

Never hardcode a secret here — this module only defines shape and defaults;
actual values come from `.env` locally or AWS Secrets Manager / ECS task
secrets in deployed environments.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Core ---
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    secret_key: str = Field(default="dev-only-not-secure")
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://wealth_advisor:wealth_advisor@localhost:5432/wealth_advisor"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- S3 ---
    aws_region: str = Field(default="ap-south-1")
    s3_bucket_statements: str = Field(default="ai-wealth-advisor-statements")
    s3_bucket_reports: str = Field(default="ai-wealth-advisor-reports")

    # --- Auth (Cognito) ---
    cognito_user_pool_id: str = Field(default="")
    cognito_app_client_id: str = Field(default="")
    cognito_region: str = Field(default="ap-south-1")
    jwt_algorithm: str = Field(default="RS256")

    # --- Market data ---
    amfi_nav_url: str = Field(default="https://www.amfiindia.com/spages/NAVAll.txt")

    # --- LLM ---
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-5.5")
    openai_embedding_model: str = Field(default="text-embedding-3-large")

    # --- Business rules / thresholds ---
    recommendation_confidence_floor: float = 0.55
    expense_ratio_outlier_std_devs: float = 2.0
    overlap_warning_threshold_pct: float = 40.0
    risk_free_rate_annual_pct: float = 6.75  # India 10Y G-Sec proxy, override via env in prod

    # --- Notifications ---
    ses_from_email: str = Field(default="alerts@aiwealthadvisor.app")
    whatsapp_business_api_token: str = Field(default="")
    fcm_server_key: str = Field(default="")

    # --- Rate limiting ---
    rate_limit_per_minute_user: int = 100
    rate_limit_per_minute_ip: int = 500

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()

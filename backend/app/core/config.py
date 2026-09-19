"""
Application configuration module using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

from functools import lru_cache
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    """Core application settings with environment variable bindings."""

    # Application settings
    app_name: str = Field(default="Paytm MerchantMind API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    debug: bool = Field(default=True, alias="DEBUG")

    # CORS settings
    cors_origins: Union[List[str], str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"]

    # Database settings
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/merchantmind",
        alias="DATABASE_URL"
    )
    db_echo: bool = Field(default=False, alias="DB_ECHO")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")

    # Demo & Synthetic Data settings
    demo_merchant_id: str = Field(default="demo-merchant-001", alias="DEMO_MERCHANT_ID")
    seed_random_seed: int = Field(default=42, alias="SEED_RANDOM_SEED")
    data_mode: str = Field(default="postgres", alias="DATA_MODE")

    # AI / LLM settings
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gemini-1.5-flash", alias="LLM_MODEL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")

    # Cognee Cloud — AI Memory Layer
    cognee_api_key: str = Field(default="", alias="COGNEE_API_KEY")
    cognee_base_url: str = Field(default="https://your-tenant.aws.cognee.ai", alias="COGNEE_BASE_URL")
    cognee_tenant_id: str = Field(default="", alias="COGNEE_TENANT_ID")
    cognee_user_id: str = Field(default="", alias="COGNEE_USER_ID")

    # n8n — Campaign Delivery Automation
    n8n_webhook_url: str = Field(default="", alias="N8N_WEBHOOK_URL")
    # Optional: only sent when explicitly configured; n8n webhook may run without auth
    n8n_webhook_secret: str = Field(default="", alias="N8N_WEBHOOK_SECRET")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()

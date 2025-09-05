"""Application configuration using Pydantic Settings"""


from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/groupchat"
    )

    # Redis
    redis_url: RedisDsn | None = Field(
        default="redis://localhost:6379/0"
    )

    # OpenAI
    openai_api_key: str | None = Field(default=None)

    # Twilio
    twilio_account_sid: str | None = Field(default=None)
    twilio_auth_token: str | None = Field(default=None)
    twilio_phone_number: str | None = Field(default=None)
    twilio_webhook_url: str | None = Field(default=None)

    # Stripe
    stripe_secret_key: str | None = Field(default=None)
    stripe_webhook_secret: str | None = Field(default=None)

    # Application
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=True)
    app_secret_key: str = Field(default="change-me-in-production")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)

    # Security
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_hours: int = Field(default=24)

    # Feature Flags
    enable_sms: bool = Field(default=False)
    enable_payments: bool = Field(default=False)
    enable_real_embeddings: bool = Field(default=False)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    # Micropayment Configuration
    query_price_cents: float = Field(default=0.5)  # Half a cent per query
    contributor_pool_percentage: float = Field(default=0.7)  # 70% to contributors
    platform_percentage: float = Field(default=0.2)  # 20% to platform
    referrer_percentage: float = Field(default=0.1)  # 10% to referrers

    # Matching Algorithm Weights
    embedding_weight: float = Field(default=0.45)
    tag_overlap_weight: float = Field(default=0.20)
    trust_score_weight: float = Field(default=0.15)
    availability_weight: float = Field(default=0.10)
    responsiveness_weight: float = Field(default=0.10)


settings = Settings()

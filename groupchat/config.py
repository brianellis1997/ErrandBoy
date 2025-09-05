"""Application configuration using Pydantic Settings"""


from pydantic import Field, PostgresDsn, RedisDsn, field_validator
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

    @field_validator('twilio_phone_number')
    @classmethod
    def validate_twilio_phone_number(cls, v):
        """Validate Twilio phone number format"""
        if v is not None and not v.startswith('+'):
            raise ValueError('Twilio phone number must start with +')
        return v

    def is_sms_configured(self) -> bool:
        """Check if SMS/Twilio is properly configured"""
        return all([
            self.enable_sms,
            self.twilio_account_sid,
            self.twilio_auth_token,
            self.twilio_phone_number
        ])

    def is_payments_configured(self) -> bool:
        """Check if payments/Stripe is properly configured"""
        return all([
            self.enable_payments,
            self.stripe_secret_key,
            self.stripe_webhook_secret
        ])

    def validate_configuration(self) -> dict[str, list[str]]:
        """Validate configuration and return any issues"""
        issues = {"errors": [], "warnings": []}
        
        # SMS configuration validation
        if self.enable_sms:
            if not self.twilio_account_sid:
                issues["errors"].append("SMS enabled but twilio_account_sid not configured")
            if not self.twilio_auth_token:
                issues["errors"].append("SMS enabled but twilio_auth_token not configured")
            if not self.twilio_phone_number:
                issues["errors"].append("SMS enabled but twilio_phone_number not configured")
            elif not self.twilio_phone_number.startswith('+'):
                issues["errors"].append("twilio_phone_number must start with +")
        
        # Payment configuration validation
        if self.enable_payments:
            if not self.stripe_secret_key:
                issues["errors"].append("Payments enabled but stripe_secret_key not configured")
            if not self.stripe_webhook_secret:
                issues["errors"].append("Payments enabled but stripe_webhook_secret not configured")
        
        # Percentage validation
        total_percentage = (
            self.contributor_pool_percentage + 
            self.platform_percentage + 
            self.referrer_percentage
        )
        if abs(total_percentage - 1.0) > 0.01:  # Allow small floating point differences
            issues["errors"].append(f"Payment percentages must sum to 1.0, got {total_percentage}")
        
        # Matching weights validation
        total_weight = (
            self.embedding_weight + 
            self.tag_overlap_weight + 
            self.trust_score_weight + 
            self.availability_weight + 
            self.responsiveness_weight
        )
        if abs(total_weight - 1.0) > 0.01:
            issues["warnings"].append(f"Matching weights should sum to 1.0, got {total_weight}")
        
        # Security warnings
        if self.app_env == "production":
            if self.app_debug:
                issues["warnings"].append("Debug mode enabled in production")
            if self.app_secret_key == "change-me-in-production":
                issues["errors"].append("Default secret key used in production")
            if self.jwt_secret_key == "change-me-in-production":
                issues["errors"].append("Default JWT secret key used in production")
        
        return issues


settings = Settings()

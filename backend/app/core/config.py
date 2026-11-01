"""Application configuration and validation."""

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_SECRET_LENGTH = 32
PLACEHOLDERS = ("dev-", "placeholder", "your-", "localhost")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT_SECONDS: int = 30

    # CORS - bypass JSON decoding so parse_cors_origins receives comma-separated string
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Database
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/civicmesh")

    # Supabase Auth
    SUPABASE_URL: str = Field(default="https://localhost.supabase.co")
    SUPABASE_JWT_SECRET: str = Field(default="dev-supabase-jwt-secret-placeholder")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="dev-supabase-service-role-key-placeholder")

    # Storage Buckets
    STORAGE_EVIDENCE_BUCKET: str = "civicmesh-evidence"
    STORAGE_DOCUMENTS_BUCKET: str = "civicmesh-sources"

    # Pilot Locality
    PILOT_LOCALITY_NAME: str = "Pilot-Ward-1"
    PILOT_LATITUDE: float = Field(default=28.6139, ge=-90.0, le=90.0)
    PILOT_LONGITUDE: float = Field(default=77.2090, ge=-180.0, le=180.0)
    PILOT_RADIUS_METERS: float = Field(default=5000.0, gt=0)

    # Worker & AI
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash")
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    WORKER_MAX_RETRIES: int = 3

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(o).strip() for o in parsed if str(o).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            for name, secret in [
                ("SUPABASE_JWT_SECRET", self.SUPABASE_JWT_SECRET),
                ("SUPABASE_SERVICE_ROLE_KEY", self.SUPABASE_SERVICE_ROLE_KEY),
            ]:
                if not secret or len(secret.strip()) < MIN_SECRET_LENGTH:
                    raise ValueError(
                        f"{name} must be at least {MIN_SECRET_LENGTH} characters in production."
                    )
                if any(p in secret.lower() for p in PLACEHOLDERS):
                    raise ValueError(
                        f"{name} contains prohibited placeholder in production."
                    )
        return self

    def is_configured_for_production(self) -> bool:
        """Check if production environment has required non-default secrets."""
        for secret in [self.SUPABASE_JWT_SECRET, self.SUPABASE_SERVICE_ROLE_KEY]:
            if not secret or len(secret.strip()) < MIN_SECRET_LENGTH:
                return False
            if any(p in secret.lower() for p in PLACEHOLDERS):
                return False
        return True


@lru_cache
def get_settings() -> Settings:
    return Settings()

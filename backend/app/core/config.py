from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    cors_origins: list[str] = ["http://localhost:3000"]
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_service_role_key: str | None = None
    database_url: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    embedding_dimensions: int = 768

    @field_validator("cors_origins")
    @classmethod
    def explicit_origins(cls, origins):
        from urllib.parse import urlsplit

        for origin in origins:
            url = urlsplit(origin)
            if url.scheme not in ("http", "https") or not url.netloc or url.path or "*" in origin:
                raise ValueError("CORS requires explicit HTTP(S) origins without paths")
        return origins

    @field_validator("supabase_url")
    @classmethod
    def trusted_auth_url(cls, value):
        if value:
            from urllib.parse import urlsplit

            url = urlsplit(value)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.query
                or url.fragment
            ):
                raise ValueError("SUPABASE_URL must be an HTTPS project URL")
        return value.rstrip("/") if value else None

    @field_validator("database_url")
    @classmethod
    def psycopg_url(cls, value):
        if value and not value.startswith("postgresql+psycopg://"):
            raise ValueError("Use postgresql+psycopg:// for SQLAlchemy")
        return value

    @field_validator("embedding_dimensions")
    @classmethod
    def migration_dimension(cls, value):
        if value != 768:
            raise ValueError("Changing embedding dimensions requires a coordinated migration")
        return value


@lru_cache
def get_settings():
    return Settings()

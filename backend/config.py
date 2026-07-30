from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_base_url: str = Field(default="http://127.0.0.1:8000", alias="APP_BASE_URL")
    session_cookie_name: str = Field(default="humanbulb_session", alias="SESSION_COOKIE_NAME")
    session_refresh_cookie_name: str = Field(default="humanbulb_refresh", alias="SESSION_REFRESH_COOKIE_NAME")
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")

    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_anon_key: str = Field(alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_bucket_uploads: str = Field(default="portal-uploads", alias="SUPABASE_BUCKET_UPLOADS")
    supabase_bucket_reports: str = Field(default="portal-reports", alias="SUPABASE_BUCKET_REPORTS")
    database_url: str = Field(alias="DATABASE_URL")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-mini", alias="OPENAI_MODEL")

    max_upload_size_mb: int = Field(default=15, alias="MAX_UPLOAD_SIZE_MB")
    allowed_image_types: str = Field(default=".png,.jpg,.jpeg,.webp", alias="ALLOWED_IMAGE_TYPES")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

from pathlib import Path

from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Validated environment configuration. Secrets are never included in reprs."""

    DATABASE_URL: str
    JWT_SECRET_KEY: SecretStr
    JWT_EXPIRE_HOURS: int = Field(default=24, ge=1, le=168)
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    APP_ENV: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    BUSINESS_TIMEZONE: str = "Asia/Shanghai"
    LLM_API_KEY: SecretStr | None = None
    LLM_MODEL: str | None = None
    LLM_BASE_URL: str | None = None
    SILICONFLOW_EMBEDDING_API_KEY: SecretStr | None = None
    EMBEDDING_MODEL: str = "Qwen/Qwen3-VL-Embedding-8B"
    EMBEDDING_DIMENSIONS: int = Field(default=4096, ge=1)
    RAG_MIN_SIMILARITY: float = Field(default=0.15, ge=-1.0, le=1.0)
    UPLOAD_MAX_BYTES: int = Field(default=10 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    AGENT_REQUEST_TIMEOUT_SECONDS: int = Field(default=60, ge=1, le=300)

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.strip() or "123456" in value:
            raise ValueError("DATABASE_URL must be set to a non-default database URL")
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.APP_ENV.lower() in {"production", "prod"}:
            secret = self.JWT_SECRET_KEY.get_secret_value()
            if len(secret) < 32 or secret.lower() in {"changeme", "secret", "password"}:
                raise ValueError("JWT_SECRET_KEY must contain at least 32 characters in production")
            if not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS:
                raise ValueError("Production CORS_ORIGINS must list explicit origins")
        return self


settings = Settings()

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = settings.UPLOAD_MAX_BYTES
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx",
    ".xls", ".xlsx", ".zip",
}

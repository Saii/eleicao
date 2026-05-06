from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DB_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/campanha_ac"
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MIN: int = 480
    API_CORS_ORIGINS: str = "http://localhost:8501"


settings = Settings()

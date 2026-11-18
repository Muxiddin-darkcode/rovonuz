"""
ROVON.UZ - Core Application Settings & Configuration
Loaded via Pydantic BaseSettings from .env or environment variables.
"""

from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ROVON.UZ Media Intelligence"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "rovon-default-secret-key-change-in-prod"

    # Database (Defaults to local zero-config SQLite, switchable to PostgreSQL via .env)
    DATABASE_URL: str = "sqlite+aiosqlite:///./rovon_media.db"

    # Redis (Event Bus & Distributed Locks)
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI Models
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_EDITORIAL_MODEL: str = "gemini-3.5-flash-lite"
    OPENAI_API_KEY: Optional[str] = None

    # Search API
    TAVILY_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_CX: Optional[str] = None

    # Telegram Bot & Channel
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHANNEL_ID: str = "@rovonuz"
    TELEGRAM_ADMIN_CHAT_ID: Optional[int] = None

    # Telethon MTProto Observer
    TELEGRAM_API_ID: Optional[int] = None
    TELEGRAM_API_HASH: Optional[str] = None
    TELEGRAM_SESSION_NAME: str = "rovon_observer_session"

    @field_validator("TELEGRAM_API_ID", "TELEGRAM_ADMIN_CHAT_ID", mode="before")
    @classmethod
    def validate_optional_int(cls, v):
        if v is None or not str(v).strip().isdigit():
            return None
        return int(v)

    # Media Templates & Assets
    FONT_PATH_BOLD: str = "app/media_studio/templates/fonts/Inter-Bold.ttf"
    FONT_PATH_REGULAR: str = "app/media_studio/templates/fonts/Inter-Regular.ttf"
    ROVON_LOGO_PATH: str = "app/media_studio/templates/branding/rovon_logo.png"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

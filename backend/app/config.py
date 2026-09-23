from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "GeneSense AI Core"
    app_env: str = "development"
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'healthpredict.db'}"
    ai_provider: str = "google"
    google_ai_api_key: str | None = None
    google_ai_model: str = "gemini-3.6-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_vision_model: str = "gpt-5-mini"
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    app_base_url: str = "http://localhost:8000"
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = ""
    enable_demo_login: bool = True

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.session_secret)

    @property
    def ai_enabled(self) -> bool:
        provider = self.ai_provider.strip().lower()
        return bool(
            (provider == "google" and self.google_ai_api_key)
            or (provider == "openai" and self.openai_api_key)
        )

    @property
    def ai_provider_label(self) -> str:
        return "Google Gemini" if self.ai_provider.strip().lower() == "google" else "OpenAI"

    @property
    def secure_cookies(self) -> bool:
        return urlsplit(self.app_base_url).scheme == "https"

    @property
    def demo_enabled(self) -> bool:
        return self.app_env == "development" and self.enable_demo_login and urlsplit(self.app_base_url).hostname in {"localhost", "127.0.0.1"}

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

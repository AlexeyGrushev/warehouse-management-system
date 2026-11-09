from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://wms:wms@localhost:5432/wms"
    test_database_url: str = "postgresql+psycopg://wms:wms@localhost:5432/wms_test"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 60
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me"
    # Как часто фоновая задача освобождает истёкшие резервы (секунды); 0 — не запускать
    reservation_expiry_interval_seconds: float = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://wms:wms@localhost:5432/wms"
    test_database_url: str = "postgresql+psycopg://wms:wms@localhost:5432/wms_test"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAUNCHPAD_", env_file=".env")

    app_name: str = "Acquisition Launchpad API"
    environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://launchpad:launchpad@127.0.0.1:5441/launchpad"
    )
    sql_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

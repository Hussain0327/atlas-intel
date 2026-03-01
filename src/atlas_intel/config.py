"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    database_url: str = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas_intel"

    # SEC EDGAR
    sec_user_agent: str = "AtlasIntel rajahh7865@gmail.com"
    sec_rate_limit: int = 8

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "")


settings = Settings()

"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    database_url: str = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas_intel"

    # SEC EDGAR
    sec_user_agent: str = "AtlasIntel rajahh7865@gmail.com"
    sec_rate_limit: int = 8

    # Financial Modeling Prep
    fmp_api_key: str = ""
    fmp_rate_limit: int = 5

    # NLP
    finbert_model: str = "ProsusAI/finbert"
    nlp_batch_size: int = 32

    # FRED (Federal Reserve Economic Data)
    fred_api_key: str = ""
    fred_rate_limit: int = 100
    fred_series: str = "GDP,UNRATE,DFF,DGS10,CPIAUCSL,HOUST,INDPRO"

    # USPTO PatentsView
    patent_api_key: str = ""
    patent_rate_limit: int = 40

    # LLM — dual provider (Anthropic Claude + OpenAI GPT)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    llm_provider: str = "auto"  # "auto" | "anthropic" | "openai"
    llm_max_tokens: int = 4096
    llm_report_cache_ttl: int = 3600

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "")


settings = Settings()

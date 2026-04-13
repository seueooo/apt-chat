from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_db_url: str
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_model_cheap: str = "claude-haiku-4-5-20251001"
    anthropic_model_good: str = "claude-sonnet-4-6"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.cors_origins.split(",")]


settings = Settings()

import logging
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables (.env)
    """

    database_url: str = "sqlite:///./migration.db"
    analyzer_api_url: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"   # ⭐ Ignore all other env variables


# Global settings instance
settings = Settings()

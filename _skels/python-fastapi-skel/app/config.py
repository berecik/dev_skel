"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    project_name: str = "python-fastapi-skel"
    version: str = "1.0.0"
    debug: bool = True

    database_url: str = "sqlite+aiosqlite:///./app.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

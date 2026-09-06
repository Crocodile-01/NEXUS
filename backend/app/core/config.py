from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "NEXUS"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Database configuration with SQLite async fallback for local dev
    DATABASE_URL: str = "sqlite+aiosqlite:///./nexus.db"

    # Execution Mode: PASSIVE_PUBLIC | AUTHORIZED_SECURITY_ASSESSMENT
    EXECUTION_MODE: str = "PASSIVE_PUBLIC"

    # Security / CORS
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

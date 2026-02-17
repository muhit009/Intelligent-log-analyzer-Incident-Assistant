from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
from pydantic_settings import SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",   # ✅ allow POSTGRES_* etc.
    )

    DATABASE_URL: str = Field(default="postgresql+psycopg2://loguser:logpass@localhost:5432/loganalyzer")

    # Upload constraints
    UPLOAD_DIR: str = Field(default="uploads")
    MAX_UPLOAD_MB: int = Field(default=200)
    ALLOWED_EXTENSIONS: set[str] = {"log", "txt", "json"}
    LOG_LEVEL: str = Field(default="INFO")

    # JWT / Auth
    JWT_SECRET_KEY: str = Field(default="CHANGE-ME-IN-PRODUCTION")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=60)

    # Bootstrap admin
    FIRST_ADMIN_USERNAME: str = Field(default="admin")
    FIRST_ADMIN_PASSWORD: str = Field(default="changeme")

settings = Settings()

def ensure_upload_dir() -> Path:
    p = Path(settings.UPLOAD_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p

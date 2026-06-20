import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # Database Configuration
    # Defaults to a local SQLite database file inside the backend directory
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/spendsnap.db"

    # OCR Configuration
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    
    # Uploads directory
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")
    
    # Allow CORS origins (useful for testing on different hosts/devices)
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql") or self.DATABASE_URL.startswith("postgres")

    @property
    def use_mock_ocr(self) -> bool:
        # If credentials aren't set, use mock OCR for development/testing
        return not self.GOOGLE_APPLICATION_CREDENTIALS

    @property
    def BASE_DIR(self) -> Path:
        return BASE_DIR

settings = Settings()


# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

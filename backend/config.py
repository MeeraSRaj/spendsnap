import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────
    # Defaults to local SQLite; override with a Postgres URL in production.
    # Example: postgresql://user:password@localhost:5432/spendsnap
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/spendsnap.db"

    # ── OCR ───────────────────────────────────────────────────
    # Path to a Google Cloud service-account JSON key file.
    # If not set, the system falls back to Mock OCR (no credentials needed).
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # ── File uploads ──────────────────────────────────────────
    # Directory where uploaded receipt images/PDFs are stored.
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")
    # Maximum allowed upload size in megabytes.
    MAX_UPLOAD_SIZE_MB: int = 10

    # ── Supabase Integration ──────────────────────────────────
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "receipts"
    # Can be overridden in .env. If None, it will dynamically evaluate based on keys.
    USE_MOCK_AUTH: Optional[bool] = None

    # ── CORS ──────────────────────────────────────────────────
    # In development this is open. In production, restrict to your domain(s):
    # CORS_ORIGINS=["https://app.spendsnap.in"]
    CORS_ORIGINS: List[str] = ["http://localhost:8081", "http://127.0.0.1:8081", "http://localhost:3000"]

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
    def use_mock_auth(self) -> bool:
        if self.USE_MOCK_AUTH is not None:
            return self.USE_MOCK_AUTH
        return not (self.SUPABASE_URL and self.SUPABASE_ANON_KEY)

    @property
    def use_mock_storage(self) -> bool:
        return not (self.SUPABASE_URL and self.SUPABASE_SERVICE_ROLE_KEY)

    @property
    def BASE_DIR(self) -> Path:
        return BASE_DIR

settings = Settings()

# Ensure uploads directory exists on startup
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

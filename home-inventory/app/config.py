from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_password: str = "changeme"
    session_secret: str = "dev-secret-not-for-production"
    session_max_age_days: int = 30

    # "local" writes images to local_media_dir and skips all cloud access, so the UI can be
    # developed with no credentials and no network.
    storage_backend: Literal["local", "gcs"] = "local"
    local_media_dir: str = "dev-media"
    media_bucket: str = "my-stuff-inventory-media"

    db_path: str = "dev.sqlite"
    # When set, the database is restored from this bucket on boot and snapshotted back after
    # every write. Empty means purely local, which is what the fast dev loop uses.
    db_bucket: str = ""
    db_object: str = "db/inventory.sqlite"

    gcp_project: str = "my-stuff-inventory"
    # Gemini 3.x is not served from any europe-* region; "global" is required. See research D1.
    gemini_location: str = "global"
    gemini_model: str = "gemini-3.1-flash-lite"
    extract_timeout_seconds: float = 8.0
    # Searching the web takes longer than answering from the prompt alone.
    find_page_timeout_seconds: float = 20.0
    scrape_timeout_seconds: float = 6.0
    max_upload_bytes: int = 20 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

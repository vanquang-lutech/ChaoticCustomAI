from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.constants import BYTES_PER_MB


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-2"
    image_size: str = "1024x1024"
    image_quality: str = "medium"
    # Rewrites a customer's order note into a structured request before the image call. A text
    # model, so the call is cheap and quick next to the image call it decides whether to make.
    modified_request_model: str = "gpt-5-nano"
    # Turn off to send order notes to the image model exactly as the customer wrote them, which
    # is what makes the two paths comparable on real orders.
    normalize_order_notes: bool = True

    # --- Application ---
    app_name: str = "ChaoticCustomAI"
    api_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"
    log_dir: Path = Path("logs")
    timezone: str = "Asia/Ho_Chi_Minh"

    # --- Storage ---
    storage_dir: Path = Path("storage")
    max_upload_files: int = 3
    max_upload_size_mb: int = 10
    # Comma separated rather than a JSON list, so the .env stays readable.
    allowed_image_types: str = "image/png,image/jpeg,image/webp"
    files_url_prefix: str = "/api/v1/files"
    style_presets_dir: Path = Path("assets/text-styles")

    # --- Task queue ---
    # Redis is used only as the Celery broker: a queue, not a datastore. Nothing durable is
    # kept in it -- images, job records and usage all live on disk.
    celery_broker_url: str = "redis://localhost:6379/0"

    @property
    def allowed_content_types(self) -> frozenset[str]:
        return frozenset(
            part.strip() for part in self.allowed_image_types.split(",") if part.strip()
        )

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * BYTES_PER_MB

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def now(self) -> datetime:
        """Current time in the configured zone.

        All date partitioning (storage folders, log filenames, usage rollups) goes through
        here, so a container running with TZ=UTC still files records under the business day
        the operators expect.
        """
        return datetime.now(self.tzinfo)


@lru_cache
def get_settings() -> Settings:
    return Settings()

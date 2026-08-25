"""Custom text: render the user's text in the style of a preset reference image."""

import logging
from pathlib import Path

from src.core.config import Settings
from src.core.enums import Feature, StylePreset
from src.providers.openai.openai_client import ImageResult
from src.schemas.custom_text import CustomTextRequest
from src.schemas.job import JobAccepted, JobRecord
from src.services.gpt_image_service import GptImageService
from src.services.job_service import JobService
from src.services.storage_service import StorageService
from src.taskqueue.client import enqueue
from src.taskqueue.config import TASK_CUSTOM_TEXT

logger = logging.getLogger(__name__)


class CustomTextService:
    def __init__(
        self,
        settings: Settings,
        storage: StorageService,
        jobs: JobService,
        images: GptImageService,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._jobs = jobs
        self._images = images

    def create(self, request: CustomTextRequest) -> JobAccepted:
        # Fail now rather than in the worker if the reference image is missing.
        self._images.style_preset_path(request.style_preset)

        payload = request.model_dump(mode="json")
        record = self._jobs.create(Feature.CUSTOM_TEXT, meta=payload)
        self._storage.save_request(Feature.CUSTOM_TEXT, record.job_id, payload)

        try:
            enqueue(TASK_CUSTOM_TEXT, record.job_id)
        except Exception:
            self._jobs.mark_failed(record, "Could not queue custom text rendering")
            raise

        return JobAccepted(job_id=record.job_id, feature=record.feature, status=record.status)

    def run(self, job_id: str) -> JobRecord:
        def produce(record: JobRecord, _job_dir: Path) -> ImageResult:
            return self._images.render_custom_text(
                text=record.meta["text"],
                preset=StylePreset(record.meta["style_preset"]),
                size=record.meta.get("size"),
                quality=record.meta.get("quality"),
            )

        return self._jobs.execute(job_id, produce)

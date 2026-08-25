"""Generate image: a text description in, a transparent PNG out."""

import logging
from pathlib import Path

from src.core.config import Settings
from src.core.enums import Feature
from src.providers.openai.openai_client import ImageResult
from src.schemas.image import GenerateImageRequest
from src.schemas.job import JobAccepted, JobRecord
from src.services.gpt_image_service import GptImageService
from src.services.job_service import JobService
from src.services.storage_service import StorageService
from src.taskqueue.client import enqueue
from src.taskqueue.config import TASK_GENERATE_IMAGE

logger = logging.getLogger(__name__)


class GenerateImageService:
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

    def create(self, request: GenerateImageRequest) -> JobAccepted:
        record = self._jobs.create(Feature.GENERATE_IMAGE, meta=request.model_dump())
        # The request is stored next to its result so a job folder explains itself later.
        self._storage.save_request(Feature.GENERATE_IMAGE, record.job_id, request.model_dump())

        try:
            enqueue(TASK_GENERATE_IMAGE, record.job_id)
        except Exception:
            self._jobs.mark_failed(record, "Could not queue image generation")
            raise

        return JobAccepted(job_id=record.job_id, feature=record.feature, status=record.status)

    def run(self, job_id: str) -> JobRecord:
        def produce(record: JobRecord, _job_dir: Path) -> ImageResult:
            return self._images.generate_transparent(
                description=record.meta["prompt"],
                size=record.meta.get("size"),
                quality=record.meta.get("quality"),
            )

        return self._jobs.execute(job_id, produce)

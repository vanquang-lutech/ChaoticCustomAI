"""Upload: store what the user sent, optionally strip the background.

One uploaded file becomes one job, so every job folder holds exactly one ``original.*`` and at
most one ``result.png``. That also means a single failing image does not drag the other two
down, and token usage stays attributable per image.
"""

import logging
from pathlib import Path

from fastapi import UploadFile

from src.core.config import Settings
from src.core.constants import ORIGINAL_STEM
from src.core.enums import Feature, JobStatus, StorageKind
from src.core.exceptions import (
    FileTooLargeError,
    TooManyFilesError,
    UnsupportedImageTypeError,
    ValidationError,
)
from src.providers.openai.openai_client import ImageResult
from src.schemas.image import UploadItem, UploadResponse
from src.schemas.job import JobRecord
from src.services.gpt_image_service import GptImageService
from src.services.job_service import JobService
from src.services.storage_service import StorageService
from src.taskqueue.client import enqueue
from src.taskqueue.config import TASK_REMOVE_BACKGROUND
from src.utils.file import extension_for_content_type
from src.utils.hashing import short_sha256
from src.utils.image import probe_image

logger = logging.getLogger(__name__)

_READ_CHUNK = 64 * 1024


class UploadService:
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

    # --- API side ----------------------------------------------------------

    async def handle(self, files: list[UploadFile], remove_background: bool) -> UploadResponse:
        """Validate every file first, then create jobs.

        Validating up front means a request with one oversized file is rejected whole, instead
        of leaving half its images stored and half not.
        """
        self._check_count(files)
        payloads = [await self._read_valid_image(upload) for upload in files]

        items = [
            self._create_item(original_name, content_type, data, remove_background)
            for original_name, content_type, data in payloads
        ]
        return UploadResponse(remove_background=remove_background, items=items)

    def _check_count(self, files: list[UploadFile]) -> None:
        if not files:
            raise ValidationError("At least one image is required")
        if len(files) > self._settings.max_upload_files:
            raise TooManyFilesError(
                "At most " + str(self._settings.max_upload_files) + " images per request"
            )

    async def _read_valid_image(self, upload: UploadFile) -> tuple[str, str, bytes]:
        """Read one upload, enforcing the size cap while reading rather than after."""
        limit = self._settings.max_upload_size_bytes
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await upload.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise FileTooLargeError(
                    "Each image must be at most " + str(self._settings.max_upload_size_mb) + " MB"
                )
            chunks.append(chunk)

        data = b"".join(chunks)
        if not data:
            raise ValidationError("Empty upload: " + (upload.filename or "unnamed"))

        content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if content_type not in self._settings.allowed_content_types:
            raise UnsupportedImageTypeError("Unsupported image type: " + (content_type or "?"))
        # The declared type is client-controlled; decoding the header is what proves it.
        probe_image(data)
        return upload.filename or "unnamed", content_type, data

    def _create_item(
        self,
        original_name: str,
        content_type: str,
        data: bytes,
        remove_background: bool,
    ) -> UploadItem:
        extension = extension_for_content_type(content_type)
        filename = ORIGINAL_STEM + extension

        record = self._jobs.create(
            Feature.UPLOAD,
            meta={
                "original_filename": original_name,
                "content_type": content_type,
                "remove_background": remove_background,
                "input_filename": filename,
                "sha256_short": short_sha256(data),
            },
        )
        self._storage.save_input_bytes(Feature.UPLOAD, record.job_id, filename, data)

        if not remove_background:
            return self._finish_without_processing(record, filename)
        return self._queue_background_removal(record, original_name)

    def _finish_without_processing(self, record: JobRecord, filename: str) -> UploadItem:
        """No OpenAI call is needed, so answer with the stored file straight away.

        The URL points at the input rather than copying identical bytes into ``output/``.
        """
        self._jobs.complete_immediately(record, StorageKind.INPUT, filename)
        path = self._storage.job_dir(Feature.UPLOAD, record.job_id) / "input" / filename
        return UploadItem(
            job_id=record.job_id,
            filename=record.meta.get("original_filename", filename),
            status=JobStatus.SUCCEEDED,
            image=self._storage.image_ref(record.job_id, StorageKind.INPUT, path),
        )

    def _queue_background_removal(self, record: JobRecord, original_name: str) -> UploadItem:
        try:
            enqueue(TASK_REMOVE_BACKGROUND, record.job_id)
        except Exception:
            self._jobs.mark_failed(record, "Could not queue background removal")
            raise
        return UploadItem(
            job_id=record.job_id,
            filename=original_name,
            status=JobStatus.PENDING,
        )

    # --- Worker side -------------------------------------------------------

    def run_remove_background(self, job_id: str) -> JobRecord:
        def produce(record: JobRecord, job_dir: Path) -> ImageResult:
            filename = record.meta.get("input_filename")
            if not filename:
                raise ValidationError("Job " + job_id + " has no input filename")
            source = job_dir / StorageKind.INPUT.value / filename
            if not source.is_file():
                raise ValidationError("Input image is missing: " + str(source))
            return self._images.remove_background(source)

        return self._jobs.execute(job_id, produce)

"""Job lifecycle: create, persist, run, report.

``job.json`` inside the job folder is the durable record. Redis is only Celery's message broker,
so the polling API never depends on Redis and history survives a Redis restart.

``execute`` is the shared spine of all three features: every feature differs only in how it
produces an image, so status transitions, output writing, usage recording and error capture
are implemented once here.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from src.core.config import Settings
from src.core.constants import JOB_RECORD_FILENAME, RESULT_FILENAME
from src.core.enums import Feature, JobStatus, StorageKind
from src.core.exceptions import JobNotFoundError
from src.providers.openai.openai_client import ImageResult
from src.schemas.job import JobRecord, JobResponse
from src.services.storage_service import StorageService
from src.services.usage_service import UsageService
from src.utils.file import read_json, write_json
from src.utils.ids import new_job_id

logger = logging.getLogger(__name__)

# Given a job record and its folder, produce the image. Implemented per feature.
ImageProducer = Callable[[JobRecord, Path], ImageResult]


class JobService:
    def __init__(self, settings: Settings, storage: StorageService, usage: UsageService) -> None:
        self._settings = settings
        self._storage = storage
        self._usage = usage

    # --- Persistence -------------------------------------------------------

    def create(self, feature: Feature, meta: dict | None = None) -> JobRecord:
        record = JobRecord(
            job_id=new_job_id(self._settings.now()),
            feature=feature,
            status=JobStatus.PENDING,
            created_at=self._settings.now(),
            meta=meta or {},
        )
        self._storage.job_dir(feature, record.job_id, create=True)
        self.save(record)
        logger.info("Created %s job %s", feature.value, record.job_id)
        return record

    def save(self, record: JobRecord) -> None:
        path = (
            self._storage.job_dir(record.feature, record.job_id, create=True) / JOB_RECORD_FILENAME
        )
        write_json(path, record.model_dump(mode="json"))

    def load(self, job_id: str) -> JobRecord:
        feature, job_dir = self._storage.find_job_dir(job_id)
        path = job_dir / JOB_RECORD_FILENAME
        if not path.is_file():
            raise JobNotFoundError("Job record missing for " + job_id)
        record = JobRecord.model_validate(read_json(path))
        if record.feature != feature:
            # The folder is authoritative; a mismatch means the file was hand-edited.
            logger.warning(
                "Job %s records feature %s but lives under %s",
                job_id,
                record.feature.value,
                feature.value,
            )
        return record

    # --- Running -----------------------------------------------------------

    def execute(self, job_id: str, produce: ImageProducer) -> JobRecord:
        """Run a queued job to completion, recording whatever happened.

        Called from the Celery worker. Failures are written to ``job.json`` first and then
        re-raised, so the client sees a ``failed`` job and the worker log keeps the traceback.
        """
        record = self.load(job_id)
        job_dir = self._storage.job_dir(record.feature, job_id)

        record.status = JobStatus.RUNNING
        record.started_at = self._settings.now()
        self.save(record)

        try:
            result = produce(record, job_dir)
        except Exception as exc:
            record.status = JobStatus.FAILED
            record.finished_at = self._settings.now()
            record.error = str(exc)
            self.save(record)
            logger.exception("Job %s failed", job_id)
            raise

        self._storage.save_output_bytes(record.feature, job_id, result.data)
        self._usage.record(job_id, record.feature, result.usage)

        record.status = JobStatus.SUCCEEDED
        record.finished_at = self._settings.now()
        record.usage = result.usage
        record.result_kind = StorageKind.OUTPUT.value
        record.result_filename = RESULT_FILENAME
        self.save(record)
        logger.info("Job %s succeeded", job_id)
        return record

    def complete_immediately(
        self, record: JobRecord, kind: StorageKind, filename: str
    ) -> JobRecord:
        """Finish a job that needed no OpenAI call.

        Used by uploads with ``remove_background=false``: the stored input already is the
        deliverable, so it is pointed at directly instead of copying the bytes.
        """
        record.status = JobStatus.SUCCEEDED
        record.started_at = record.started_at or self._settings.now()
        record.finished_at = self._settings.now()
        record.result_kind = kind.value
        record.result_filename = filename
        self.save(record)
        return record

    # --- Reporting ---------------------------------------------------------

    def to_response(self, record: JobRecord) -> JobResponse:
        images = []
        if record.result_filename and record.result_kind:
            kind = StorageKind(record.result_kind)
            path = (
                self._storage.job_dir(record.feature, record.job_id)
                / kind.value
                / record.result_filename
            )
            if path.is_file():
                images.append(self._storage.image_ref(record.job_id, kind, path))
            else:
                logger.warning("Job %s points at a missing file %s", record.job_id, path)
        return JobResponse(
            job_id=record.job_id,
            feature=record.feature,
            status=record.status,
            created_at=record.created_at,
            finished_at=record.finished_at,
            images=images,
            usage=record.usage,
            error=record.error,
        )

    def mark_failed(self, record: JobRecord, message: str) -> JobRecord:
        """Record a failure that happened before a worker ever saw the job."""
        record.status = JobStatus.FAILED
        record.finished_at = self._settings.now()
        record.error = message
        self.save(record)
        logger.error("Job %s failed before execution: %s", record.job_id, message)
        return record

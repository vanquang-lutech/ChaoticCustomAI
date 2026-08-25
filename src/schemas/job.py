"""Job records. ``JobRecord`` is what lands in ``job.json``; ``JobResponse`` is what the API
returns."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.core.enums import Feature, JobStatus
from src.schemas.common import ImageRef
from src.schemas.usage import TokenUsage


class JobRecord(BaseModel):
    """Durable, self-describing record stored alongside the job's input and output."""

    job_id: str
    feature: Feature
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    usage: TokenUsage | None = None
    # Which file inside the job folder is the deliverable, and in which sub-folder.
    result_filename: str | None = None
    result_kind: str | None = None
    meta: dict[str, Any] = {}


class JobResponse(BaseModel):
    job_id: str
    feature: Feature
    status: JobStatus
    created_at: datetime
    finished_at: datetime | None = None
    images: list[ImageRef] = []
    usage: TokenUsage | None = None
    error: str | None = None


class JobAccepted(BaseModel):
    """202 body: the work is queued, poll ``GET /jobs/{job_id}``."""

    job_id: str
    feature: Feature
    status: JobStatus

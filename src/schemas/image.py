"""Request and response models for the upload and generate-image features."""

from typing import Literal

from pydantic import BaseModel, Field

from src.core.enums import JobStatus
from src.schemas.common import ImageRef

ImageSize = Literal["1024x1024", "1536x1024", "1024x1536", "auto"]
ImageQuality = Literal["low", "medium", "high", "auto"]


class GenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    size: ImageSize | None = None
    quality: ImageQuality | None = None


class UploadItem(BaseModel):
    """One uploaded file becomes one job.

    With ``remove_background=false`` nothing needs OpenAI, so ``status`` is already
    ``succeeded`` and ``image`` is filled in. Otherwise ``status`` is ``pending`` and the
    client polls the job.
    """

    job_id: str
    filename: str
    status: JobStatus
    image: ImageRef | None = None


class UploadResponse(BaseModel):
    remove_background: bool
    items: list[UploadItem]

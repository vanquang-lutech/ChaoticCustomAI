"""File serving route.

The URL is keyed by job id, not by storage path, so the directory layout stays internal. Path
validation lives in ``StorageService.resolve_servable``.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from src.core.constants import CONTENT_TYPE_BY_EXTENSION
from src.core.dependencies import get_storage_service
from src.core.enums import StorageKind
from src.services.storage_service import StorageService

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{job_id}/{kind}/{filename}", response_class=FileResponse)
def get_file(
    job_id: str,
    kind: StorageKind,
    filename: str,
    storage: StorageService = Depends(get_storage_service),
) -> FileResponse:
    path = storage.resolve_servable(job_id, kind, filename)
    media_type = CONTENT_TYPE_BY_EXTENSION.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name)

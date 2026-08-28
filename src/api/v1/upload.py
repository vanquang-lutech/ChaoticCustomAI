"""Upload route.

Answers ``200`` when nothing had to be generated and ``202`` when background removal was
queued, so a client can tell from the status code alone whether it needs to poll.
"""

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from src.core.dependencies import get_upload_service
from src.schemas.image import UploadResponse
from src.services.upload_service import UploadService

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=UploadResponse)
async def upload_images(
    response: Response,
    files: list[UploadFile] = File(description="Up to 3 images"),
    remove_background: bool = Form(default=False),
    service: UploadService = Depends(get_upload_service),
) -> UploadResponse:
    result = await service.handle(files, remove_background)
    response.status_code = status.HTTP_202_ACCEPTED if remove_background else status.HTTP_200_OK
    return result

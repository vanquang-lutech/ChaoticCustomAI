"""Generate-image route."""

from fastapi import APIRouter, Depends, status

from src.core.dependencies import get_generate_service
from src.schemas.image import GenerateImageRequest
from src.schemas.job import JobAccepted
from src.services.generate_service import GenerateImageService

router = APIRouter(prefix="/generate-image", tags=["generate-image"])


@router.post("", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def generate_image(
    request: GenerateImageRequest,
    service: GenerateImageService = Depends(get_generate_service),
) -> JobAccepted:
    return service.create(request)

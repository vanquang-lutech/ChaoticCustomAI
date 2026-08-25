"""Custom-text route."""

from fastapi import APIRouter, Depends, status

from src.core.dependencies import get_custom_text_service
from src.core.enums import StylePreset
from src.schemas.custom_text import CustomTextRequest
from src.schemas.job import JobAccepted
from src.services.custom_text_service import CustomTextService

router = APIRouter(prefix="/custom-text", tags=["custom-text"])


@router.get("/styles", response_model=list[str])
def list_style_presets() -> list[str]:
    """The style names accepted by ``POST /custom-text``."""
    return [preset.value for preset in StylePreset]


@router.post("", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_custom_text(
    request: CustomTextRequest,
    service: CustomTextService = Depends(get_custom_text_service),
) -> JobAccepted:
    return service.create(request)

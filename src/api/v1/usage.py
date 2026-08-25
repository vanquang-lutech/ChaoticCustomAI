"""Token usage route. Reports tokens per model and per feature -- never money."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from src.core.config import Settings, get_settings
from src.core.dependencies import get_usage_service
from src.schemas.usage import UsageSummary
from src.services.usage_service import UsageService

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageSummary)
def get_usage(
    date_from: date | None = Query(default=None, description="Defaults to today"),
    date_to: date | None = Query(default=None, description="Defaults to date_from"),
    service: UsageService = Depends(get_usage_service),
    settings: Settings = Depends(get_settings),
) -> UsageSummary:
    start = date_from or settings.now().date()
    return service.summarize(start, date_to or start)

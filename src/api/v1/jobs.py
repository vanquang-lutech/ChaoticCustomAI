"""Job polling route."""

from fastapi import APIRouter, Depends

from src.core.dependencies import get_job_service
from src.schemas.job import JobResponse
from src.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, service: JobService = Depends(get_job_service)) -> JobResponse:
    return service.to_response(service.load(job_id))

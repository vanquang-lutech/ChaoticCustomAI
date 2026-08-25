"""Task: strip the background off an uploaded image."""

import logging

from src.core.dependencies import get_upload_service
from src.taskqueue.client import celery_app
from src.taskqueue.config import TASK_REMOVE_BACKGROUND

logger = logging.getLogger(__name__)


@celery_app.task(name=TASK_REMOVE_BACKGROUND, ignore_result=True)
def remove_background_task(job_id: str) -> dict:
    logger.info("Removing background for job %s", job_id)
    record = get_upload_service().run_remove_background(job_id)
    return {"job_id": record.job_id, "status": record.status.value}

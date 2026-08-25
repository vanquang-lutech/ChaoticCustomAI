"""Task: render the user's text in a preset style."""

import logging

from src.core.dependencies import get_custom_text_service
from src.taskqueue.client import celery_app
from src.taskqueue.config import TASK_CUSTOM_TEXT

logger = logging.getLogger(__name__)


@celery_app.task(name=TASK_CUSTOM_TEXT, ignore_result=True)
def custom_text_task(job_id: str) -> dict:
    logger.info("Rendering custom text for job %s", job_id)
    record = get_custom_text_service().run(job_id)
    return {"job_id": record.job_id, "status": record.status.value}

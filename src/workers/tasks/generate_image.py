"""Task: generate a transparent image from a text description."""

import logging

from src.core.dependencies import get_generate_service
from src.taskqueue.client import celery_app
from src.taskqueue.config import TASK_GENERATE_IMAGE

logger = logging.getLogger(__name__)


@celery_app.task(name=TASK_GENERATE_IMAGE, ignore_result=True)
def generate_image_task(job_id: str) -> dict:
    logger.info("Generating image for job %s", job_id)
    record = get_generate_service().run(job_id)
    return {"job_id": record.job_id, "status": record.status.value}

"""Task: edit a product mock-up to the customer's specification."""

import logging

from src.core.dependencies import get_custom_product_service
from src.taskqueue.client import celery_app
from src.taskqueue.config import TASK_CUSTOM_PRODUCT

logger = logging.getLogger(__name__)


@celery_app.task(name=TASK_CUSTOM_PRODUCT, ignore_result=True)
def custom_product_task(job_id: str) -> dict:
    logger.info("Customising product for job %s", job_id)
    record = get_custom_product_service().run(job_id)
    return {"job_id": record.job_id, "status": record.status.value}

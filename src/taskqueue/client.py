"""Celery producer configured with Redis as a broker only.

Redis transports small job messages from the API to a worker. Task state and results are
deliberately not stored in a Celery result backend: ``job.json`` remains the durable source of
truth used by the polling API.
"""

import logging

from celery import Celery

from src.core.config import get_settings
from src.core.exceptions import QueueUnavailableError
from src.taskqueue.config import TASK_MODULES

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "chaotic_custom_ai",
    broker=settings.celery_broker_url,
    backend=None,
    include=TASK_MODULES,
)
celery_app.conf.update(
    # ``job.json`` is the result store. Keeping Celery results disabled prevents enqueue from
    # blocking while Celery tries to reconnect to a Redis result backend.
    result_backend=None,
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.timezone,
    enable_utc=True,
    task_default_queue="chaotic_custom_ai",
    task_default_delivery_mode=2,
    # Image jobs take much longer than ordinary web requests. Reserve work fairly instead of
    # letting one worker process hold several waiting jobs.
    worker_prefetch_multiplier=1,
    # OpenAI calls are billable and this path is not idempotent yet. Early ACK avoids an
    # automatic duplicate call if a worker dies after OpenAI returns but before acknowledging.
    task_acks_late=False,
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": 3600,
        # Producers should fail quickly enough for the API to return a useful 503.
        "max_retries": 3,
    },
)


def enqueue(task_name: str, job_id: str) -> None:
    """Send a job id to the worker, translating broker failures into an API-safe error."""
    try:
        celery_app.send_task(
            task_name,
            args=[job_id],
            queue="chaotic_custom_ai",
            ignore_result=True,
        )
    except Exception as exc:
        logger.exception("Could not queue task %s for job %s", task_name, job_id)
        raise QueueUnavailableError("Task queue is unavailable") from exc

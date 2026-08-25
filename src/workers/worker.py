"""Celery worker entrypoint.

    celery -A src.workers.worker worker --loglevel=info

The task modules are pulled in through the Celery app's ``include`` setting, so this module
only has to expose the app and set logging up.
"""

from src.core.config import get_settings
from src.core.logging import setup_logging
from src.taskqueue.client import celery_app

setup_logging(get_settings())

# ``celery -A`` looks for an attribute named ``app`` or ``celery``.
app = celery_app

"""Job identifiers.

A job id carries its own creation date -- ``20260825T140344-a3f9c1``. Because the storage
tree is partitioned by month and day, embedding the date means any id can be resolved to its
folder with pure string arithmetic: no Redis lookup, no directory scan, and stored files stay
addressable even if the Celery result backend is wiped.
"""

import secrets
from datetime import date, datetime

from src.core.constants import (
    JOB_ID_PATTERN,
    JOB_ID_RANDOM_LENGTH,
    JOB_ID_TIME_FORMAT,
)
from src.core.exceptions import ValidationError


def new_job_id(now: datetime) -> str:
    suffix = secrets.token_hex(JOB_ID_RANDOM_LENGTH // 2)
    return f"{now.strftime(JOB_ID_TIME_FORMAT)}-{suffix}"


def is_valid_job_id(value: str) -> bool:
    return bool(JOB_ID_PATTERN.match(value))


def job_id_date(job_id: str) -> date:
    """The date encoded in a job id.

    Raises ``ValidationError`` for anything malformed, which is what stops a crafted id from
    ever reaching the filesystem.
    """
    if not is_valid_job_id(job_id):
        raise ValidationError(f"Malformed job id: {job_id!r}")
    return datetime.strptime(job_id.split("-", 1)[0], JOB_ID_TIME_FORMAT).date()

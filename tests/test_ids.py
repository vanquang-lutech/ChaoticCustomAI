"""Job ids must be parseable and unforgeable, because they select a filesystem path."""

from datetime import date, datetime

import pytest

from src.core.exceptions import ValidationError
from src.utils.ids import is_valid_job_id, job_id_date, new_job_id


def test_new_job_id_encodes_its_creation_date():
    job_id = new_job_id(datetime(2026, 8, 25, 14, 3, 44))
    assert job_id.startswith("20260825T140344-")
    assert job_id_date(job_id) == date(2026, 8, 25)
    assert is_valid_job_id(job_id)


def test_ids_are_unique():
    moment = datetime(2026, 8, 25, 14, 3, 44)
    assert len({new_job_id(moment) for _ in range(200)}) > 190


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        "../../etc/passwd",
        "20260825T140344",
        "20260825T140344-ZZZZZZ",
        "20260825T140344-a3f9c1/../..",
        "9999T99-abcdef",
    ],
)
def test_malformed_ids_are_rejected(candidate):
    assert not is_valid_job_id(candidate)
    with pytest.raises(ValidationError):
        job_id_date(candidate)

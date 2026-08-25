"""Storage layout and the path-traversal guard on the file endpoint."""

from datetime import date

import pytest

from src.core.dependencies import get_storage_service
from src.core.enums import Feature, StorageKind
from src.core.exceptions import (
    FileNotFoundInStorageError,
    JobNotFoundError,
    ValidationError,
)


def test_day_dir_is_month_then_day():
    storage = get_storage_service()
    assert storage.day_dir(date(2026, 8, 25)).parts[-2:] == ("2026_08", "2026_08_25")


def test_job_dir_derives_the_date_from_the_job_id():
    storage = get_storage_service()
    path = storage.job_dir(Feature.GENERATE_IMAGE, "20260825T140344-a3f9c1")
    assert path.parts[-4:] == (
        "2026_08",
        "2026_08_25",
        "generate_image",
        "20260825T140344-a3f9c1",
    )


def test_saving_creates_both_subfolders(png_bytes):
    storage = get_storage_service()
    job_id = "20260825T140344-a3f9c1"
    path = storage.save_input_bytes(Feature.UPLOAD, job_id, "original.png", png_bytes)

    assert path.read_bytes() == png_bytes
    job_dir = storage.job_dir(Feature.UPLOAD, job_id)
    assert (job_dir / "input").is_dir()
    assert (job_dir / "output").is_dir()


def test_find_job_dir_locates_the_feature(png_bytes):
    storage = get_storage_service()
    job_id = "20260825T140344-a3f9c1"
    storage.save_input_bytes(Feature.CUSTOM_TEXT, job_id, "original.png", png_bytes)

    feature, path = storage.find_job_dir(job_id)
    assert feature is Feature.CUSTOM_TEXT
    assert path.name == job_id


def test_find_job_dir_rejects_unknown_and_malformed_ids():
    storage = get_storage_service()
    with pytest.raises(JobNotFoundError):
        storage.find_job_dir("20260825T140344-a3f9c1")
    with pytest.raises(JobNotFoundError):
        storage.find_job_dir("../../../.env")


def test_resolve_servable_returns_the_file(png_bytes):
    storage = get_storage_service()
    job_id = "20260825T140344-a3f9c1"
    storage.save_input_bytes(Feature.UPLOAD, job_id, "original.png", png_bytes)

    resolved = storage.resolve_servable(job_id, StorageKind.INPUT, "original.png")
    assert resolved.read_bytes() == png_bytes


@pytest.mark.parametrize(
    "filename",
    ["../../../.env", "..", "../job.json", "sub/dir.png", "a" * 100],
)
def test_resolve_servable_refuses_traversal(png_bytes, filename):
    storage = get_storage_service()
    job_id = "20260825T140344-a3f9c1"
    storage.save_input_bytes(Feature.UPLOAD, job_id, "original.png", png_bytes)

    with pytest.raises(ValidationError):
        storage.resolve_servable(job_id, StorageKind.INPUT, filename)


def test_resolve_servable_404s_for_a_missing_file(png_bytes):
    storage = get_storage_service()
    job_id = "20260825T140344-a3f9c1"
    storage.save_input_bytes(Feature.UPLOAD, job_id, "original.png", png_bytes)

    with pytest.raises(FileNotFoundInStorageError):
        storage.resolve_servable(job_id, StorageKind.OUTPUT, "result.png")


def test_public_url_is_keyed_by_job_id():
    storage = get_storage_service()
    url = storage.public_url("20260825T140344-a3f9c1", StorageKind.OUTPUT, "result.png")
    assert url == "/api/v1/files/20260825T140344-a3f9c1/output/result.png"

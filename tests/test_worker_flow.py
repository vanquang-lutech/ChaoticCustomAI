"""End-to-end through the worker spine, with the OpenAI provider faked out.

Covers the whole path a queued job takes: request -> stored input -> task -> stored output ->
job record -> usage record -> the URL the client finally fetches.
"""

import json

from src.core.dependencies import get_storage_service
from src.core.enums import Feature
from src.services.gpt_image_service import GptImageService
from src.workers.tasks.remove_background import remove_background_task


def test_remove_background_job_runs_to_completion(
    client, monkeypatch, png_bytes, fake_result, no_queue
):
    monkeypatch.setattr(
        GptImageService,
        "remove_background",
        lambda self, image_path, quality=None: fake_result,
    )

    accepted = client.post(
        "/api/v1/upload",
        files=[("files", ("cat.png", png_bytes, "image/png"))],
        data={"remove_background": "true"},
    )
    assert accepted.status_code == 202
    job_id = accepted.json()["items"][0]["job_id"]

    # Before the worker runs, the job is pending and carries no image.
    pending = client.get(f"/api/v1/jobs/{job_id}").json()
    assert pending["status"] == "pending"
    assert pending["images"] == []

    # Run the Celery task body directly.
    assert remove_background_task(job_id=job_id) == {"job_id": job_id, "status": "succeeded"}

    finished = client.get(f"/api/v1/jobs/{job_id}").json()
    assert finished["status"] == "succeeded"
    assert finished["error"] is None
    assert finished["usage"]["total_tokens"] == 33
    assert finished["usage"]["model"] == "gpt-image-test"

    image = finished["images"][0]
    assert image["url"] == f"/api/v1/files/{job_id}/output/result.png"
    served = client.get(image["url"])
    assert served.status_code == 200
    assert served.content == fake_result.data

    storage = get_storage_service()
    job_dir = storage.job_dir(Feature.UPLOAD, job_id)
    assert (job_dir / "input" / "original.png").is_file()
    assert (job_dir / "output" / "result.png").is_file()

    record = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert record["status"] == "succeeded"
    assert record["result_kind"] == "output"
    assert record["result_filename"] == "result.png"

    usage_lines = storage.usage_path(finished_date(finished)).read_text(encoding="utf-8")
    entries = [json.loads(line) for line in usage_lines.splitlines() if line.strip()]
    assert len(entries) == 1
    assert entries[0]["job_id"] == job_id
    assert entries[0]["feature"] == "upload"
    assert entries[0]["total_tokens"] == 33


def test_a_failing_provider_marks_the_job_failed(client, monkeypatch, png_bytes, no_queue):
    def explode(self, image_path, quality=None):
        raise RuntimeError("provider is down")

    monkeypatch.setattr(GptImageService, "remove_background", explode)

    job_id = client.post(
        "/api/v1/upload",
        files=[("files", ("cat.png", png_bytes, "image/png"))],
        data={"remove_background": "true"},
    ).json()["items"][0]["job_id"]

    try:
        remove_background_task(job_id=job_id)
    except RuntimeError:
        pass  # re-raised on purpose so Celery records the failure too
    else:
        raise AssertionError("the task should have re-raised")

    failed = client.get(f"/api/v1/jobs/{job_id}").json()
    assert failed["status"] == "failed"
    assert "provider is down" in failed["error"]
    assert failed["images"] == []


def finished_date(job_payload: dict):
    from datetime import datetime

    return datetime.fromisoformat(job_payload["finished_at"]).date()

"""The two prompt-driven features: both queue a job and persist their request."""

import json

from src.core.dependencies import get_storage_service
from src.core.enums import Feature, StylePreset
from src.services.gpt_image_service import GptImageService
from src.workers.tasks.custom_text import custom_text_task
from src.workers.tasks.generate_image import generate_image_task


def test_generate_image_queues_a_job_and_stores_the_request(client, no_queue):
    response = client.post("/api/v1/generate-image", json={"prompt": "a small cute cat"})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["feature"] == "generate_image"

    assert no_queue == [("chaotic.generate_image", body["job_id"])]

    request_path = (
        get_storage_service().job_dir(Feature.GENERATE_IMAGE, body["job_id"])
        / "input"
        / "request.json"
    )
    assert json.loads(request_path.read_text(encoding="utf-8"))["prompt"] == "a small cute cat"


def test_generate_image_rejects_an_empty_prompt(client, no_queue):
    assert client.post("/api/v1/generate-image", json={"prompt": ""}).status_code == 422


def test_generate_image_runs_and_produces_a_result(client, monkeypatch, fake_result, no_queue):
    monkeypatch.setattr(
        GptImageService,
        "generate_transparent",
        lambda self, description, size=None, quality=None: fake_result,
    )
    job_id = client.post("/api/v1/generate-image", json={"prompt": "a small cute cat"}).json()[
        "job_id"
    ]

    generate_image_task(job_id=job_id)

    finished = client.get(f"/api/v1/jobs/{job_id}").json()
    assert finished["status"] == "succeeded"
    assert finished["images"][0]["url"] == f"/api/v1/files/{job_id}/output/result.png"


def test_style_presets_are_listed(client):
    presets = client.get("/api/v1/custom-text/styles").json()
    assert presets == [preset.value for preset in StylePreset]
    assert "y2k-neon" in presets


def test_custom_text_queues_a_job(client, no_queue):
    response = client.post(
        "/api/v1/custom-text", json={"text": "HELLO", "style_preset": "y2k-neon"}
    )

    assert response.status_code == 202
    body = response.json()
    assert no_queue == [("chaotic.custom_text", body["job_id"])]

    request_path = (
        get_storage_service().job_dir(Feature.CUSTOM_TEXT, body["job_id"])
        / "input"
        / "request.json"
    )
    stored = json.loads(request_path.read_text(encoding="utf-8"))
    assert stored == {
        "text": "HELLO",
        "style_preset": "y2k-neon",
        "size": None,
        "quality": None,
    }


def test_custom_text_rejects_an_unknown_style(client, no_queue):
    response = client.post(
        "/api/v1/custom-text", json={"text": "HELLO", "style_preset": "not-a-style"}
    )
    assert response.status_code == 422


def test_custom_text_runs_with_the_preset_as_the_reference(
    client, monkeypatch, fake_result, no_queue
):
    seen = {}

    def fake_render(self, text, preset, size=None, quality=None):
        seen["text"] = text
        seen["preset"] = preset
        return fake_result

    monkeypatch.setattr(GptImageService, "render_custom_text", fake_render)
    job_id = client.post(
        "/api/v1/custom-text", json={"text": "HELLO", "style_preset": "gold-foil"}
    ).json()["job_id"]

    custom_text_task(job_id=job_id)

    assert seen == {"text": "HELLO", "preset": StylePreset.GOLD_FOIL}
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "succeeded"

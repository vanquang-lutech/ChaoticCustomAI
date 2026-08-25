"""Upload endpoint: validation, the synchronous path, and the queued path."""

from src.core.dependencies import get_storage_service
from src.core.enums import Feature


def test_upload_without_removal_answers_200_and_stores_the_file(client, png_bytes, no_queue):
    response = client.post(
        "/api/v1/upload",
        files=[("files", ("cat.png", png_bytes, "image/png"))],
        data={"remove_background": "false"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["remove_background"] is False
    assert len(body["items"]) == 1

    item = body["items"][0]
    assert item["status"] == "succeeded"
    assert item["filename"] == "cat.png"
    assert item["image"]["url"].endswith("/input/original.png")
    assert item["image"]["width"] == 32
    assert item["image"]["height"] == 24

    # Nothing was queued, because nothing needed OpenAI.
    assert no_queue == []

    stored = (
        get_storage_service().job_dir(Feature.UPLOAD, item["job_id"]) / "input" / "original.png"
    )
    assert stored.read_bytes() == png_bytes


def test_the_returned_url_serves_the_bytes(client, png_bytes, no_queue):
    response = client.post(
        "/api/v1/upload",
        files=[("files", ("cat.png", png_bytes, "image/png"))],
        data={"remove_background": "false"},
    )
    url = response.json()["items"][0]["image"]["url"]

    served = client.get(url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == png_bytes


def test_upload_with_removal_answers_202_and_queues_one_job_per_image(client, png_bytes, no_queue):
    response = client.post(
        "/api/v1/upload",
        files=[
            ("files", ("a.png", png_bytes, "image/png")),
            ("files", ("b.png", png_bytes, "image/png")),
        ],
        data={"remove_background": "true"},
    )

    assert response.status_code == 202
    items = response.json()["items"]
    assert [item["status"] for item in items] == ["pending", "pending"]
    assert [item["image"] for item in items] == [None, None]

    queued_ids = [job_id for _, job_id in no_queue]
    assert queued_ids == [item["job_id"] for item in items]
    assert all(task == "chaotic.remove_background" for task, _ in no_queue)


def test_more_than_three_images_is_rejected(client, png_bytes, no_queue):
    response = client.post(
        "/api/v1/upload",
        files=[("files", (f"{i}.png", png_bytes, "image/png")) for i in range(4)],
        data={"remove_background": "false"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "too_many_files"


def test_a_non_image_content_type_is_rejected(client, no_queue):
    response = client.post(
        "/api/v1/upload",
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
        data={"remove_background": "false"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_image_type"


def test_bytes_that_are_not_really_an_image_are_rejected(client, no_queue):
    """The declared content type is client-controlled; the header decode is the real check."""
    response = client.post(
        "/api/v1/upload",
        files=[("files", ("fake.png", b"not a png at all", "image/png"))],
        data={"remove_background": "false"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_image_type"


def test_an_oversized_image_is_rejected(client, monkeypatch, png_bytes, no_queue):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "0")
    from src.core.config import get_settings

    get_settings.cache_clear()
    response = client.post(
        "/api/v1/upload",
        files=[("files", ("big.png", png_bytes, "image/png"))],
        data={"remove_background": "false"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "file_too_large"

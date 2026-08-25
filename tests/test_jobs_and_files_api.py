"""Job polling and file serving, including the hostile inputs."""

import pytest


@pytest.mark.parametrize(
    "job_id",
    ["20260825T140344-a3f9c1", "not-a-job-id", "....", "%00"],
)
def test_unknown_or_malformed_jobs_are_404(client, job_id):
    """Well-formed-looking but unknown, and outright malformed, both come back as 404."""
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/jobs/%2e%2e%2f%2e%2e%2f.env",
        "/api/v1/jobs/..%2f..%2f.env",
        "/api/v1/files/%2e%2e%2f.env/input/result.png",
    ],
)
def test_traversal_in_the_url_never_reaches_a_handler(client, path):
    """Encoded separators are decoded before routing, so these match no route at all.

    Routing is therefore the outermost of four guards; the job-id pattern, the filename
    pattern and ``resolve_within`` sit behind it.
    """
    response = client.get(path)
    assert response.status_code == 404
    assert "code" not in response.json()


def test_file_endpoint_rejects_an_unknown_kind(client):
    response = client.get("/api/v1/files/20260825T140344-a3f9c1/secrets/result.png")
    assert response.status_code == 422


def test_file_endpoint_does_not_serve_the_job_record(client, png_bytes, no_queue):
    """``job.json`` sits in the job folder but outside input/ and output/."""
    job_id = client.post(
        "/api/v1/upload",
        files=[("files", ("cat.png", png_bytes, "image/png"))],
        data={"remove_background": "false"},
    ).json()["items"][0]["job_id"]

    assert client.get(f"/api/v1/files/{job_id}/input/job.json").status_code == 404
    assert client.get(f"/api/v1/files/{job_id}/output/original.png").status_code == 404


def test_health_endpoint(client):
    assert client.get("/health").json()["status"] == "ok"

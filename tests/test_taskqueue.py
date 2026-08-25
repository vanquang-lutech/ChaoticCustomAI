"""Worker bootstrap and enqueue failure handling.

Task registration is a silent-failure mode: if a task module is renamed and ``TASK_MODULES``
is not updated, the API keeps accepting jobs and the worker never picks them up, so every job
sits in ``pending`` forever with nothing logged.
"""

import pytest

from src.core.exceptions import QueueUnavailableError
from src.taskqueue import client as client_module
from src.taskqueue.config import (
    TASK_CUSTOM_TEXT,
    TASK_GENERATE_IMAGE,
    TASK_MODULES,
    TASK_REMOVE_BACKGROUND,
)


def test_the_worker_bootstrap_registers_every_task():
    """``import_default_modules`` is the step a real worker runs at startup."""
    from src.workers.worker import app

    app.loader.import_default_modules()

    registered = {name for name in app.tasks if name.startswith("chaotic.")}
    assert registered == {TASK_REMOVE_BACKGROUND, TASK_GENERATE_IMAGE, TASK_CUSTOM_TEXT}


def test_every_configured_task_module_exists():
    import importlib

    for module_path in TASK_MODULES:
        assert importlib.import_module(module_path) is not None


def test_redis_is_a_broker_only():
    assert client_module.celery_app.conf.result_backend is None
    assert client_module.celery_app.conf.task_ignore_result is True


def test_a_broker_outage_becomes_a_503(monkeypatch):
    def explode(*_args, **_kwargs):
        raise ConnectionRefusedError("redis is down")

    monkeypatch.setattr(client_module.celery_app, "send_task", explode)

    with pytest.raises(QueueUnavailableError) as raised:
        client_module.enqueue(TASK_GENERATE_IMAGE, "20260825T140344-a3f9c1")

    assert raised.value.status_code == 503
    assert raised.value.code == "queue_unavailable"


def test_a_failed_enqueue_marks_the_job_failed_instead_of_leaving_it_pending(client, monkeypatch):
    def explode(_task_name, _job_id):
        raise QueueUnavailableError("redis is down")

    monkeypatch.setattr("src.services.generate_service.enqueue", explode)

    response = client.post("/api/v1/generate-image", json={"prompt": "a cat"})
    assert response.status_code == 503
    assert response.json()["code"] == "queue_unavailable"

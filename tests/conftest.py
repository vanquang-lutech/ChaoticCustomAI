"""Shared fixtures.

Every test runs against a throwaway storage root and a fake image provider: the suite must
never touch the real OpenAI API or the developer's ``storage/`` tree.
"""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from src.core import dependencies
from src.core.config import get_settings
from src.providers.openai.openai_client import ImageResult
from src.schemas.usage import TokenUsage

_CACHED_FACTORIES = (
    get_settings,
    dependencies.get_storage_service,
    dependencies.get_usage_service,
    dependencies.get_job_service,
    dependencies.get_image_service,
    dependencies.get_image_intake,
    dependencies.get_upload_service,
    dependencies.get_generate_service,
    dependencies.get_custom_text_service,
    dependencies.get_note_normalizer,
    dependencies.get_custom_product_service,
)


def _clear_caches() -> None:
    for factory in _CACHED_FACTORIES:
        factory.cache_clear()


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point every path-dependent setting at a temp directory."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    monkeypatch.setenv("STYLE_PRESETS_DIR", str(Path("assets/text-styles").resolve()))
    # Normalising an order note is an OpenAI text call. Off by default so no test can make
    # one by accident; the tests that cover it turn it on and fake the client.
    monkeypatch.setenv("NORMALIZE_ORDER_NOTES", "false")
    _clear_caches()
    yield get_settings()
    _clear_caches()


@pytest.fixture
def png_bytes() -> bytes:
    """A small but genuinely decodable RGBA PNG."""
    buffer = io.BytesIO()
    Image.new("RGBA", (32, 24), (255, 0, 0, 128)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def fake_result(png_bytes: bytes) -> ImageResult:
    return ImageResult(
        data=png_bytes,
        usage=TokenUsage(
            model="gpt-image-test",
            input_tokens=11,
            output_tokens=22,
            total_tokens=33,
        ),
    )


@pytest.fixture
def no_queue(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Capture enqueue calls instead of needing a live broker."""
    captured: list[tuple[str, str]] = []

    def fake_enqueue(task_name: str, job_id: str) -> None:
        captured.append((task_name, job_id))

    for module in (
        "src.services.upload_service",
        "src.services.generate_service",
        "src.services.custom_text_service",
        "src.services.custom_product_service",
    ):
        monkeypatch.setattr(module + ".enqueue", fake_enqueue)
    return captured


@pytest.fixture
def client(isolated_settings) -> TestClient:
    from src.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

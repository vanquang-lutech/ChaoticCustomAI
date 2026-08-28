"""FastAPI application entrypoint.

uvicorn src.main:app --reload
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.dependencies import get_image_service
from src.core.exceptions import AppError
from src.core.logging import setup_logging
from src.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


def _mark_binary_formats(node: object) -> None:
    """Add ``format: binary`` to every binary field in the OpenAPI schema.

    FastAPI emits binary payloads the OpenAPI 3.1 way, as ``contentMediaType:
    application/octet-stream``. Swagger UI still decides whether to draw a file picker from the
    3.0-style ``format: binary``, so without this the upload form renders ``files`` as a
    free-text "Add string item" box. The endpoint itself is unaffected either way; this only
    fixes what /docs shows. ``format`` is an open-ended annotation, so keeping both is valid.
    """
    if isinstance(node, dict):
        if (
            node.get("type") == "string"
            and node.get("contentMediaType") == "application/octet-stream"
        ):
            node["format"] = "binary"
        for value in node.values():
            _mark_binary_formats(value)
    elif isinstance(node, list):
        for item in node:
            _mark_binary_formats(item)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Fail loudly at startup for anything that would otherwise fail per-request."""
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)

    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY is not set; every image call will fail")

    missing = get_image_service().verify_style_presets()
    if missing:
        logger.warning(
            "Custom text will fail for these styles until their images are added: %s",
            ", ".join(missing),
        )

    # Every model actually in use is named here. A setting whose env var never reaches it fails
    # silently -- the note normaliser just falls back -- so the resolved values are logged.
    logger.info(
        "%s started | image_model=%s note_model=%s normalize_notes=%s storage=%s tz=%s",
        settings.app_name,
        settings.openai_image_model,
        settings.modified_request_model if settings.normalize_order_notes else "-",
        settings.normalize_order_notes,
        settings.storage_dir,
        settings.timezone,
    )
    yield
    logger.info("%s stopped", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        description=(
            "Upload images, generate images and render custom stylised text. "
            "Anything that calls OpenAI is queued as a job; poll GET /api/v1/jobs/{job_id}."
        ),
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        """Domain errors carry their own status code, so the routes stay free of HTTP details."""
        logger.warning("%s: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(code=exc.code, detail=exc.message).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code="internal_error", detail="Internal server error"
            ).model_dump(),
        )

    # Built eagerly so the patch lands in the cached schema that /openapi.json serves.
    _mark_binary_formats(app.openapi())

    return app


app = create_app()

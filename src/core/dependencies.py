"""Service wiring.

These factories are cached and plain callables, so the same graph serves both FastAPI's
``Depends`` and the Celery tasks -- the workers do not run inside a request, and must not need
a second construction path.
"""

from functools import lru_cache

from src.core.config import Settings, get_settings
from src.services.custom_product_service import CustomProductService
from src.services.custom_text_service import CustomTextService
from src.services.generate_service import GenerateImageService
from src.services.gpt_image_service import GptImageService
from src.services.image_intake import ImageIntake
from src.services.job_service import JobService
from src.services.note_normalizer import NoteNormalizer
from src.services.storage_service import StorageService
from src.services.upload_service import UploadService
from src.services.usage_service import UsageService


def _settings() -> Settings:
    return get_settings()


@lru_cache
def get_storage_service() -> StorageService:
    return StorageService(_settings())


@lru_cache
def get_usage_service() -> UsageService:
    return UsageService(_settings(), get_storage_service())


@lru_cache
def get_job_service() -> JobService:
    return JobService(_settings(), get_storage_service(), get_usage_service())


@lru_cache
def get_image_service() -> GptImageService:
    return GptImageService(_settings())


@lru_cache
def get_image_intake() -> ImageIntake:
    return ImageIntake(_settings())


@lru_cache
def get_upload_service() -> UploadService:
    return UploadService(
        _settings(),
        get_storage_service(),
        get_job_service(),
        get_image_service(),
        get_image_intake(),
    )


@lru_cache
def get_generate_service() -> GenerateImageService:
    return GenerateImageService(
        _settings(), get_storage_service(), get_job_service(), get_image_service()
    )


@lru_cache
def get_custom_text_service() -> CustomTextService:
    return CustomTextService(
        _settings(), get_storage_service(), get_job_service(), get_image_service()
    )


@lru_cache
def get_note_normalizer() -> NoteNormalizer:
    return NoteNormalizer(_settings())


@lru_cache
def get_custom_product_service() -> CustomProductService:
    return CustomProductService(
        _settings(),
        get_storage_service(),
        get_job_service(),
        get_image_service(),
        get_image_intake(),
        get_note_normalizer(),
        get_usage_service(),
    )

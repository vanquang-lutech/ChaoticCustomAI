"""Domain errors.

Services raise these; the API layer turns them into HTTP responses (see ``main.py``).
Keeping them free of HTTP concepts lets the Celery workers raise the same errors.
"""


class AppError(Exception):
    """Base class for every error this service raises deliberately."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class TooManyFilesError(ValidationError):
    code = "too_many_files"


class FileTooLargeError(ValidationError):
    code = "file_too_large"


class UnsupportedImageTypeError(ValidationError):
    code = "unsupported_image_type"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class JobNotFoundError(NotFoundError):
    code = "job_not_found"


class FileNotFoundInStorageError(NotFoundError):
    code = "file_not_found"


class StylePresetMissingError(AppError):
    status_code = 500
    code = "style_preset_missing"


class ImageProviderError(AppError):
    status_code = 502
    code = "image_provider_error"


class QueueUnavailableError(AppError):
    status_code = 503
    code = "queue_unavailable"

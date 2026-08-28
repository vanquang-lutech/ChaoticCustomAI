"""Enumerations shared across the whole service.

The string values of ``Feature`` double as directory names under ``storage/`` and as the
suffix of the Celery task names, so they must not be renamed casually.
"""

from enum import StrEnum


class Feature(StrEnum):
    """A user-facing capability. The value is also the storage folder name."""

    UPLOAD = "upload"
    GENERATE_IMAGE = "generate_image"
    CUSTOM_TEXT = "custom_text"
    CUSTOM_PRODUCT = "custom_product"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @property
    def is_final(self) -> bool:
        return self in (JobStatus.SUCCEEDED, JobStatus.FAILED)


class StorageKind(StrEnum):
    """The two sub-folders inside a job directory."""

    INPUT = "input"
    OUTPUT = "output"


class StylePreset(StrEnum):
    """Style reference images for the custom-text feature.

    Each value must have a matching ``<value>.png`` in ``settings.style_presets_dir``;
    this is verified at application startup.
    """

    COLLEGIATE = "collegiate"
    COMIC_BOLD = "comic-bold"
    GOLD_FOIL = "gold-foil"
    MIAMI_SCRIPT = "miami-script"
    PASTEL_CANDY = "pastel-candy"
    PIXEL_BLOCK = "pixel-block"
    STREET_TAG = "street-tag"
    Y2K_NEON = "y2k-neon"


class CustomizationMode(StrEnum):
    """How a customer described the change they want on a product mock-up.

    The storefront lets them do one or the other, never both: fill in the structured fields
    beside the product, or type a free-form request into the order note. The two arrive as
    different shapes and are prompted differently, so the mode is part of the request rather
    than something inferred from which payload happens to be present.
    """

    FIELDS = "fields"
    NOTE = "note"

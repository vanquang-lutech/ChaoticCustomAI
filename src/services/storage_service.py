"""The only module that knows how the storage tree is laid out.

    storage/<yyyy_mm>/<yyyy_mm_dd>/<feature>/<job_id>/{input,output}/

A job folder is self-contained: its input, its output and its ``job.json`` sit together, so it
can be inspected, archived or deleted as one unit. Nothing outside this service builds a
storage path, which is what lets the layout change without touching the API.
"""

import logging
from datetime import date
from pathlib import Path

from src.core.config import Settings
from src.core.constants import (
    DAY_DIR_FORMAT,
    MONTH_DIR_FORMAT,
    REQUEST_FILENAME,
    RESULT_FILENAME,
    SERVABLE_FILENAME_PATTERN,
    USAGE_FILENAME,
)
from src.core.enums import Feature, StorageKind
from src.core.exceptions import (
    FileNotFoundInStorageError,
    JobNotFoundError,
    ValidationError,
)
from src.schemas.common import ImageRef
from src.utils.file import atomic_write_bytes, resolve_within, write_json
from src.utils.ids import is_valid_job_id, job_id_date
from src.utils.image import probe_image

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root = Path(settings.storage_dir)

    @property
    def root(self) -> Path:
        return self._root

    # --- Path construction -------------------------------------------------

    def day_dir(self, day: date) -> Path:
        return self._root / day.strftime(MONTH_DIR_FORMAT) / day.strftime(DAY_DIR_FORMAT)

    def usage_path(self, day: date) -> Path:
        return self.day_dir(day) / USAGE_FILENAME

    def job_dir(self, feature: Feature, job_id: str, create: bool = False) -> Path:
        """Where a job lives. The date comes from the job id itself."""
        path = self.day_dir(job_id_date(job_id)) / feature.value / job_id
        if create:
            (path / StorageKind.INPUT.value).mkdir(parents=True, exist_ok=True)
            (path / StorageKind.OUTPUT.value).mkdir(parents=True, exist_ok=True)
        return path

    def find_job_dir(self, job_id: str) -> tuple[Feature, Path]:
        """Locate a job without knowing its feature.

        Only three ``is_dir`` checks, because the id already pins down the day.
        """
        if not is_valid_job_id(job_id):
            raise JobNotFoundError("Unknown job: " + job_id)
        day = self.day_dir(job_id_date(job_id))
        for feature in Feature:
            candidate = day / feature.value / job_id
            if candidate.is_dir():
                return feature, candidate
        raise JobNotFoundError("Unknown job: " + job_id)

    # --- Writing -----------------------------------------------------------

    def save_input_bytes(self, feature: Feature, job_id: str, filename: str, data: bytes) -> Path:
        path = self.job_dir(feature, job_id, create=True) / StorageKind.INPUT.value / filename
        atomic_write_bytes(path, data)
        logger.info("Stored input %s (%d bytes)", path, len(data))
        return path

    def save_output_bytes(
        self,
        feature: Feature,
        job_id: str,
        data: bytes,
        filename: str = RESULT_FILENAME,
    ) -> Path:
        path = self.job_dir(feature, job_id, create=True) / StorageKind.OUTPUT.value / filename
        atomic_write_bytes(path, data)
        logger.info("Stored output %s (%d bytes)", path, len(data))
        return path

    def save_request(self, feature: Feature, job_id: str, payload: dict) -> Path:
        """Persist the request that started a job, next to its result."""
        path = (
            self.job_dir(feature, job_id, create=True) / StorageKind.INPUT.value / REQUEST_FILENAME
        )
        write_json(path, payload)
        return path

    # --- Reading / serving -------------------------------------------------

    def resolve_servable(self, job_id: str, kind: StorageKind, filename: str) -> Path:
        """Validate a client-supplied triple and return the file it names.

        Three independent checks stand between the URL and the disk: the job id must match its
        pattern, ``kind`` is already an enum, and the filename must be a plain basename. The
        final ``resolve_within`` is the backstop.
        """
        if not SERVABLE_FILENAME_PATTERN.match(filename):
            raise ValidationError("Illegal filename: " + filename)
        _, job_path = self.find_job_dir(job_id)
        relative = job_path.relative_to(self._root).as_posix()
        path = resolve_within(self._root, relative, kind.value, filename)
        # Belt and braces: resolution must not have changed which file was asked for.
        if path.name != filename:
            raise ValidationError("Illegal filename: " + filename)
        if not path.is_file():
            raise FileNotFoundInStorageError("No such file: " + kind.value + "/" + filename)
        return path

    def public_url(self, job_id: str, kind: StorageKind, filename: str) -> str:
        prefix = self._settings.files_url_prefix.rstrip("/")
        return prefix + "/" + job_id + "/" + kind.value + "/" + filename

    def image_ref(self, job_id: str, kind: StorageKind, path: Path) -> ImageRef:
        """Describe a stored image for a response body."""
        width: int | None = None
        height: int | None = None
        try:
            info = probe_image(path.read_bytes())
            width, height = info.width, info.height
        except Exception:  # noqa: BLE001 - dimensions are cosmetic, never fail a response
            logger.warning("Could not read dimensions of %s", path)
        return ImageRef(
            url=self.public_url(job_id, kind, path.name),
            filename=path.name,
            size_bytes=path.stat().st_size,
            width=width,
            height=height,
        )

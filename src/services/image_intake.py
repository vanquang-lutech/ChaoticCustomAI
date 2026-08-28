"""Turning an uploaded file into bytes we are willing to store.

Shared by every feature that accepts an image from a client, so the size cap, the content-type
check and the header decode are written once. The cap is enforced while reading rather than
after: a client that announces a small file and sends a huge one is cut off mid-stream instead
of filling memory first and being rejected afterwards.
"""

import logging
from dataclasses import dataclass

from fastapi import UploadFile

from src.core.config import Settings
from src.core.exceptions import (
    FileTooLargeError,
    UnsupportedImageTypeError,
    ValidationError,
)
from src.utils.file import extension_for_content_type
from src.utils.image import probe_image

logger = logging.getLogger(__name__)

_READ_CHUNK = 64 * 1024


@dataclass(frozen=True)
class IncomingImage:
    """An upload that has been read, checked, and not yet stored."""

    filename: str
    content_type: str
    data: bytes

    @property
    def extension(self) -> str:
        return extension_for_content_type(self.content_type)


class ImageIntake:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def read(self, upload: UploadFile) -> IncomingImage:
        limit = self._settings.max_upload_size_bytes
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await upload.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise FileTooLargeError(
                    "Each image must be at most " + str(self._settings.max_upload_size_mb) + " MB"
                )
            chunks.append(chunk)

        data = b"".join(chunks)
        if not data:
            raise ValidationError("Empty upload: " + (upload.filename or "unnamed"))

        content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if content_type not in self._settings.allowed_content_types:
            raise UnsupportedImageTypeError("Unsupported image type: " + (content_type or "?"))
        # The declared type is client-controlled; decoding the header is what proves it.
        probe_image(data)
        return IncomingImage(
            filename=upload.filename or "unnamed",
            content_type=content_type,
            data=data,
        )

"""Image inspection. Pillow is used for validation only -- never to alter the pixels."""

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from src.core.exceptions import UnsupportedImageTypeError


@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int
    format: str
    mode: str

    @property
    def has_alpha(self) -> bool:
        return self.mode in ("RGBA", "LA", "PA") or self.mode == "P"


def probe_image(data: bytes) -> ImageInfo:
    """Read an image's header, confirming the bytes really are a decodable image.

    An upload's declared content type is attacker-controlled; this is what actually proves
    the payload is an image.
    """
    try:
        with Image.open(io.BytesIO(data)) as image:
            info = ImageInfo(
                width=image.width,
                height=image.height,
                format=(image.format or "unknown").lower(),
                mode=image.mode,
            )
        # verify() needs a fresh stream because it consumes the file.
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UnsupportedImageTypeError(f"Not a readable image: {exc}") from exc
    return info

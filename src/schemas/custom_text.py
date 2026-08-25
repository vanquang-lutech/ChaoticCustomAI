"""Request model for the custom-text feature."""

from pydantic import BaseModel, Field

from src.core.enums import StylePreset
from src.schemas.image import ImageQuality, ImageSize


class CustomTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200, description="The text to render")
    style_preset: StylePreset = Field(description="Which style reference image to follow")
    size: ImageSize | None = None
    quality: ImageQuality | None = None

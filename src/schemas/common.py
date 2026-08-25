"""Response pieces shared by more than one feature."""

from pydantic import BaseModel, Field


class ImageRef(BaseModel):
    """A stored image, addressed by URL rather than by storage path."""

    url: str = Field(description="Fetch the bytes from here")
    filename: str
    size_bytes: int
    width: int | None = None
    height: int | None = None


class ErrorResponse(BaseModel):
    code: str
    detail: str

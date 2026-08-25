"""Thin wrapper over the OpenAI image endpoints.

Everything above this layer deals in ``bytes`` plus a ``TokenUsage``; nothing else imports the
OpenAI SDK. The SDK already retries transient failures on its own, so no retry loop here.
"""

import base64
import logging
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI, OpenAIError

from src.core.exceptions import ImageProviderError
from src.schemas.usage import TokenUsage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageResult:
    data: bytes
    usage: TokenUsage


class OpenAIImageClient:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ImageProviderError("OPENAI_API_KEY is not configured")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def generate(self, prompt: str, size: str, quality: str) -> ImageResult:
        """Create an image from a prompt alone."""
        try:
            response = self._client.images.generate(
                model=self._model,
                prompt=prompt,
                background="transparent",
                size=size,
                quality=quality,
                output_format="png",
            )
        except OpenAIError as exc:
            raise ImageProviderError(f"Image generation failed: {exc}") from exc
        return self._to_result(response)

    def edit(self, prompt: str, image_path: Path, size: str, quality: str) -> ImageResult:
        """Transform an existing image -- used for background removal and custom text."""
        try:
            with image_path.open("rb") as handle:
                response = self._client.images.edit(
                    model=self._model,
                    image=handle,
                    prompt=prompt,
                    background="transparent",
                    size=size,
                    quality=quality,
                    output_format="png",
                )
        except OpenAIError as exc:
            raise ImageProviderError(f"Image edit failed: {exc}") from exc
        return self._to_result(response)

    def _to_result(self, response: object) -> ImageResult:
        data = getattr(response, "data", None)
        b64 = getattr(data[0], "b64_json", None) if data else None
        if not b64:
            raise ImageProviderError("OpenAI returned no image data")
        return ImageResult(data=base64.b64decode(b64), usage=self._to_usage(response))

    def _to_usage(self, response: object) -> TokenUsage:
        """Read the token counts off the response.

        The field is absent on some models and on older API versions, so a missing usage block
        degrades to zeros rather than failing a job that already produced an image.
        """
        usage = getattr(response, "usage", None)
        if usage is None:
            logger.warning("No usage block on the %s response; recording zeros", self._model)
            return TokenUsage(model=self._model)
        return TokenUsage(
            model=self._model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )

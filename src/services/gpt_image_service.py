"""Feature-agnostic OpenAI image work: pairs a prompt builder with the provider.

The provider is built lazily so that importing this module -- and starting the app -- does not
require an API key. Only an actual image call does.
"""

import logging
from pathlib import Path

from src.core.config import Settings
from src.core.enums import StylePreset
from src.core.exceptions import StylePresetMissingError
from src.prompts.custom_text import build_custom_text_prompt
from src.prompts.generate_image import build_generate_image_prompt
from src.prompts.remove_background import build_remove_background_prompt
from src.providers.openai.openai_client import ImageResult, OpenAIImageClient

logger = logging.getLogger(__name__)


class GptImageService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: OpenAIImageClient | None = None

    @property
    def client(self) -> OpenAIImageClient:
        if self._client is None:
            self._client = OpenAIImageClient(
                api_key=self._settings.openai_api_key,
                model=self._settings.openai_image_model,
            )
        return self._client

    # --- Style presets -----------------------------------------------------

    def style_preset_path(self, preset: StylePreset) -> Path:
        path = Path(self._settings.style_presets_dir) / (preset.value + ".png")
        if not path.is_file():
            raise StylePresetMissingError("Missing style reference image: " + str(path))
        return path

    def verify_style_presets(self) -> list[str]:
        """Check every preset has its reference image. Called at startup.

        A missing file would otherwise only surface when a user picks that style.
        """
        missing = [
            preset.value
            for preset in StylePreset
            if not (Path(self._settings.style_presets_dir) / (preset.value + ".png")).is_file()
        ]
        if missing:
            logger.error("Style preset images missing: %s", ", ".join(missing))
        return missing

    # --- Image operations --------------------------------------------------

    def generate_transparent(
        self, description: str, size: str | None = None, quality: str | None = None
    ) -> ImageResult:
        return self.client.generate(
            prompt=build_generate_image_prompt(description),
            size=size or self._settings.image_size,
            quality=quality or self._settings.image_quality,
        )

    def remove_background(self, image_path: Path, quality: str | None = None) -> ImageResult:
        """Strip the background off an existing image.

        Size is pinned to ``auto`` so the model keeps the source dimensions -- resizing here
        would contradict the prompt's preservation requirements.
        """
        return self.client.edit(
            prompt=build_remove_background_prompt(),
            image_path=image_path,
            size="auto",
            quality=quality or self._settings.image_quality,
        )

    def render_custom_text(
        self,
        text: str,
        preset: StylePreset,
        size: str | None = None,
        quality: str | None = None,
    ) -> ImageResult:
        return self.client.edit(
            prompt=build_custom_text_prompt(text, preset.value),
            image_path=self.style_preset_path(preset),
            size=size or self._settings.image_size,
            quality=quality or self._settings.image_quality,
        )

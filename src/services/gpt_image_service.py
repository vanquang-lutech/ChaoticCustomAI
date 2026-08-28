"""Feature-agnostic OpenAI image work: pairs a prompt builder with the provider.

The provider is built lazily so that importing this module -- and starting the app -- does not
require an API key. Only an actual image call does.
"""

import logging
from pathlib import Path

from src.core.config import Settings
from src.core.enums import StylePreset
from src.core.exceptions import StylePresetMissingError
from src.prompts.custom_product import (
    CASE_FIELDS_REMOVE,
    CASE_FIELDS_REPLACE,
    CASE_FIELDS_REPLACE_REMOVE,
    CASE_NOTE,
    CASE_NOTE_REFERENCE,
    build_custom_product_note_prompt,
    build_custom_product_note_with_reference_prompt,
    build_custom_product_remove_prompt,
    build_custom_product_replace_and_remove_prompt,
    build_custom_product_replace_prompt,
)
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
            image_paths=[image_path],
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
            image_paths=[self.style_preset_path(preset)],
            size=size or self._settings.image_size,
            quality=quality or self._settings.image_quality,
        )

    # --- Product customisation -------------------------------------------------------------
    # Two parameters are pinned here that the other features do not pin, and getting either
    # wrong quietly ruins the result:
    #
    #   size="auto"        A mock-up showing a front and a back view is far wider than one
    #                      showing a single view. Any fixed size would squash it or crop a
    #                      view away, so the source dimensions are kept.
    #   background="auto"  The other two features return cutouts and want transparency. Here
    #                      the product photo's own background is part of what must survive the
    #                      edit, so it is left alone.

    def customize_product(
        self,
        case: str,
        template_path: Path,
        fields: dict[str, str] | None = None,
        remove_fields: list[str] | None = None,
        note: str | None = None,
        reference_path: Path | None = None,
        size: str | None = None,
        quality: str | None = None,
    ) -> ImageResult:
        """Edit a product mock-up with the prompt written for ``case``.

        ``case`` comes from ``customization_case`` rather than being worked out here, so the
        prompt that runs and the case recorded on the job cannot disagree.
        """
        paths = [template_path]
        if reference_path is not None:
            # The mock-up stays first: the prompt refers to the second image as reference only.
            paths.append(reference_path)

        return self.client.edit(
            prompt=self._product_prompt(case, fields or {}, remove_fields or [], note or ""),
            image_paths=paths,
            size=size or "auto",
            quality=quality or self._settings.image_quality,
            background="auto",
        )

    @staticmethod
    def _product_prompt(
        case: str, fields: dict[str, str], remove_fields: list[str], note: str
    ) -> str:
        if case == CASE_FIELDS_REPLACE:
            return build_custom_product_replace_prompt(fields)
        if case == CASE_FIELDS_REMOVE:
            return build_custom_product_remove_prompt(remove_fields)
        if case == CASE_FIELDS_REPLACE_REMOVE:
            return build_custom_product_replace_and_remove_prompt(fields, remove_fields)
        if case == CASE_NOTE:
            return build_custom_product_note_prompt(note)
        if case == CASE_NOTE_REFERENCE:
            return build_custom_product_note_with_reference_prompt(note)
        raise ValueError("Unknown customisation case: " + case)

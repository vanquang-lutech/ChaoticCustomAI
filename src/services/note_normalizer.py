"""Reading a customer's order note before it reaches the image model.

A note is a prompt written by a member of the public. This turns it into a checked, structured
request first, which buys three things:

* a request that cannot be done to a garment is refused in about a second, instead of after an
  image call that was always going to produce the wrong thing;
* the parts of it that name elements the image prompts already know are prompted with the same
  precise wording a storefront field would get;
* the words that reach the image prompt have been read and rewritten, rather than pasted in.

It is best-effort by design. If the text call fails, the note is passed through as it always
was and the job carries on -- a customer's order is not worth losing to a hiccup in an
optimisation.
"""

import logging

from src.core.config import Settings
from src.prompts.note_normalizer import (
    build_note_normalizer_content,
    build_note_normalizer_prompt,
)
from src.providers.openai.openai_text_client import OpenAITextClient
from src.schemas.custom_product import (
    SOURCE_NORMALIZED,
    SOURCE_RAW,
    SOURCE_RAW_FALLBACK,
    NoteIntent,
)
from src.schemas.usage import TokenUsage

logger = logging.getLogger(__name__)


class NoteNormalizer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: OpenAITextClient | None = None

    @property
    def client(self) -> OpenAITextClient:
        """Built on first use, so importing this module never needs an API key."""
        if self._client is None:
            self._client = OpenAITextClient(
                api_key=self._settings.openai_api_key,
                model=self._settings.modified_request_model,
            )
        return self._client

    def normalize(self, note: str) -> tuple[NoteIntent, TokenUsage | None]:
        """Read a note. Returns the request it describes, and what the reading cost.

        The usage comes back separately because it belongs to this call, not to the image call
        the job records as its result -- both are appended to ``usage.jsonl`` under their own
        model, so the two show up as separate lines and separate buckets.
        """
        if not self._settings.normalize_order_notes:
            return NoteIntent(instructions=note, source=SOURCE_RAW), None

        try:
            result = self.client.complete_json(
                instructions=build_note_normalizer_prompt(),
                content=build_note_normalizer_content(note),
            )
            intent = NoteIntent.model_validate(result.data | {"source": SOURCE_NORMALIZED})
        except Exception as exc:  # noqa: BLE001 - a failed reading must not fail the order
            logger.warning("Could not normalise the order note, using it as written: %s", exc)
            return NoteIntent(instructions=note, source=SOURCE_RAW_FALLBACK), None

        if not intent.feasible:
            logger.info("Order note refused as infeasible: %s", intent.rejected_reason)
            return intent, result.usage

        if not (intent.instructions or intent.replace or intent.remove):
            # Understood as feasible but describing nothing: the note is more use as written.
            logger.warning("Normalisation returned an empty request, using the note as written")
            return NoteIntent(instructions=note, source=SOURCE_RAW_FALLBACK), result.usage

        logger.info(
            "Normalised order note: replace=%s remove=%s fully_structured=%s",
            sorted(intent.replace),
            intent.remove,
            intent.fully_structured,
        )
        return intent, result.usage

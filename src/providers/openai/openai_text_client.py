"""OpenAI text calls. Used only to turn a customer's order note into a structured request.

Separate from ``OpenAIImageClient`` because it is a different model, a different endpoint and a
different order of magnitude of cost: a text call on a 1000-character note is negligible next to
one image call, which is what makes it worth spending before deciding to spend the image call.

The response is asked for as JSON and returned as a plain dict. Validating it into a model is
the caller's job, so a malformed answer is a domain decision rather than a provider error.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAI, OpenAIError

from src.core.exceptions import ImageProviderError
from src.schemas.usage import TokenUsage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextResult:
    data: dict[str, Any]
    usage: TokenUsage


class OpenAITextClient:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ImageProviderError("OPENAI_API_KEY is not configured")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def complete_json(self, instructions: str, content: str) -> TextResult:
        """Ask for one JSON object.

        ``instructions`` and ``content`` are sent as separate messages on purpose: the content is
        text a member of the public wrote, and keeping it out of the instruction message is the
        first line of defence, before anything the instructions themselves say about it.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": content},
                ],
            )
        except OpenAIError as exc:
            raise ImageProviderError(f"Text completion failed: {exc}") from exc

        return TextResult(data=self._to_data(response), usage=self._to_usage(response))

    def _to_data(self, response: object) -> dict[str, Any]:
        choices = getattr(response, "choices", None)
        message = getattr(choices[0], "message", None) if choices else None
        body = getattr(message, "content", None) if message else None
        if not body:
            raise ImageProviderError("OpenAI returned no text")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ImageProviderError(f"OpenAI returned text that is not JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ImageProviderError("OpenAI returned JSON that is not an object")
        return parsed

    def _to_usage(self, response: object) -> TokenUsage:
        """Read the token counts off the response.

        Chat completions name them differently from the image endpoint, so they are mapped here
        rather than leaving two vocabularies in ``usage.jsonl``.
        """
        usage = getattr(response, "usage", None)
        if usage is None:
            logger.warning("No usage block on the %s response; recording zeros", self._model)
            return TokenUsage(model=self._model)
        return TokenUsage(
            model=self._model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )

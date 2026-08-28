"""Request models for the product-customisation feature.

The storefront offers a customer two ways to ask for a change and lets them use only one:
fill in the fields beside the product, or type into the order note. ``mode`` says which, and
the validators here are what make "only one" true rather than merely intended.
"""

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.constants import (
    CUSTOM_FIELD_KEY_PATTERN,
    MAX_CUSTOM_FIELD_VALUE_LENGTH,
    MAX_CUSTOM_FIELDS,
    MAX_ORDER_NOTE_LENGTH,
    PRODUCT_ID_PATTERN,
)
from src.core.enums import CustomizationMode
from src.core.exceptions import ValidationError
from src.prompts.custom_product import FIELD_GUIDANCE
from src.schemas.image import ImageQuality, ImageSize


def _clean_text(value: str) -> str:
    """Drop control characters and collapse the edges.

    Anything a customer types ends up inside a prompt, so a stray newline or terminal escape
    has no business surviving the trip. Applied to values, never to keys -- see ``_clean_key``.
    """
    return "".join(char for char in value if char == " " or char.isprintable()).strip()


def _clean_key(value: str) -> str:
    """Trim a field key, and nothing more.

    Keys are emitted by the storefront, not typed by a customer, so a malformed one is a bug
    worth reporting rather than something to repair. Stripping control characters here would
    turn a key that must be rejected into one that happens to match the pattern.
    """
    return value.strip()


class CustomProductRequest(BaseModel):
    """One customisation request for one product mock-up.

    ``fields`` and ``remove_fields`` together carry three distinct states per field, which a
    flat mapping alone cannot express:

    * listed in ``fields``        -- write this value onto the garment
    * listed in ``remove_fields`` -- the customer switched it off; erase it from the garment
    * absent from both           -- this product has no such field; do not touch it
    """

    mode: CustomizationMode
    fields: dict[str, str] = Field(
        default_factory=dict,
        description="Field values to apply, e.g. {'name': 'MRS. JOHNSON', 'number': '01'}",
    )
    remove_fields: list[str] = Field(
        default_factory=list,
        description="Field keys the customer switched off; erased from the garment",
    )
    note: str | None = Field(
        default=None,
        description="The customer's own description of what they want changed",
    )
    product_id: str | None = Field(
        default=None,
        description="Storefront product id, recorded with the job",
    )
    size: ImageSize | None = None
    quality: ImageQuality | None = None

    @field_validator("fields", mode="before")
    @classmethod
    def _check_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        cleaned: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            key = _clean_key(str(raw_key))
            text = _clean_text("" if raw_value is None else str(raw_value))
            # A field the customer left blank is not an instruction. Switching a field off is
            # said explicitly through ``remove_fields``, never by sending an empty string.
            if not text:
                continue
            if not CUSTOM_FIELD_KEY_PATTERN.match(key):
                raise ValidationError("Not a usable field name: " + repr(raw_key))
            if len(text) > MAX_CUSTOM_FIELD_VALUE_LENGTH:
                raise ValidationError(
                    "Field "
                    + key
                    + " is longer than "
                    + str(MAX_CUSTOM_FIELD_VALUE_LENGTH)
                    + " characters"
                )
            cleaned[key] = text
        if len(cleaned) > MAX_CUSTOM_FIELDS:
            raise ValidationError("At most " + str(MAX_CUSTOM_FIELDS) + " fields per request")
        return cleaned

    @field_validator("remove_fields", mode="before")
    @classmethod
    def _check_remove_fields(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        cleaned: list[str] = []
        for raw_key in value:
            key = _clean_key(str(raw_key))
            if not key:
                continue
            if not CUSTOM_FIELD_KEY_PATTERN.match(key):
                raise ValidationError("Not a usable field name: " + repr(raw_key))
            if key not in cleaned:
                cleaned.append(key)
        if len(cleaned) > MAX_CUSTOM_FIELDS:
            raise ValidationError("At most " + str(MAX_CUSTOM_FIELDS) + " fields per request")
        return cleaned

    @field_validator("note", mode="before")
    @classmethod
    def _check_note(cls, value: object) -> object:
        if value is None:
            return None
        note = _clean_text(str(value))
        if len(note) > MAX_ORDER_NOTE_LENGTH:
            raise ValidationError(
                "The order note must be at most " + str(MAX_ORDER_NOTE_LENGTH) + " characters"
            )
        return note or None

    @field_validator("product_id", mode="before")
    @classmethod
    def _check_product_id(cls, value: object) -> object:
        if value is None:
            return None
        product_id = _clean_text(str(value))
        if not product_id:
            return None
        if not PRODUCT_ID_PATTERN.match(product_id):
            raise ValidationError("Not a usable product id: " + repr(value))
        return product_id

    @model_validator(mode="after")
    def _check_one_mode_only(self) -> "CustomProductRequest":
        """Enforce the storefront's either/or, and refuse to guess when it is broken."""
        if self.mode is CustomizationMode.FIELDS:
            if self.note:
                raise ValidationError("mode=fields does not take an order note")
            if not self.fields and not self.remove_fields:
                # Erasing alone is a real request: "take the number off, leave the rest".
                raise ValidationError(
                    "mode=fields needs at least one field value or one field to remove"
                )
        else:
            if self.fields or self.remove_fields:
                raise ValidationError("mode=note does not take field values")
            if not self.note:
                raise ValidationError("mode=note needs an order note")

        overlap = sorted(set(self.fields) & set(self.remove_fields))
        if overlap:
            raise ValidationError(
                "These fields ask to be set and removed at once: " + ", ".join(overlap)
            )
        return self


SOURCE_RAW = "raw"
SOURCE_NORMALIZED = "normalized"
SOURCE_RAW_FALLBACK = "raw-fallback"


class NoteIntent(BaseModel):
    """What a customer's free-text order note actually asks for.

    Produced by the normalising step before any image call, so the image prompt is built from a
    description that has been read and checked rather than from raw customer text.

    ``instructions`` always carries the whole request in prose. ``replace`` and ``remove`` carry
    the parts that fit the element vocabulary the image prompts know, and ``fully_structured``
    says whether they cover the request on their own -- when they do, the request is prompted
    exactly like one typed into the storefront fields, which is the more precise wording.
    """

    feasible: bool = True
    replace: dict[str, str] = Field(default_factory=dict)
    remove: list[str] = Field(default_factory=list)
    instructions: str | None = None
    fully_structured: bool = False
    rejected_reason: str | None = None
    # Recorded on the job so the raw and normalised paths stay comparable on real data.
    source: str = SOURCE_RAW

    @field_validator("replace", mode="before")
    @classmethod
    def _clean_replace(cls, value: object) -> object:
        """Drop anything the model invented that the image prompts cannot name."""
        if not isinstance(value, dict):
            return {}
        return {
            _clean_key(str(key)): _clean_text(str(item))
            for key, item in value.items()
            if _clean_key(str(key)) in FIELD_GUIDANCE and _clean_text(str(item or ""))
        }

    @field_validator("remove", mode="before")
    @classmethod
    def _clean_remove(cls, value: object) -> object:
        if not isinstance(value, list):
            return []
        cleaned = []
        for key in value:
            name = _clean_key(str(key))
            if name in FIELD_GUIDANCE and name not in cleaned:
                cleaned.append(name)
        return cleaned

    @field_validator("instructions", "rejected_reason", mode="before")
    @classmethod
    def _clean_prose(cls, value: object) -> object:
        if value is None:
            return None
        return _clean_text(str(value)) or None

    @model_validator(mode="after")
    def _only_trust_structure_it_earned(self) -> "NoteIntent":
        """``fully_structured`` has to be backed by structure that survived cleaning.

        The flag decides which prompt runs, so a model that claims the request is fully
        structured while naming elements we dropped must not be taken at its word.
        """
        if self.fully_structured and not (self.replace or self.remove):
            self.fully_structured = False
        return self

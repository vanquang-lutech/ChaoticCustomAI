"""Custom-product route.

Multipart rather than JSON, because the product mock-up being edited is uploaded with the
request. Multipart has no nested objects, so ``fields`` arrives as a JSON object string while
``remove_fields`` arrives as a repeated form field -- a JSON array is accepted there too, since
a client that already encodes ``fields`` as JSON will reach for the same shape.
"""

import json

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import ValidationError as PydanticValidationError

from src.core.dependencies import get_custom_product_service
from src.core.enums import CustomizationMode
from src.core.exceptions import ValidationError
from src.schemas.custom_product import CustomProductRequest
from src.schemas.job import JobAccepted
from src.services.custom_product_service import CustomProductService

router = APIRouter(prefix="/custom-product", tags=["custom-product"])


def _text(value: str | None) -> str | None:
    """An untouched form input arrives as an empty string, which is not a value."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_fields(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("fields must be a JSON object: " + str(exc)) from exc
    if not isinstance(parsed, dict):
        raise ValidationError("fields must be a JSON object")
    return parsed


def _parse_remove_fields(raw: list[str] | None) -> list[str]:
    values = [value for value in (raw or []) if value and value.strip()]
    # Tolerate a JSON array in a single field, so encoding it like ``fields`` also works.
    if len(values) == 1 and values[0].strip().startswith("["):
        try:
            parsed = json.loads(values[0])
        except json.JSONDecodeError as exc:
            raise ValidationError("remove_fields must be a JSON array: " + str(exc)) from exc
        if not isinstance(parsed, list):
            raise ValidationError("remove_fields must be a JSON array")
        return [str(item) for item in parsed]
    return values


def _empty_upload(upload: UploadFile | None) -> bool:
    """A file input the customer never used still arrives, with nothing in it."""
    return upload is None or not upload.filename


@router.post("", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
async def customize_product(
    template: UploadFile = File(description="The product mock-up to edit"),
    mode: CustomizationMode = Form(description="fields or note -- one or the other, not both"),
    fields: str | None = Form(
        default=None,
        description='JSON object of field values, e.g. {"name": "MRS. JOHNSON", "number": "01"}',
    ),
    remove_fields: list[str] | None = Form(
        default=None,
        description="Field keys the customer switched off; erased from the garment",
    ),
    note: str | None = Form(default=None, description="The customer's own order note"),
    product_id: str | None = Form(default=None),
    size: str | None = Form(default=None),
    quality: str | None = Form(default=None),
    reference: UploadFile | None = File(
        default=None, description="Optional image the customer attached to their note"
    ),
    service: CustomProductService = Depends(get_custom_product_service),
) -> JobAccepted:
    payload = {
        "mode": mode,
        "fields": _parse_fields(_text(fields)),
        "remove_fields": _parse_remove_fields(remove_fields),
        "note": _text(note),
        "product_id": _text(product_id),
        "size": _text(size),
        "quality": _text(quality),
    }
    try:
        request = CustomProductRequest.model_validate(payload)
    except PydanticValidationError as exc:
        # The domain rules raise AppError themselves; this catches the type-level failures, so
        # a bad ``size`` answers 422 like everything else instead of falling through as a 500.
        raise ValidationError(_first_message(exc)) from exc

    return await service.create(
        request,
        template=template,
        reference=None if _empty_upload(reference) else reference,
    )


def _first_message(exc: PydanticValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error.get("loc", ())) or "request"
    return location + ": " + error.get("msg", "is not valid")

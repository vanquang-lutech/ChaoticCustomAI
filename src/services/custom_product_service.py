"""Custom product: edit a product mock-up the way the customer asked for it.

Two ways in, one job either way. The customer either fills in the fields beside the product or
writes into the order note, never both; the storefront enforces the choice in its UI and
``CustomProductRequest`` enforces it here.

The mock-up arrives with the request as an upload rather than being looked up server-side, so
a job folder holds everything the edit was made from: the template, any reference image the
customer attached, the request, the result.
"""

import logging
from pathlib import Path

from fastapi import UploadFile

from src.core.config import Settings
from src.core.constants import REFERENCE_STEM, TEMPLATE_STEM
from src.core.enums import CustomizationMode, Feature, StorageKind
from src.core.exceptions import ValidationError
from src.prompts.custom_product import CASE_NOTE, CASE_NOTE_REFERENCE, customization_case
from src.providers.openai.openai_client import ImageResult
from src.schemas.custom_product import CustomProductRequest, NoteIntent
from src.schemas.job import JobAccepted, JobRecord
from src.services.gpt_image_service import GptImageService
from src.services.image_intake import ImageIntake
from src.services.job_service import JobService
from src.services.note_normalizer import NoteNormalizer
from src.services.storage_service import StorageService
from src.services.usage_service import UsageService
from src.taskqueue.client import enqueue
from src.taskqueue.config import TASK_CUSTOM_PRODUCT
from src.utils.hashing import short_sha256

logger = logging.getLogger(__name__)


class CustomProductService:
    def __init__(
        self,
        settings: Settings,
        storage: StorageService,
        jobs: JobService,
        images: GptImageService,
        intake: ImageIntake,
        notes: NoteNormalizer,
        usage: UsageService,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._jobs = jobs
        self._images = images
        self._intake = intake
        self._notes = notes
        self._usage = usage

    async def create(
        self,
        request: CustomProductRequest,
        template: UploadFile,
        reference: UploadFile | None = None,
    ) -> JobAccepted:
        self._check_product(request.product_id)
        if reference is not None and request.mode is not CustomizationMode.NOTE:
            # The storefront only offers the image upload beside the order note. Refusing is
            # better than storing a file the prompt for this mode would silently ignore.
            raise ValidationError("An attached image belongs with an order note, not with fields")

        # Both uploads are read and checked before anything is written, so a bad reference
        # image does not leave a half-built job folder behind.
        template_image = await self._intake.read(template)
        reference_image = await self._intake.read(reference) if reference is not None else None

        template_filename = TEMPLATE_STEM + template_image.extension
        reference_filename = REFERENCE_STEM + reference_image.extension if reference_image else None

        meta = request.model_dump(mode="json") | {
            "template_filename": template_filename,
            "template_sha256_short": short_sha256(template_image.data),
            "template_original_filename": template_image.filename,
            "reference_filename": reference_filename,
        }

        record = self._jobs.create(Feature.CUSTOM_PRODUCT, meta=meta)
        self._storage.save_input_bytes(
            Feature.CUSTOM_PRODUCT, record.job_id, template_filename, template_image.data
        )
        if reference_image and reference_filename:
            self._storage.save_input_bytes(
                Feature.CUSTOM_PRODUCT, record.job_id, reference_filename, reference_image.data
            )
        self._storage.save_request(Feature.CUSTOM_PRODUCT, record.job_id, meta)

        try:
            enqueue(TASK_CUSTOM_PRODUCT, record.job_id)
        except Exception:
            self._jobs.mark_failed(record, "Could not queue the product customisation")
            raise

        return JobAccepted(job_id=record.job_id, feature=record.feature, status=record.status)

    def run(self, job_id: str) -> JobRecord:
        def produce(record: JobRecord, job_dir: Path) -> ImageResult:
            template_path = self._require_input(job_dir, record.meta.get("template_filename"))
            reference_path = self._optional_input(job_dir, record.meta.get("reference_filename"))
            mode = CustomizationMode(record.meta["mode"])

            fully_structured = False
            if mode is CustomizationMode.FIELDS:
                fields = record.meta.get("fields") or {}
                remove_fields = record.meta.get("remove_fields") or []
                note = None
            else:
                intent = self._resolve_note(record, record.meta.get("note") or "")
                fields = intent.replace
                remove_fields = intent.remove
                note = intent.instructions
                fully_structured = intent.fully_structured
                if not intent.feasible:
                    self._record_case(record, CASE_NOTE_REFERENCE if reference_path else CASE_NOTE)
                    raise ValidationError(
                        intent.rejected_reason or "This request cannot be applied to the product"
                    )

            case = customization_case(
                mode.value,
                fields=fields,
                remove_fields=remove_fields,
                has_reference=reference_path is not None,
                fully_structured=fully_structured,
            )
            # Written before the call, so a job that fails still says which prompt ran.
            self._record_case(record, case)

            return self._images.customize_product(
                case=case,
                template_path=template_path,
                fields=fields,
                remove_fields=remove_fields,
                note=note,
                reference_path=reference_path,
                size=record.meta.get("size"),
                quality=record.meta.get("quality"),
            )

        return self._jobs.execute(job_id, produce)

    def _record_case(self, record: JobRecord, case: str) -> None:
        """Note which of the five prompts ran, so a bad result can be traced to its wording."""
        record.meta["prompt_case"] = case
        self._jobs.save(record)

    def _resolve_note(self, record: JobRecord, note: str) -> NoteIntent:
        """Read the order note before it reaches the image model.

        The reading is its own OpenAI call, so its tokens are recorded against this job under
        the text model rather than folded into the image call's usage. ``NoteNormalizer`` falls
        back to the note as written if that call fails, so nothing here has to handle failure.
        """
        intent, usage = self._notes.normalize(note)
        record.meta["note_source"] = intent.source
        if intent.instructions and intent.instructions != note:
            # Kept so a bad result can be read against what was actually asked of the model.
            record.meta["note_normalized"] = intent.instructions
        if usage is not None:
            self._usage.record(record.job_id, Feature.CUSTOM_PRODUCT, usage)
        return intent

    def _check_product(self, product_id: str | None) -> None:
        """Shape is validated in the schema; whether the product may be customised is not.

        This is where the check belongs once the storefront's product catalogue API exists: look
        the id up, refuse products that are not customisable, and confirm the submitted fields
        are the ones that product actually offers. Until then the id is recorded with the job
        and the storefront is trusted, which is why it stays optional.
        """
        if product_id:
            logger.info("Customisation requested for product %s", product_id)

    def _require_input(self, job_dir: Path, filename: str | None) -> Path:
        if not filename:
            raise ValidationError("The job record has no template filename")
        path = self._optional_input(job_dir, filename)
        if path is None:
            raise ValidationError("The product mock-up is missing: " + filename)
        return path

    def _optional_input(self, job_dir: Path, filename: str | None) -> Path | None:
        if not filename:
            return None
        path = job_dir / StorageKind.INPUT.value / filename
        return path if path.is_file() else None

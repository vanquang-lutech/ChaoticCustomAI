"""Token accounting.

Each OpenAI call appends one line to the day's ``usage.jsonl``. Append-only, one JSON object
per line: concurrent workers never rewrite each other's records, and a torn write can only
ever affect the last line.

There is no pricing here on purpose -- the service reports tokens per model, not money.
"""

import logging
from datetime import date, datetime, timedelta

from src.core.config import Settings
from src.core.enums import Feature
from src.schemas.usage import TokenUsage, UsageBucket, UsageRecord, UsageSummary
from src.services.storage_service import StorageService
from src.utils.file import append_jsonl, read_jsonl

logger = logging.getLogger(__name__)


class UsageService:
    def __init__(self, settings: Settings, storage: StorageService) -> None:
        self._settings = settings
        self._storage = storage

    def record(
        self,
        job_id: str,
        feature: Feature,
        usage: TokenUsage,
        when: datetime | None = None,
    ) -> UsageRecord:
        moment = when or self._settings.now()
        entry = UsageRecord(ts=moment, job_id=job_id, feature=feature, **usage.model_dump())
        append_jsonl(self._storage.usage_path(moment.date()), entry.model_dump(mode="json"))
        logger.info(
            "Usage %s %s model=%s total_tokens=%d",
            feature.value,
            job_id,
            usage.model,
            usage.total_tokens,
        )
        return entry

    def summarize(self, date_from: date, date_to: date) -> UsageSummary:
        """Aggregate the day files in the inclusive range, by model and by feature."""
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        summary = UsageSummary(date_from=date_from, date_to=date_to)
        by_model: dict[str, UsageBucket] = {}
        by_feature: dict[str, UsageBucket] = {}

        day = date_from
        while day <= date_to:
            for raw in read_jsonl(self._storage.usage_path(day)):
                self._accumulate(summary, by_model, by_feature, raw)
            day += timedelta(days=1)

        summary.by_model = sorted(by_model.values(), key=lambda bucket: -bucket.total_tokens)
        summary.by_feature = sorted(by_feature.values(), key=lambda bucket: -bucket.total_tokens)
        return summary

    def _accumulate(
        self,
        summary: UsageSummary,
        by_model: dict[str, UsageBucket],
        by_feature: dict[str, UsageBucket],
        raw: dict,
    ) -> None:
        try:
            record = UsageRecord.model_validate(raw)
        except Exception:  # noqa: BLE001 - one bad line must not sink the whole report
            logger.warning("Skipping unreadable usage line: %r", raw)
            return

        summary.calls += 1
        summary.input_tokens += record.input_tokens
        summary.output_tokens += record.output_tokens
        summary.total_tokens += record.total_tokens

        for table, key in ((by_model, record.model), (by_feature, record.feature.value)):
            bucket = table.setdefault(key, UsageBucket(key=key))
            bucket.calls += 1
            bucket.input_tokens += record.input_tokens
            bucket.output_tokens += record.output_tokens
            bucket.total_tokens += record.total_tokens

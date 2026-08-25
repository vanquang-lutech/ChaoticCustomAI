"""Token accounting. Tokens and model only -- this service does not price anything."""

from datetime import date, datetime

from pydantic import BaseModel

from src.core.enums import Feature


class TokenUsage(BaseModel):
    """What one OpenAI image call consumed."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class UsageRecord(TokenUsage):
    """One line of ``usage.jsonl``."""

    ts: datetime
    job_id: str
    feature: Feature


class UsageBucket(BaseModel):
    key: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class UsageSummary(BaseModel):
    date_from: date
    date_to: date
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    by_model: list[UsageBucket] = []
    by_feature: list[UsageBucket] = []

"""Token accounting: tokens and model, never money."""

from datetime import date, datetime

from src.core.dependencies import get_usage_service
from src.core.enums import Feature
from src.schemas.usage import TokenUsage


def _usage(model: str, total: int) -> TokenUsage:
    return TokenUsage(
        model=model, input_tokens=total // 4, output_tokens=total - total // 4, total_tokens=total
    )


def test_records_aggregate_by_model_and_feature():
    service = get_usage_service()
    day = datetime(2026, 8, 25, 10, 0)

    service.record("job-1", Feature.GENERATE_IMAGE, _usage("gpt-image-1", 100), when=day)
    service.record("job-2", Feature.GENERATE_IMAGE, _usage("gpt-image-1", 200), when=day)
    service.record("job-3", Feature.UPLOAD, _usage("gpt-image-2", 60), when=day)

    summary = service.summarize(date(2026, 8, 25), date(2026, 8, 25))

    assert summary.calls == 3
    assert summary.total_tokens == 360
    assert {bucket.key: bucket.total_tokens for bucket in summary.by_model} == {
        "gpt-image-1": 300,
        "gpt-image-2": 60,
    }
    assert {bucket.key: bucket.calls for bucket in summary.by_feature} == {
        "generate_image": 2,
        "upload": 1,
    }
    # Nothing in the report is a price.
    assert "cost" not in summary.model_dump_json()


def test_summary_spans_a_date_range_and_ignores_empty_days():
    service = get_usage_service()
    service.record("job-1", Feature.UPLOAD, _usage("m", 10), when=datetime(2026, 8, 24, 9, 0))
    service.record("job-2", Feature.UPLOAD, _usage("m", 20), when=datetime(2026, 8, 26, 9, 0))

    spanning = service.summarize(date(2026, 8, 24), date(2026, 8, 26))
    assert spanning.calls == 2
    assert spanning.total_tokens == 30

    single = service.summarize(date(2026, 8, 25), date(2026, 8, 25))
    assert single.calls == 0
    assert single.by_model == []


def test_a_reversed_range_is_normalised():
    service = get_usage_service()
    service.record("j", Feature.UPLOAD, _usage("m", 5), when=datetime(2026, 8, 24, 9, 0))

    summary = service.summarize(date(2026, 8, 26), date(2026, 8, 24))
    assert (summary.date_from, summary.date_to) == (date(2026, 8, 24), date(2026, 8, 26))
    assert summary.calls == 1


def test_a_corrupt_line_does_not_sink_the_report():
    service = get_usage_service()
    day = datetime(2026, 8, 25, 10, 0)
    service.record("job-1", Feature.UPLOAD, _usage("m", 40), when=day)

    from src.core.dependencies import get_storage_service

    path = get_storage_service().usage_path(day.date())
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{ this is not json\n")

    summary = service.summarize(date(2026, 8, 25), date(2026, 8, 25))
    assert summary.calls == 1
    assert summary.total_tokens == 40


def test_usage_endpoint_defaults_to_today(client):
    body = client.get("/api/v1/usage").json()
    assert body["calls"] == 0
    assert body["date_from"] == body["date_to"]

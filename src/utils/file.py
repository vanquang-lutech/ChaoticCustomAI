"""Filesystem helpers: traversal-safe path building, atomic writes, JSON and JSONL IO."""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from src.core.constants import EXTENSION_BY_CONTENT_TYPE
from src.core.exceptions import UnsupportedImageTypeError, ValidationError

logger = logging.getLogger(__name__)


def resolve_within(base: Path, *parts: str) -> Path:
    """Join ``parts`` onto ``base`` and refuse to leave it.

    Guards the file endpoint: a request for ``../../.env`` resolves outside ``base`` and is
    rejected here rather than served.
    """
    base_resolved = base.resolve()
    candidate = base_resolved.joinpath(*parts).resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise ValidationError("Resolved path escapes the storage root")
    return candidate


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write via a temp file in the same directory, then rename.

    A reader polling a job never sees a half-written PNG.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def write_json(path: Path, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    atomic_write_bytes(path, body.encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, payload: Any) -> None:
    """Append one JSON object as a single line.

    One ``write`` of one line in append mode is what keeps concurrent workers from
    interleaving or clobbering each other's usage records.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def read_jsonl(path: Path) -> list[Any]:
    """Read an append-only JSONL file, skipping any line that will not parse.

    A crash mid-append can leave one truncated line behind. Skipping it here is what makes the
    append-only design actually durable -- one damaged record must not take down a whole
    report.
    """
    if not path.exists():
        return []
    records = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping unparseable line %d of %s", number, path)
    return records


def extension_for_content_type(content_type: str | None) -> str:
    if not content_type:
        raise UnsupportedImageTypeError("Upload is missing a content type")
    extension = EXTENSION_BY_CONTENT_TYPE.get(content_type.split(";", 1)[0].strip().lower())
    if extension is None:
        raise UnsupportedImageTypeError(f"Unsupported image type: {content_type}")
    return extension


def find_by_stem(directory: Path, stem: str) -> Path | None:
    """The single file named ``<stem>.<anything>`` in ``directory``, if it exists."""
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.iterdir()):
        if candidate.is_file() and candidate.stem == stem:
            return candidate
    return None

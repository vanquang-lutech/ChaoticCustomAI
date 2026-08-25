"""Fixed names and patterns. Anything configurable belongs in ``config.py`` instead."""

import re

# --- Layout inside a job directory ---
JOB_RECORD_FILENAME = "job.json"
REQUEST_FILENAME = "request.json"
RESULT_FILENAME = "result.png"
ORIGINAL_STEM = "original"
USAGE_FILENAME = "usage.jsonl"

# --- Date formats used for the storage partitions and the log filenames ---
MONTH_DIR_FORMAT = "%Y_%m"
DAY_DIR_FORMAT = "%Y_%m_%d"

# --- Job ids look like 20260825T140344-a3f9c1 ---
JOB_ID_TIME_FORMAT = "%Y%m%dT%H%M%S"
JOB_ID_RANDOM_LENGTH = 6
JOB_ID_PATTERN = re.compile(r"^\d{8}T\d{6}-[0-9a-f]{6}$")

# --- Only these names may be requested through the file endpoint ---
# Must start with an alphanumeric, which rules out ".", "..", and dotfiles such as ".env".
SERVABLE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# --- Upload handling ---
EXTENSION_BY_CONTENT_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
CONTENT_TYPE_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

BYTES_PER_MB = 1024 * 1024

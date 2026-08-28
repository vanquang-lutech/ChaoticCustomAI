import re

# Layout
JOB_RECORD_FILENAME = "job.json"
REQUEST_FILENAME = "request.json"
RESULT_FILENAME = "result.png"
ORIGINAL_STEM = "original"
TEMPLATE_STEM = "template"
REFERENCE_STEM = "reference"
USAGE_FILENAME = "usage.jsonl"

# Date formats
MONTH_DIR_FORMAT = "%Y_%m"
DAY_DIR_FORMAT = "%Y_%m_%d"

# Job ids
JOB_ID_TIME_FORMAT = "%Y%m%dT%H%M%S"
JOB_ID_RANDOM_LENGTH = 6
JOB_ID_PATTERN = re.compile(r"^\d{8}T\d{6}-[0-9a-f]{6}$")

# --- Only these names may be requested through the file endpoint ---
# Must start with an alphanumeric, which rules out ".", "..", and dotfiles such as ".env".
SERVABLE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# Upload handling
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

# --- Product customisation ---
# Which fields a product offers is decided by the storefront, so the keys are not enumerated
# here. They are still constrained: a key must read like a field label, which keeps junk and
# smuggled prompt text out of the meta record and out of the prompt.
CUSTOM_FIELD_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]{0,39}$")
MAX_CUSTOM_FIELDS = 12
MAX_CUSTOM_FIELD_VALUE_LENGTH = 120
MAX_ORDER_NOTE_LENGTH = 1000
# Product ids come from the storefront. Validated for shape only; whether the id names a
# product that may be customised at all is checked once that catalogue API exists.
PRODUCT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")

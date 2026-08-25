"""Content hashing, used to tie a stored file to a log line without keeping the bytes."""

import hashlib


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def short_sha256(data: bytes, length: int = 12) -> str:
    return sha256_hex(data)[:length]

"""Logging setup: one log file per day, named ``logs/<yyyy_mm_dd>.log``."""

import logging
import sys
from pathlib import Path

from src.core.config import Settings
from src.core.constants import DAY_DIR_FORMAT

_CONFIGURED = False


class DailyFileHandler(logging.FileHandler):
    """Writes to ``<dir>/<yyyy_mm_dd>.log``, switching files when the day rolls over.

    ``TimedRotatingFileHandler`` would name the *rotated* files by date and keep the live one
    on a fixed name; we want the live file itself to carry the date, so long-running workers
    land in today's file without a restart.
    """

    def __init__(self, directory: Path, settings: Settings, encoding: str = "utf-8") -> None:
        self._directory = directory
        self._settings = settings
        self._current_day = self._today()
        directory.mkdir(parents=True, exist_ok=True)
        super().__init__(self._path_for(self._current_day), encoding=encoding, delay=True)

    def _today(self) -> str:
        return self._settings.now().strftime(DAY_DIR_FORMAT)

    def _path_for(self, day: str) -> str:
        return str(self._directory / f"{day}.log")

    def emit(self, record: logging.LogRecord) -> None:
        today = self._today()
        if today != self._current_day:
            self._current_day = today
            self.baseFilename = self._path_for(today)
            if self.stream:
                self.stream.close()
                self.stream = None
        super().emit(record)


def setup_logging(settings: Settings) -> None:
    """Attach a console and a daily-file handler to the root logger. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s [%(process)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    daily = DailyFileHandler(settings.log_dir, settings)
    daily.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers = [console, daily]

    # uvicorn installs its own handlers; let them bubble up to ours instead.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

    _CONFIGURED = True

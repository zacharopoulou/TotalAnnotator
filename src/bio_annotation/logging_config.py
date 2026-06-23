from __future__ import annotations

import logging

DEFAULT_LOG_LEVEL = "WARNING"
LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"


def configure_logging(level: str | int = DEFAULT_LOG_LEVEL) -> None:
    logging.basicConfig(
        level=_normalize_log_level(level),
        format=LOG_FORMAT,
        force=True,
    )


def _normalize_log_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    normalized = level.strip().upper()
    if not normalized:
        return logging.WARNING
    value = getattr(logging, normalized, None)
    if isinstance(value, int):
        return value
    raise ValueError(f"Unsupported log level: {level}")

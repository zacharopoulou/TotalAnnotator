"""Progress reporting for pipeline runs.

Annotator work emits `ProgressEvent`s; the default reporter logs them, and the
terminal UI swaps in a reporter that drives a spinner. Rendering never happens
in the pipeline layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from bio_annotation.entity_types import ANNOTATOR_DISPLAY_NAMES

logger = logging.getLogger(__name__)

# Approximate download sizes. Loading is cached by Hugging Face, so the download
# only happens when the model is not on disk yet.
ANNOTATOR_ASSET_HINTS: dict[str, str] = {
    "biobert": "~1.3 GB (3 models) to download if not cached",
    "apollo": "~740 MB to download if not cached",
    "clinicalbert": "~430 MB to download if not cached",
    "d4data": "~430 MB to download if not cached",
}

@dataclass(frozen=True)
class ProgressEvent:
    annotator: str
    phase: str  # "preflight" (model assets) or "annotate" (per document)
    event: str  # "start", "done" or "error"
    annotator_index: int | None = None
    annotator_total: int | None = None
    document_id: str | None = None
    pmid: str | None = None
    document_index: int | None = None
    document_total: int | None = None
    elapsed_seconds: float | None = None
    annotation_count: int | None = None
    reason: str | None = None

    @property
    def label(self) -> str:
        return ANNOTATOR_DISPLAY_NAMES.get(self.annotator, self.annotator)

    @property
    def document_label(self) -> str | None:
        if self.pmid:
            return f"PMID {self.pmid}"
        return self.document_id


ProgressReporter = Callable[[ProgressEvent], None]

def describe(event: ProgressEvent) -> str:
    """Human-readable one-line message for an event."""

    if event.phase == "preflight":
        return _describe_preflight(event)
    return _describe_annotate(event)

def log_progress(event: ProgressEvent) -> None:
    """Default reporter: log every event, warn on failures."""

    if event.event == "error":
        logger.warning("%s", describe(event))
    else:
        logger.info("%s", describe(event))

def _describe_preflight(event: ProgressEvent) -> str:
    if event.event == "start":
        hint = ANNOTATOR_ASSET_HINTS.get(event.annotator)
        message = f"Loading {event.label} model assets"
        return f"{message}; {hint}" if hint else message
    if event.event == "done":
        return f"Loaded {event.label} model assets{_elapsed(event)}"
    return f"{event.label} model assets unavailable{_elapsed(event)}: {event.reason}"

def _describe_annotate(event: ProgressEvent) -> str:
    prefix = ""
    if event.annotator_index and event.annotator_total:
        prefix = f"[{event.annotator_index}/{event.annotator_total}] "
    target = ""
    if event.document_label:
        target = f" on {event.document_label}"
    if event.document_index and event.document_total:
        target += f" (document {event.document_index}/{event.document_total})"
    if event.event == "start":
        return f"{prefix}Running {event.label}{target}"
    if event.event == "done":
        count = event.annotation_count or 0
        plural = "" if count == 1 else "s"
        message = f"{prefix}{event.label}{target}: {count} annotation{plural}{_elapsed(event)}"
        if not count and event.reason:
            message += f" - {event.reason}"
        return message
    return f"{prefix}{event.label} failed{target}{_elapsed(event)}: {event.reason}"

def _elapsed(event: ProgressEvent) -> str:
    if event.elapsed_seconds is None:
        return ""
    return f" in {event.elapsed_seconds:.1f}s"

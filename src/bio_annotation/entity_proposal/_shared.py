from __future__ import annotations

import hashlib
from typing import Any

from bio_annotation.entity_types import ENTITY_TYPE_ALIASES, normalize_entity_type
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

# Backwards-compatible name for older imports.
ENTITY_TYPE_MAP = ENTITY_TYPE_ALIASES


def pick_first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_offsets(document: Document, span_text: str, start: Any, end: Any) -> tuple[int | None, int | None]:
    if start is not None and end is not None:
        return int(start), int(end)

    if not span_text:
        return None, None

    text = document.text
    index = text.find(span_text)
    if index == -1:
        return None, None

    return index, index + len(span_text)


# Document.text joins title and body with "\n\n" (two newlines), but the
# HTML renderer and PubTator3's BioC payloads both use a single "\n".
# BERN2 and Flair receive Document.text, so their abstract offsets land
# one character past the canonical position. This helper shifts them back.
def shift_to_pubtator_offsets(
    document: Document, start: Any, end: Any
) -> tuple[Any, Any]:
    if start is None:
        return start, end
    title = (document.title or "").strip()
    if not title:
        return start, end
    body_start_in_input = len(title) + 2
    try:
        start_int = int(start)
    except (TypeError, ValueError):
        return start, end
    if start_int < body_start_in_input:
        return start, end
    new_end = end
    if end is not None:
        try:
            new_end = int(end) - 1
        except (TypeError, ValueError):
            new_end = end
    return start_int - 1, new_end


def sanitize_identifier(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text or text == "-":
        return None

    return text


def build_annotation_id(
    *,
    source: str,
    document_id: str,
    span_text: str,
    entity_type: str,
    start: int | None,
    end: int | None,
) -> str:
    raw = "|".join(
        [
            source,
            document_id,
            entity_type,
            str(start),
            str(end),
            span_text,
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{source}:{digest}"


def make_annotation(
    *,
    document: Document,
    source: str,
    span_text: str,
    entity_type: Any,
    start: Any = None,
    end: Any = None,
    canonical_id: Any = None,
    canonical_name: Any = None,
    confidence: Any = None,
) -> Annotation:
    normalized_span = str(span_text).strip()
    resolved_start, resolved_end = resolve_offsets(document, normalized_span, start, end)
    normalized_type = normalize_entity_type(entity_type)
    annotation_id = build_annotation_id(
        source=source,
        document_id=document.document_id,
        span_text=normalized_span,
        entity_type=normalized_type,
        start=resolved_start,
        end=resolved_end,
    )

    return Annotation(
        annotation_id=annotation_id,
        source=source,
        span_text=normalized_span,
        start=resolved_start,
        end=resolved_end,
        entity_type=normalized_type,
        canonical_id=sanitize_identifier(canonical_id),
        canonical_name=sanitize_identifier(canonical_name),
        confidence=coerce_float(confidence),
    )

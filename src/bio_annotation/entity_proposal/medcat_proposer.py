from __future__ import annotations

import json
import logging
import os
import warnings
from typing import Any, Callable
from urllib import error, request

from bio_annotation.entity_proposal._shared import make_annotation, pick_first
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

logger = logging.getLogger(__name__)


def _looks_like_entity_record(item: dict[str, Any]) -> bool:
    if not item:
        return False
    return bool(
        item.get("cui")
        or item.get("pretty_name")
        or item.get("source_value")
        or item.get("value")
        or item.get("mention")
    )


def _flatten_annotation_value(raw: Any) -> list[dict[str, Any]]:
    """Normalize MedCAT / MedCATservice annotation containers to flat entity dicts."""

    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            vals = [v for v in item.values() if isinstance(v, dict)]
            if (
                vals
                and len(vals) == len(item)
                and any(_looks_like_entity_record(v) for v in vals)
            ):
                out.extend(vals)
            else:
                out.append(item)
        return [x for x in out if _looks_like_entity_record(x)]
    if isinstance(raw, dict):
        nested_ent = raw.get("entities")
        if isinstance(nested_ent, dict) and nested_ent:
            inner = _flatten_annotation_value(nested_ent)
            if inner:
                return inner
        vals = [v for v in raw.values() if isinstance(v, dict)]
        if vals and len(vals) == len(raw) and any(_looks_like_entity_record(v) for v in vals):
            return vals
        if _looks_like_entity_record(raw):
            return [raw]
    return []


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict) and _looks_like_entity_record(item)]

    if not isinstance(payload, dict):
        return []

    # CogStack MedCATservice: { "result": { "annotations": ... } }
    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("annotations", "entities"):
            records = _flatten_annotation_value(result.get(key))
            if records:
                return records

    for key in ("entities", "annotations", "results", "denotations"):
        records = _flatten_annotation_value(payload.get(key))
        if records:
            return records

    if _looks_like_entity_record(payload):
        return [payload]
    return []


def parse_medcat_response(document: Document, payload: Any) -> list[Annotation]:
    annotations: list[Annotation] = []
    for record in _extract_records(payload):
        mention = pick_first(
            record.get("value"),
            record.get("source_value"),
            record.get("detected_name"),
            record.get("mention"),
            record.get("text"),
            record.get("pretty_name"),
        )
        if not mention:
            continue
        annotations.append(
            make_annotation(
                document=document,
                source="medcat",
                span_text=mention,
                entity_type=pick_first(
                    record.get("type"),
                    record.get("entity_type"),
                    record.get("tui"),
                    record.get("semantic_type"),
                    "concept",
                ),
                start=pick_first(
                    record.get("start"),
                    record.get("start_char"),
                    record.get("begin"),
                ),
                end=pick_first(
                    record.get("end"),
                    record.get("end_char"),
                ),
                canonical_id=pick_first(
                    record.get("cui"),
                    record.get("id"),
                    record.get("concept_id"),
                ),
                canonical_name=pick_first(
                    record.get("pretty_name"),
                    record.get("name"),
                    record.get("preferred_name"),
                ),
                confidence=pick_first(
                    record.get("acc"),
                    record.get("confidence"),
                    record.get("score"),
                ),
            )
        )
    return annotations


def call_medcat(document: Document, endpoint: str | None = None, timeout: int = 45) -> Any:
    target = endpoint or os.getenv("MEDCAT_API_URL")
    if not target:
        return None
    text = document.get_text()
    # CogStack MedCATservice POST /api/process uses {"content": {"text": ...}}; we also send top-level "text".
    body: dict[str, Any] = {
        "text": text,
        "content": {"text": text},
    }
    payload = json.dumps(body).encode("utf-8")
    http_request = request.Request(
        target,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "TotalAnnotator/medcat-client"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:  # noqa: BLE001
            detail = ""
        msg = f"{exc.code} {exc.reason} {detail}".strip()
        warnings.warn(f"MedCAT HTTP error for {target!r}: {msg}", UserWarning, stacklevel=2)
        logger.warning("MedCAT HTTP error %s", msg)
        return None
    except (error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        warnings.warn(f"MedCAT request to {target!r} failed: {exc}", UserWarning, stacklevel=2)
        logger.warning("MedCAT request failed: %s", exc)
        return None


def annotate_with_medcat(
    document: Document,
    *,
    response: Any = None,
    request_fn: Callable[[Document], Any] | None = None,
    endpoint: str | None = None,
) -> list[Annotation]:
    payload = response
    if payload is None and request_fn is not None:
        payload = request_fn(document)
    if payload is None:
        payload = call_medcat(document, endpoint=endpoint)
    return parse_medcat_response(document, payload)


__all__ = ["annotate_with_medcat", "call_medcat", "parse_medcat_response"]

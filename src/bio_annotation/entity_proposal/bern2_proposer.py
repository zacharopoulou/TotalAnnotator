from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib import error, parse, request

from bio_annotation.entity_proposal._shared import (
    make_annotation,
    pick_first,
    shift_to_pubtator_offsets,
)
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

DEFAULT_BERN2_API_URL = "http://bern2.korea.ac.kr/plain"
LOCAL_BERN2_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("annotations", "entities", "denotations"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def parse_bern2_response(document: Document, payload: Any) -> list[Annotation]:
    annotations: list[Annotation] = []
    for record in _extract_records(payload):
        span = record.get("span") if isinstance(record.get("span"), dict) else {}
        mention = pick_first(
            record.get("mention"),
            record.get("text"),
            record.get("span_text"),
            record.get("obj"),
        )
        if not mention:
            continue

        raw_start = pick_first(record.get("start"), span.get("begin"), span.get("start"))
        raw_end = pick_first(record.get("end"), span.get("end"))
        shifted_start, shifted_end = shift_to_pubtator_offsets(document, raw_start, raw_end)
        annotations.append(
            make_annotation(
                document=document,
                source="bern2",
                span_text=mention,
                entity_type=pick_first(
                    record.get("type"),
                    record.get("entity_type"),
                    record.get("obj"),
                ),
                start=shifted_start,
                end=shifted_end,
                canonical_id=pick_first(
                    _first_identifier(record.get("id")),
                    record.get("db_id"),
                    record.get("identifier"),
                ),
                canonical_name=pick_first(
                    record.get("normalizedName"),
                    record.get("preferred_name"),
                    record.get("name"),
                ),
                confidence=pick_first(
                    record.get("confidence"),
                    record.get("probability"),
                    record.get("prob"),
                    record.get("score"),
                ),
            )
        )

    return annotations


def _first_identifier(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def call_bern2(document: Document, endpoint: str | None = None, timeout: int = 30) -> Any:
    target = endpoint or os.getenv("BERN2_API_URL") or DEFAULT_BERN2_API_URL
    if not target.endswith("/plain"):
        target = target.rstrip("/") + "/plain"

    payload = json.dumps({"text": document.text}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    http_request = request.Request(target, data=payload, headers=headers, method="POST")

    try:
        opener = _request_opener_for_url(target)
        with opener.open(http_request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError(f"BERN2 request failed for {target}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"BERN2 returned invalid JSON from {target}: {exc}") from exc


def _request_opener_for_url(url: str) -> request.OpenerDirector:
    host = parse.urlparse(url).hostname
    if host in LOCAL_BERN2_HOSTS:
        return request.build_opener(request.ProxyHandler({}))
    return request.build_opener()


def annotate_with_bern2(
    document: Document,
    *,
    response: Any = None,
    request_fn: Callable[[Document], Any] | None = None,
    endpoint: str | None = None,
    timeout: int = 30,
) -> list[Annotation]:
    payload = response
    if payload is None and request_fn is not None:
        payload = request_fn(document)
    if payload is None:
        payload = call_bern2(document, endpoint=endpoint, timeout=timeout)
    return parse_bern2_response(document, payload)

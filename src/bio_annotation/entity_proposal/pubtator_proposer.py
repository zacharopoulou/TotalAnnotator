from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib import error, parse, request

from bio_annotation.entity_proposal._shared import make_annotation, pick_first
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation


def _parse_pubtator_document(document: Document, doc_payload: dict[str, Any]) -> list[Annotation]:
    annotations: list[Annotation] = []
    passages = doc_payload.get("passages", [])
    for passage in passages:
        passage_offset = int(passage.get("offset", 0))
        for record in passage.get("annotations", []):
            locations = record.get("locations", [])
            first_location = locations[0] if locations else {}
            start = pick_first(record.get("start"), first_location.get("offset"))
            length = first_location.get("length")
            end = record.get("end")
            if end is None and start is not None and length is not None:
                end = int(start) + int(length)

            infons = record.get("infons", {})
            mention = pick_first(record.get("text"), record.get("span_text"))
            if not mention:
                continue

            adjusted_start = int(start) + passage_offset if start is not None else None
            adjusted_end = int(end) + passage_offset if end is not None else None

            annotations.append(
                make_annotation(
                    document=document,
                    source="pubtator",
                    span_text=mention,
                    entity_type=pick_first(
                        infons.get("type"),
                        record.get("type"),
                        record.get("entity_type"),
                    ),
                    start=adjusted_start,
                    end=adjusted_end,
                    canonical_id=pick_first(
                        infons.get("identifier"),
                        record.get("identifier"),
                        record.get("id"),
                    ),
                    canonical_name=pick_first(infons.get("name"), record.get("name")),
                )
            )
    return annotations


def parse_pubtator_response(document: Document, payload: Any) -> list[Annotation]:
    if payload is None:
        return []

    if isinstance(payload, dict):
        if "documents" in payload and isinstance(payload["documents"], list):
            annotations: list[Annotation] = []
            for doc_payload in payload["documents"]:
                if isinstance(doc_payload, dict):
                    annotations.extend(_parse_pubtator_document(document, doc_payload))
            return annotations
        if "passages" in payload:
            return _parse_pubtator_document(document, payload)
        return []

    if isinstance(payload, list):
        annotations: list[Annotation] = []
        for doc_payload in payload:
            if isinstance(doc_payload, dict):
                annotations.extend(_parse_pubtator_document(document, doc_payload))
        return annotations

    return []


def call_pubtator(document: Document, endpoint: str | None = None, timeout: int = 30) -> Any:
    target = endpoint or os.getenv("PUBTATOR_API_URL")
    if not target or not document.pmid:
        return None

    params = parse.urlencode({"pmids": document.pmid, "concepts": "gene,disease,mutation,chemical,species,cellline"})
    request_url = f"{target}?{params}"
    http_request = request.Request(request_url, headers={"Accept": "application/json"}, method="GET")

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, json.JSONDecodeError):
        return None


def annotate_with_pubtator(
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
        payload = call_pubtator(document, endpoint=endpoint)
    return parse_pubtator_response(document, payload)

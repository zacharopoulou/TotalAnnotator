from __future__ import annotations

import json
import os
from typing import Any, Callable

from bio_annotation.clients.pubtator3 import (
    DEFAULT_EXPORT_FORMAT,
    PUBTATOR3_API_BASE_URL,
    PubTator3Client,
)
from bio_annotation.entity_proposal._shared import make_annotation, pick_first
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation


def _parse_bioc_document(document: Document, doc_payload: dict[str, Any]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for passage in doc_payload.get("passages", []):
        for record in passage.get("annotations", []):
            locations = record.get("locations", [])
            first_location = locations[0] if locations else {}
            start = pick_first(first_location.get("offset"), record.get("start"))
            length = first_location.get("length")
            end = pick_first(record.get("end"), int(start) + int(length) if start is not None and length is not None else None)

            mention = pick_first(record.get("text"), record.get("span_text"))
            if mention is None and start is not None and end is not None:
                mention = document.text[int(start) : int(end)]
            if not mention:
                continue

            infons = record.get("infons", {})
            annotations.append(
                make_annotation(
                    document=document,
                    source="pubtator3",
                    span_text=mention,
                    entity_type=pick_first(infons.get("type"), record.get("type"), record.get("entity_type")),
                    start=start,
                    end=end,
                    canonical_id=pick_first(infons.get("identifier"), record.get("identifier"), record.get("id")),
                    canonical_name=pick_first(infons.get("name"), record.get("name")),
                )
            )
    return annotations


def _parse_pubannotation_document(document: Document, payload: dict[str, Any]) -> list[Annotation]:
    text = str(payload.get("text") or document.text)
    annotations: list[Annotation] = []
    for record in payload.get("denotations", []):
        span = record.get("span", {})
        start = span.get("begin")
        end = span.get("end")
        mention = pick_first(record.get("text"), text[int(start) : int(end)] if start is not None and end is not None else None)
        if not mention:
            continue

        raw_object = str(record.get("obj") or "").strip()
        entity_type = raw_object.split(":", 1)[0] if ":" in raw_object else raw_object
        canonical_id = raw_object.split(":", 1)[1] if ":" in raw_object else None

        annotations.append(
            make_annotation(
                document=document,
                source="pubtator3",
                span_text=mention,
                entity_type=entity_type,
                start=start,
                end=end,
                canonical_id=canonical_id,
            )
        )
    return annotations


def _parse_pubtator_text(document: Document, payload: str) -> list[Annotation]:
    annotations: list[Annotation] = []
    for line in payload.splitlines():
        if not line.strip() or "|t|" in line or "|a|" in line:
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        _, start, end, mention, entity_type, canonical_id = parts[:6]
        try:
            start_offset = int(start)
            end_offset = int(end)
        except ValueError:
            continue
        annotations.append(
            make_annotation(
                document=document,
                source="pubtator3",
                span_text=mention,
                entity_type=entity_type,
                start=start_offset,
                end=end_offset,
                canonical_id=canonical_id,
            )
        )
    return annotations


def parse_pubtator3_response(document: Document, payload: Any) -> list[Annotation]:
    if payload is None:
        return []

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return _parse_pubtator_text(document, payload)

    if isinstance(payload, dict):
        if "documents" in payload and isinstance(payload["documents"], list):
            annotations: list[Annotation] = []
            for doc_payload in payload["documents"]:
                if isinstance(doc_payload, dict):
                    annotations.extend(_parse_bioc_document(document, doc_payload))
            return annotations
        if "PubTator3" in payload and isinstance(payload["PubTator3"], list):
            annotations: list[Annotation] = []
            for doc_payload in payload["PubTator3"]:
                if isinstance(doc_payload, dict):
                    annotations.extend(_parse_bioc_document(document, doc_payload))
            return annotations
        if "passages" in payload:
            return _parse_bioc_document(document, payload)
        if "denotations" in payload:
            return _parse_pubannotation_document(document, payload)
        return []

    if isinstance(payload, list):
        annotations: list[Annotation] = []
        for doc_payload in payload:
            if isinstance(doc_payload, dict):
                if "denotations" in doc_payload:
                    annotations.extend(_parse_pubannotation_document(document, doc_payload))
                else:
                    annotations.extend(_parse_bioc_document(document, doc_payload))
        return annotations

    return []


def build_pubtator3_text_payload(document: Document) -> str:
    return document.text


def _document_pmcid(document: Document) -> str | None:
    pubmed_record = document.metadata.get("pubmed_record") if isinstance(document.metadata, dict) else None
    if isinstance(pubmed_record, dict):
        value = pubmed_record.get("pmcid")
        if value:
            return str(value)
    return None


def call_pubtator3(
    document: Document,
    *,
    client: PubTator3Client | None = None,
    endpoint: str | None = None,
    timeout: int = 60,
    format: str = DEFAULT_EXPORT_FORMAT,
    text_mode: str = "auto",
    raw_text_bioconcept: str = "All",
    raw_text_max_attempts: int = 20,
    raw_text_poll_interval: float = 2.0,
    raw_text_poll_backoff: float = 1.5,
    raw_text_max_poll_interval: float = 15.0,
) -> Any:
    active_client = client or PubTator3Client(
        base_url=endpoint or os.getenv("PUBTATOR3_API_URL", PUBTATOR3_API_BASE_URL),
        timeout=timeout,
    )
    if text_mode == "raw_text" and document.text.strip():
        return active_client.annotate_text(
            build_pubtator3_text_payload(document),
            bioconcept=raw_text_bioconcept,
            max_attempts=raw_text_max_attempts,
            poll_interval=raw_text_poll_interval,
            poll_backoff=raw_text_poll_backoff,
            max_poll_interval=raw_text_max_poll_interval,
        )

    if document.source == "pubmed" and document.pmid:
        return active_client.fetch_publications_by_pmids([document.pmid], format=format)

    pmcid = _document_pmcid(document) if document.source == "pubmed" else None
    if pmcid:
        return active_client.fetch_publications_by_pmcids([pmcid], format=format)

    if document.text.strip():
        return active_client.annotate_text(
            build_pubtator3_text_payload(document),
            bioconcept=raw_text_bioconcept,
            max_attempts=raw_text_max_attempts,
            poll_interval=raw_text_poll_interval,
            poll_backoff=raw_text_poll_backoff,
            max_poll_interval=raw_text_max_poll_interval,
        )

    return None


def annotate_with_pubtator3(
    document: Document,
    *,
    response: Any = None,
    request_fn: Callable[[Document], Any] | None = None,
    client: PubTator3Client | None = None,
    endpoint: str | None = None,
    timeout: int = 60,
    format: str = DEFAULT_EXPORT_FORMAT,
    text_mode: str = "auto",
    raw_text_bioconcept: str = "All",
    raw_text_max_attempts: int = 20,
    raw_text_poll_interval: float = 2.0,
    raw_text_poll_backoff: float = 1.5,
    raw_text_max_poll_interval: float = 15.0,
) -> list[Annotation]:
    payload = response
    if payload is None and request_fn is not None:
        payload = request_fn(document)
    if payload is None:
        payload = call_pubtator3(
            document,
            client=client,
            endpoint=endpoint,
            timeout=timeout,
            format=format,
            text_mode=text_mode,
            raw_text_bioconcept=raw_text_bioconcept,
            raw_text_max_attempts=raw_text_max_attempts,
            raw_text_poll_interval=raw_text_poll_interval,
            raw_text_poll_backoff=raw_text_poll_backoff,
            raw_text_max_poll_interval=raw_text_max_poll_interval,
        )
    return parse_pubtator3_response(document, payload)


__all__ = [
    "annotate_with_pubtator3",
    "build_pubtator3_text_payload",
    "call_pubtator3",
    "parse_pubtator3_response",
]

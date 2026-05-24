from __future__ import annotations

import json
import os
from typing import Any, Callable

from bio_annotation.clients.pubtator3 import (
    DEFAULT_EXPORT_FORMAT,
    DEFAULT_TEXT_MAX_POLL_SECONDS,
    PUBTATOR3_API_BASE_URL,
    PubTator3Client,
    PollProgressCallback,
)
from bio_annotation.entity_proposal._shared import make_annotation, pick_first
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation


# PubTator3 publication-mode offsets are anchored to "title\nbody" (single
# newline). Use the same scheme for text-mode submissions so offsets returned
# by either path line up with the canonical text built in the web UI renderer.
def _document_annotation_text(document: Document) -> str:
    title = (document.title or "").strip()
    if document.full_text:
        body = document.full_text.strip()
    else:
        body = (document.abstract or "").strip()
    if title and body:
        return f"{title}\n{body}"
    return title or body


# Auto-mode fallback hinges on this. PubTator3 publication-mode can return a
# non-None payload that contains zero annotations (PMID known, nothing tagged),
# in which case we want to retry via text mode instead of returning empty.
def _payload_has_annotations(payload: Any) -> bool:
    if payload is None:
        return False
    if isinstance(payload, dict):
        documents = payload.get("documents") or payload.get("PubTator3") or []
        if isinstance(documents, list):
            for doc in documents:
                if not isinstance(doc, dict):
                    continue
                for passage in doc.get("passages", []):
                    if isinstance(passage, dict) and passage.get("annotations"):
                        return True
            return False
        if "passages" in payload:
            for passage in payload.get("passages", []):
                if isinstance(passage, dict) and passage.get("annotations"):
                    return True
            return False
        if "denotations" in payload:
            return bool(payload.get("denotations"))
        return False
    if isinstance(payload, list):
        return any(_payload_has_annotations(item) for item in payload)
    if isinstance(payload, str):
        for line in payload.splitlines():
            if not line.strip() or "|t|" in line or "|a|" in line:
                continue
            if "\t" in line:
                return True
        return False
    return False


def _parse_bioc_document(document: Document, doc_payload: dict[str, Any]) -> list[Annotation]:
    annotations: list[Annotation] = []
    source_text = _document_annotation_text(document)

    for passage in doc_payload.get("passages", []):
        for record in passage.get("annotations", []):
            locations = record.get("locations", [])
            first_location = locations[0] if locations else {}
            start = pick_first(first_location.get("offset"), record.get("start"))
            length = first_location.get("length")
            end = pick_first(
                record.get("end"),
                int(start) + int(length) if start is not None and length is not None else None,
            )

            mention = pick_first(record.get("text"), record.get("span_text"))
            if mention is None and start is not None and end is not None:
                mention = source_text[int(start) : int(end)]
            if not mention:
                continue

            infons = record.get("infons", {})
            annotations.append(
                make_annotation(
                    document=document,
                    source="pubtator3",
                    span_text=mention,
                    entity_type=pick_first(
                        infons.get("type"),
                        record.get("type"),
                        record.get("entity_type"),
                    ),
                    start=start,
                    end=end,
                    canonical_id=pick_first(
                        infons.get("identifier"),
                        record.get("identifier"),
                        record.get("id"),
                    ),
                    canonical_name=pick_first(infons.get("name"), record.get("name")),
                )
            )

    return annotations


def _parse_pubannotation_document(document: Document, payload: dict[str, Any]) -> list[Annotation]:
    text = str(payload.get("text") or _document_annotation_text(document))
    annotations: list[Annotation] = []

    for record in payload.get("denotations", []):
        span = record.get("span", {})
        start = span.get("begin")
        end = span.get("end")
        mention = pick_first(
            record.get("text"),
            text[int(start) : int(end)] if start is not None and end is not None else None,
        )
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
        lowered = payload.strip().lower()
        if not lowered or "not ready yet" in lowered:
            return []
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
    return _document_annotation_text(document)


def _document_pmcid(document: Document) -> str | None:
    metadata = document.metadata if isinstance(document.metadata, dict) else {}
    pubmed_record = metadata.get("pubmed_record")
    if isinstance(pubmed_record, dict):
        value = pubmed_record.get("pmcid")
        if value:
            return str(value)
    value = metadata.get("pmcid")
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
    mode: str = "auto",
    bioconcept: str = "All",
    poll_interval_seconds: float = 2.0,
    poll_backoff: float = 1.5,
    max_poll_interval_seconds: float = 15.0,
    max_poll_attempts: int = 15,
    max_poll_seconds: float = DEFAULT_TEXT_MAX_POLL_SECONDS,
    progress_callback: PollProgressCallback | None = None,
) -> Any:
    active_client = client or PubTator3Client(
        base_url=endpoint or os.getenv("PUBTATOR3_API_URL", PUBTATOR3_API_BASE_URL),
        timeout=timeout,
    )

    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"auto", "publication_only", "text_only"}:
        raise ValueError(
            "PubTator3 mode must be one of: 'auto', 'publication_only', 'text_only'."
        )

    if normalized_mode == "publication_only":
        if document.pmid:
            return active_client.fetch_publications_by_pmids([document.pmid], format=format)

        pmcid = _document_pmcid(document)
        if pmcid:
            return active_client.fetch_publications_by_pmcids([pmcid], format=format)
        return None

    if normalized_mode == "text_only":
        text_payload = build_pubtator3_text_payload(document)
        if not text_payload:
            return None
        return active_client.annotate_text(
            text_payload,
            bioconcept=bioconcept,
            max_attempts=max_poll_attempts,
            poll_interval=poll_interval_seconds,
            poll_backoff=poll_backoff,
            max_poll_interval=max_poll_interval_seconds,
            max_poll_seconds=max_poll_seconds,
            progress_callback=progress_callback,
        )

    publication_payload = call_pubtator3(
        document,
        client=active_client,
        format=format,
        mode="publication_only",
    )
    if _payload_has_annotations(publication_payload):
        return publication_payload

    text_payload = call_pubtator3(
        document,
        client=active_client,
        format=format,
        mode="text_only",
        bioconcept=bioconcept,
        poll_interval_seconds=poll_interval_seconds,
        poll_backoff=poll_backoff,
        max_poll_interval_seconds=max_poll_interval_seconds,
        max_poll_attempts=max_poll_attempts,
        max_poll_seconds=max_poll_seconds,
        progress_callback=progress_callback,
    )
    if text_payload is not None:
        return text_payload
    return publication_payload


def annotate_with_pubtator3(
    document: Document,
    *,
    response: Any = None,
    request_fn: Callable[[Document], Any] | None = None,
    client: PubTator3Client | None = None,
    endpoint: str | None = None,
    timeout: int = 60,
    format: str = DEFAULT_EXPORT_FORMAT,
    mode: str = "auto",
    bioconcept: str = "All",
    poll_interval_seconds: float = 2.0,
    poll_backoff: float = 1.5,
    max_poll_interval_seconds: float = 15.0,
    max_poll_attempts: int = 15,
    max_poll_seconds: float = DEFAULT_TEXT_MAX_POLL_SECONDS,
    progress_callback: PollProgressCallback | None = None,
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
            mode=mode,
            bioconcept=bioconcept,
            poll_interval_seconds=poll_interval_seconds,
            poll_backoff=poll_backoff,
            max_poll_interval_seconds=max_poll_interval_seconds,
            max_poll_attempts=max_poll_attempts,
            max_poll_seconds=max_poll_seconds,
            progress_callback=progress_callback,
        )
    return parse_pubtator3_response(document, payload)


__all__ = [
    "annotate_with_pubtator3",
    "build_pubtator3_text_payload",
    "call_pubtator3",
    "parse_pubtator3_response",
]

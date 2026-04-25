"""PubTator3 fetch source.

Wraps every PubTator3 endpoint that returns publication-shaped data:

* ``pmid`` / ``pmid_list``    - ``/publications/export/{format}?pmids=...``
* ``pmcid`` / ``pmcid_list``  - ``/publications/pmc_export/{format}?pmcids=...``
* ``query``                   - ``/search/?text=...`` then chained export by PMID
* ``raw_text``                - async ``request.cgi`` / ``retrieve.cgi`` flow

For PMID/PMCID/query modes we receive BioC documents and map each one to a
:class:`Document` with title and abstract extracted from the labelled
passages. The raw BioC payload is stashed in
``Document.metadata["pubtator3_payload"]`` so the PubTator3 annotator can
reuse it without a second network call.

For raw text we wrap the user input in a single :class:`Document` and stash
the parsed annotation response (whatever PubTator3 returned) in
``Document.metadata["pubtator3_payload"]`` so the annotator likewise skips
re-submitting.

The ``/entity/autocomplete`` and ``/relations`` endpoints are intentionally
out of scope here; they return entity IDs and relation graphs rather than
documents and belong in a separate resolver utility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bio_annotation.clients.pubtator3 import (
    DEFAULT_BIOCONCEPT,
    DEFAULT_EXPORT_FORMAT,
    PubTator3Client,
)
from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import FetchInput, FetchKind, check_supports

_TITLE_SECTION_TYPES = frozenset({"TITLE", "title", "Title", "front"})
_ABSTRACT_SECTION_TYPES = frozenset({"ABSTRACT", "abstract", "Abstract"})


@dataclass(slots=True)
class PubTator3Source:
    """Fetch source backed by every publication-returning PubTator3 endpoint."""

    name: str = "pubtator3"
    supported_inputs: frozenset[FetchKind] = frozenset(
        {"pmid", "pmid_list", "pmcid", "pmcid_list", "query", "raw_text"}
    )
    fields_provided: frozenset[str] = frozenset(
        {"pmid", "pmcid", "title", "abstract", "full_text", "annotations", "score"}
    )

    client: PubTator3Client = field(default_factory=PubTator3Client)
    format: str = DEFAULT_EXPORT_FORMAT
    full_text: bool = False
    bioconcept: str = DEFAULT_BIOCONCEPT
    max_search_pages: int = 1

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)

        if request.kind in {"pmid", "pmid_list"}:
            return self._fetch_by_pmids(request.pmids)
        if request.kind in {"pmcid", "pmcid_list"}:
            return self._fetch_by_pmcids(request.pmcids)
        if request.kind == "query":
            return self._fetch_by_query(request.query)
        if request.kind == "raw_text":
            return self._fetch_raw_text(request.text, request.text_id)
        return []

    def _fetch_by_pmids(self, pmids: tuple[str, ...]) -> list[Document]:
        if not pmids:
            return []
        payload = self.client.fetch_publications_by_pmids(
            pmids,
            format=self.format,
            full=self.full_text,
        )
        return _payload_to_documents(payload, with_full_text=self.full_text)

    def _fetch_by_pmcids(self, pmcids: tuple[str, ...]) -> list[Document]:
        if not pmcids:
            return []
        payload = self.client.fetch_publications_by_pmcids(
            pmcids,
            format=self.format,
            full=self.full_text,
        )
        return _payload_to_documents(payload, with_full_text=self.full_text)

    def _fetch_by_query(self, query: str) -> list[Document]:
        search_payload = self.client.search_publications(
            query,
            page=1,
            max_pages=self.max_search_pages,
        )
        results = _extract_search_results(search_payload)
        if not results:
            return []

        pmids = tuple(_coerce_pmid(hit) for hit in results)
        pmids = tuple(pmid for pmid in pmids if pmid)
        if not pmids:
            return []

        payload = self.client.fetch_publications_by_pmids(
            pmids,
            format=self.format,
            full=self.full_text,
        )
        documents = _payload_to_documents(payload, with_full_text=self.full_text)

        score_by_pmid = {
            _coerce_pmid(hit): _coerce_score(hit)
            for hit in results
            if _coerce_pmid(hit)
        }
        for document in documents:
            score = score_by_pmid.get(document.pmid)
            if score is not None:
                document.metadata["pubtator3_search_score"] = score
        return documents

    def _fetch_raw_text(self, text: str, text_id: str) -> list[Document]:
        cleaned = text or ""
        if not cleaned.strip():
            return []
        response = self.client.annotate_text(
            cleaned,
            bioconcept=self.bioconcept,
        )
        document = _build_raw_text_document(cleaned, text_id, response)
        return [document]


def _payload_to_documents(
    payload: Any,
    *,
    with_full_text: bool,
) -> list[Document]:
    documents: list[Document] = []
    for raw in _extract_bioc_documents(payload):
        document = _build_document(raw, with_full_text=with_full_text)
        if document is not None:
            documents.append(document)
    return documents


def _extract_bioc_documents(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("documents", "PubTator3"):
            container = payload.get(key)
            if isinstance(container, list):
                return [item for item in container if isinstance(item, dict)]
    return []


def _extract_search_results(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    return [hit for hit in results if isinstance(hit, dict)]


def _build_document(
    raw: dict[str, Any],
    *,
    with_full_text: bool,
) -> Document | None:
    pmid = _extract_pmid(raw)
    if not pmid:
        return None

    title, abstract, body_text = _extract_passages(raw)
    pmcid = _extract_pmcid(raw)

    metadata: dict[str, Any] = {
        "pubtator3_payload": {"documents": [raw]},
    }
    if pmcid:
        metadata["pmcid"] = pmcid

    full_text = body_text if with_full_text and body_text else None

    return Document(
        document_id=f"PMID:{pmid}",
        pmid=pmid,
        title=title,
        abstract=abstract,
        full_text=full_text,
        source="pubtator3",
        metadata=metadata,
    )


def _build_raw_text_document(text: str, text_id: str, response: Any) -> Document:
    cleaned_id = (text_id or "").strip() or "RAW:1"
    payload = _coerce_raw_text_payload(response)
    metadata: dict[str, Any] = {
        "pubtator3_payload": payload,
        "pubtator3_input_kind": "raw_text",
    }
    return Document(
        document_id=cleaned_id,
        pmid=None,
        title="",
        abstract=text,
        full_text=None,
        source="pubtator3",
        metadata=metadata,
    )


def _coerce_raw_text_payload(response: Any) -> Any:
    """Pass through the annotator-friendly payload shape.

    PubTator3's raw-text endpoint can hand back BioC-JSON, PubAnnotation, or
    the legacy PubTator tab-separated text. We do not parse it here - the
    PubTator3 annotator already understands all three. We just stash the
    response so the annotator has a cached copy.
    """

    if response is None:
        return None
    return response


def _extract_pmid(raw: dict[str, Any]) -> str | None:
    raw_id = raw.get("id")
    if raw_id is not None:
        cleaned = str(raw_id).strip()
        if cleaned:
            return cleaned

    infons = raw.get("infons")
    if isinstance(infons, dict):
        for key in ("article-id_pmid", "pmid"):
            value = infons.get(key)
            if value:
                return str(value).strip()
    return None


def _extract_pmcid(raw: dict[str, Any]) -> str | None:
    infons = raw.get("infons")
    if isinstance(infons, dict):
        for key in ("article-id_pmc", "pmcid"):
            value = infons.get(key)
            if value:
                return str(value).strip()
    return None


def _extract_passages(raw: dict[str, Any]) -> tuple[str, str, str]:
    """Return ``(title, abstract, body_text)`` extracted from BioC passages.

    ``body_text`` joins every passage that is not the title or abstract,
    used when the caller has asked for full text.
    """

    passages = raw.get("passages")
    if not isinstance(passages, list):
        return "", "", ""

    title_parts: list[str] = []
    abstract_parts: list[str] = []
    body_parts: list[str] = []
    unlabeled: list[str] = []

    for passage in passages:
        if not isinstance(passage, dict):
            continue
        text = str(passage.get("text") or "").strip()
        if not text:
            continue
        section = _passage_section(passage)
        if section in _TITLE_SECTION_TYPES:
            title_parts.append(text)
        elif section in _ABSTRACT_SECTION_TYPES:
            abstract_parts.append(text)
        elif section:
            body_parts.append(text)
        else:
            unlabeled.append(text)

    if not title_parts and unlabeled:
        title_parts = [unlabeled[0]]
        unlabeled = unlabeled[1:]
    if not abstract_parts and unlabeled:
        abstract_parts = unlabeled
        unlabeled = []
    if unlabeled:
        body_parts = unlabeled + body_parts

    return (
        " ".join(title_parts),
        " ".join(abstract_parts),
        "\n\n".join(body_parts),
    )


def _passage_section(passage: dict[str, Any]) -> str:
    infons = passage.get("infons")
    if isinstance(infons, dict):
        for key in ("section_type", "type", "section"):
            value = infons.get(key)
            if value:
                return str(value)
    return ""


def _coerce_pmid(hit: dict[str, Any]) -> str:
    for key in ("pmid", "_id"):
        value = hit.get(key)
        if value is not None:
            cleaned = str(value).strip()
            if cleaned:
                return cleaned
    return ""


def _coerce_score(hit: dict[str, Any]) -> float | None:
    value = hit.get("score")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["PubTator3Source"]

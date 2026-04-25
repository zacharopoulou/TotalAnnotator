"""PubTator3 fetch source.

Calls the PubTator3 publication-export endpoint via the existing
:class:`PubTator3Client` and converts each returned BioC document into a
:class:`Document`. The raw BioC-JSON payload is stashed in
``Document.metadata["pubtator3_payload"]`` so the PubTator3 annotator can
consume it later without a second network call.

Supported inputs: ``pmid`` and ``pmid_list`` only. PubTator3 does not
expose a query endpoint, and raw text goes through the asynchronous
annotation flow handled by the annotator (not this source).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bio_annotation.clients.pubtator3 import DEFAULT_EXPORT_FORMAT, PubTator3Client
from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import FetchInput, FetchKind, check_supports

_TITLE_SECTION_TYPES = frozenset({"TITLE", "title", "Title", "front"})
_ABSTRACT_SECTION_TYPES = frozenset({"ABSTRACT", "abstract", "Abstract"})


@dataclass(slots=True)
class PubTator3Source:
    """Fetch source backed by the PubTator3 publication-export API."""

    name: str = "pubtator3"
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid", "pmid_list"})
    fields_provided: frozenset[str] = frozenset(
        {"pmid", "pmcid", "title", "abstract", "annotations"}
    )

    client: PubTator3Client = field(default_factory=PubTator3Client)
    format: str = DEFAULT_EXPORT_FORMAT

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)
        if not request.pmids:
            return []
        payload = self.client.fetch_publications_by_pmids(
            request.pmids,
            format=self.format,
        )
        return _payload_to_documents(payload)


def _payload_to_documents(payload: Any) -> list[Document]:
    documents: list[Document] = []
    for raw in _extract_bioc_documents(payload):
        document = _build_document(raw)
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


def _build_document(raw: dict[str, Any]) -> Document | None:
    pmid = _extract_pmid(raw)
    if not pmid:
        return None

    title, abstract = _extract_title_and_abstract(raw)
    pmcid = _extract_pmcid(raw)

    metadata: dict[str, Any] = {
        "pubtator3_payload": {"documents": [raw]},
    }
    if pmcid:
        metadata["pmcid"] = pmcid

    return Document(
        document_id=f"PMID:{pmid}",
        pmid=pmid,
        title=title,
        abstract=abstract,
        full_text=None,
        source="pubtator3",
        metadata=metadata,
    )


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


def _extract_title_and_abstract(raw: dict[str, Any]) -> tuple[str, str]:
    passages = raw.get("passages")
    if not isinstance(passages, list):
        return "", ""

    title_parts: list[str] = []
    abstract_parts: list[str] = []
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
        else:
            unlabeled.append(text)

    if not title_parts and unlabeled:
        title_parts = [unlabeled[0]]
        unlabeled = unlabeled[1:]
    if not abstract_parts and unlabeled:
        abstract_parts = unlabeled

    return " ".join(title_parts), " ".join(abstract_parts)


def _passage_section(passage: dict[str, Any]) -> str:
    infons = passage.get("infons")
    if isinstance(infons, dict):
        for key in ("section_type", "type", "section"):
            value = infons.get(key)
            if value:
                return str(value)
    return ""


__all__ = ["PubTator3Source"]

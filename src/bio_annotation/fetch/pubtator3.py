"""PubTator3-backed fetch: BioC export -> :class:`~bio_annotation.schemas.document.Document`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bio_annotation.clients.pubtator3 import (
    DEFAULT_BIOCONCEPT,
    DEFAULT_EXPORT_FORMAT,
    PubTator3Client,
)
from bio_annotation.fetch.input import FetchInput, FetchKind, check_supports
from bio_annotation.schemas.document import Document

_TITLE_SECTION_TYPES = frozenset({"TITLE", "title", "Title", "front"})
_ABSTRACT_SECTION_TYPES = frozenset({"ABSTRACT", "abstract", "Abstract"})


@dataclass(slots=True)
class PubTator3Source:
    """PubTator3 BioC publication export by PMID or PMCID."""

    name: str = "pubtator3"
    supported_inputs: frozenset[FetchKind] = frozenset(
        {"pmid", "pmid_list", "pmcid", "pmcid_list"}
    )
    fields_provided: frozenset[str] = frozenset(
        {"pmid", "pmcid", "title", "abstract", "full_text", "annotations"}
    )

    client: PubTator3Client = field(default_factory=PubTator3Client)
    format: str = DEFAULT_EXPORT_FORMAT
    full_text: bool = False
    bioconcept: str = DEFAULT_BIOCONCEPT

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)
        fields = request.fields_for(self.name)
        effective_full_text = self.full_text or (fields is not None and "full_text" in fields)

        if request.kind in {"pmid", "pmid_list"}:
            return self._fetch_by_pmids(
                request.pmids,
                fields=fields,
                with_full_text=effective_full_text,
            )
        if request.kind in {"pmcid", "pmcid_list"}:
            return self._fetch_by_pmcids(
                request.pmcids,
                fields=fields,
                with_full_text=effective_full_text,
            )
        return []

    def _fetch_by_pmids(
        self,
        pmids: tuple[str, ...],
        *,
        fields: frozenset[str] | None,
        with_full_text: bool,
    ) -> list[Document]:
        if not pmids:
            return []
        payload = self.client.fetch_publications_by_pmids(
            pmids,
            format=self.format,
            full=with_full_text,
        )
        return _payload_to_documents(
            payload,
            with_full_text=with_full_text,
            fields=fields,
        )

    def _fetch_by_pmcids(
        self,
        pmcids: tuple[str, ...],
        *,
        fields: frozenset[str] | None,
        with_full_text: bool,
    ) -> list[Document]:
        if not pmcids:
            return []
        payload = self.client.fetch_publications_by_pmcids(
            pmcids,
            format=self.format,
            full=with_full_text,
        )
        return _payload_to_documents(
            payload,
            with_full_text=with_full_text,
            fields=fields,
        )

# A. Payload to Document

def _payload_to_documents(
    payload: Any,
    *,
    with_full_text: bool,
    fields: frozenset[str] | None = None,
) -> list[Document]:
    documents: list[Document] = []
    for raw in _extract_bioc_documents(payload):
        document = _build_document(raw, with_full_text=with_full_text, fields=fields)
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


def _build_document(
    raw: dict[str, Any],
    *,
    with_full_text: bool,
    fields: frozenset[str] | None = None,
) -> Document | None:
    pmid = _extract_pmid(raw)
    if not pmid:
        return None

    title, abstract, body_text = _extract_passages(raw)
    pmcid = _extract_pmcid(raw)

    if fields is None:
        metadata: dict[str, Any] = {
            "pubtator3_payload": {"documents": [raw]},
        }
        if pmcid:
            metadata["pmcid"] = pmcid
        full_text = body_text if with_full_text and body_text else None
        out_title, out_abstract = title, abstract
    else:
        metadata = {}
        if pmcid and "pmcid" in fields:
            metadata["pmcid"] = pmcid
        if "annotations" in fields:
            metadata["pubtator3_payload"] = {"documents": [raw]}
        out_title = title if "title" in fields else ""
        out_abstract = abstract if "abstract" in fields else ""
        if with_full_text and "full_text" in fields and body_text:
            full_text = body_text
        else:
            full_text = None

    return Document(
        document_id=f"PMID:{pmid}",
        pmid=pmid,
        title=out_title,
        abstract=out_abstract,
        full_text=full_text,
        source="pubtator3",
        metadata=metadata,
    )


# B. BioC parsing helpers

def _iter_infons_dicts(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """BioC metadata often lives on the first passage, not on the document node."""

    out: list[dict[str, Any]] = []
    root = raw.get("infons")
    if isinstance(root, dict) and root:
        out.append(root)
    passages = raw.get("passages")
    if isinstance(passages, list):
        for passage in passages:
            if not isinstance(passage, dict):
                continue
            inf = passage.get("infons")
            if isinstance(inf, dict) and inf:
                out.append(inf)
    return out


def _extract_pmid(raw: dict[str, Any]) -> str | None:
    """Prefer explicit PMID infons; do not trust top-level ``id`` (often PMC digits in PubTator3)."""

    for infons in _iter_infons_dicts(raw):
        for key in ("article-id_pmid", "pmid"):
            value = infons.get(key)
            if value:
                return str(value).strip()

    raw_id = raw.get("id")
    if raw_id is not None:
        cleaned = str(raw_id).strip()
        if cleaned:
            return cleaned
    return None


def _extract_pmcid(raw: dict[str, Any]) -> str | None:
    for infons in _iter_infons_dicts(raw):
        for key in ("article-id_pmc", "pmcid"):
            value = infons.get(key)
            if value:
                return str(value).strip()
    return None


def _extract_passages(raw: dict[str, Any]) -> tuple[str, str, str]:
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


__all__ = ["PubTator3Source"]

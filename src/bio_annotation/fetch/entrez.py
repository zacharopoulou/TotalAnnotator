"""NCBI E-utilities fetch via :class:`~bio_annotation.clients.entrez.EntrezClient`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bio_annotation.clients.entrez import EntrezClient
from bio_annotation.fetch.input import FetchInput, FetchKind, check_supports
from bio_annotation.schemas.document import Document

FetchRecordFn = Callable[[str], dict[str, Any]]

_CORE_FIELDS = frozenset({"pmid", "title", "abstract", "year"})


@dataclass(slots=True)
class EntrezSource:
    """PubMed records for known PMIDs (efetch). No query support."""

    name: str = "entrez"
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid", "pmid_list"})
    fields_provided: frozenset[str] = frozenset(
        {
            "pmid",
            "pmcid",
            "doi",
            "title",
            "abstract",
            "structured_abstract",
            "year",
            "authors",
            "affiliations",
            "journal",
            "journal_abbrev",
            "volume",
            "issue",
            "pages",
            "language",
            "publication_type",
            "country",
            "pub_date",
            "epub_date",
            "received_date",
            "accepted_date",
            "medline_date",
            "entrez_date",
            "revision_date",
            "keywords",
            "mesh_terms",
            "chemicals",
            "gene_symbols",
            "supplemental_mesh",
            "grants",
            "elinks",
        }
    )

    timeout: int = 30
    enrichments: tuple[str, ...] = ()

    client: EntrezClient | None = None
    fetch_record: FetchRecordFn | None = field(default=None)

    def __post_init__(self) -> None:
        if self.client is None:
            object.__setattr__(self, "client", EntrezClient(timeout=self.timeout))
        if self.fetch_record is None:
            self.fetch_record = self._default_fetch_record

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)

        effective_fields = request.fields_for(self.name)
        documents: list[Document] = []
        for pmid in request.pmids:
            document = self._fetch_one(pmid, effective_fields)
            if document is not None:
                documents.append(document)
        return documents

    def _fetch_one(
        self,
        pmid: str,
        fields: frozenset[str] | None,
    ) -> Document | None:
        assert self.fetch_record is not None
        record = self.fetch_record(pmid)
        if not isinstance(record, dict):
            return None
        return _record_to_document(record, fields=fields, fallback_pmid=pmid)

    def _default_fetch_record(self, pmid: str) -> dict[str, Any]:
        assert self.client is not None
        return self.client.fetch_pubmed(
            pmid,
            enrichments=list(self.enrichments) if self.enrichments else None,
        )


# A. Record to Document

def _record_to_document(
    record: dict[str, Any],
    *,
    fields: frozenset[str] | None,
    fallback_pmid: str,
) -> Document:
    pmid = _coerce_str(record.get("pmid")) or _coerce_str(fallback_pmid)
    title = _coerce_str(record.get("title"))
    abstract = _coerce_str(record.get("abstract"))
    year = _coerce_optional_str(record.get("year"))
    pmcid = _coerce_optional_str(record.get("pmcid"))

    filtered = _filter_record(record, fields)

    metadata: dict[str, Any] = {"pubmed_record": filtered}
    if pmcid:
        metadata["pmcid"] = pmcid

    document_id = f"PMID:{pmid}" if pmid else f"ENTREZ:{id(record)}"

    return Document(
        document_id=document_id,
        pmid=pmid or None,
        title=title,
        abstract=abstract,
        full_text=None,
        source="entrez",
        year=year,
        metadata=metadata,
    )


def _filter_record(
    record: dict[str, Any],
    fields: frozenset[str] | None,
) -> dict[str, Any]:
    if fields is None:
        return dict(record)
    keep = fields | _CORE_FIELDS
    return {key: value for key, value in record.items() if key in keep}


# B. Internal helpers

def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


__all__ = ["EntrezSource", "FetchRecordFn"]

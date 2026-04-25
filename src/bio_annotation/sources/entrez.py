"""Entrez (NCBI E-utilities) fetch source.

Wraps the existing :func:`fetch_pubmed_record` and :func:`search_pubmed_pmids`
helpers that already live in :mod:`bio_annotation.io`. Each PubMed record is
mapped onto a :class:`Document` with the full record dict stashed in
``Document.metadata["pubmed_record"]`` (matching the convention used by the
existing ``document_loader``).

Supported inputs:

* ``pmid``       - one PMID, one efetch call
* ``pmid_list``  - many PMIDs, one efetch call per PMID
* ``query``      - PubMed query, resolved via esearch then loop-fetched

A future chunk can add batched efetch (one HTTP call per N PMIDs) for big
queries; this version keeps things simple and reuses what is already in tree.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bio_annotation.io.readers import fetch_pubmed_record
from bio_annotation.io.search import search_pubmed_pmids
from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import FetchInput, FetchKind, check_supports

FetchRecordFn = Callable[[str], dict[str, Any]]
SearchPmidsFn = Callable[[str], list[str]]

_CORE_FIELDS = frozenset({"pmid", "title", "abstract", "year"})


@dataclass(slots=True)
class EntrezSource:
    """Fetch source backed by NCBI E-utilities (efetch + esearch)."""

    name: str = "entrez"
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid", "pmid_list", "query"})
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
    max_query_results: int = 200

    fetch_record: FetchRecordFn | None = field(default=None)
    search_pmids: SearchPmidsFn | None = field(default=None)

    def __post_init__(self) -> None:
        if self.fetch_record is None:
            self.fetch_record = self._default_fetch_record
        if self.search_pmids is None:
            self.search_pmids = self._default_search_pmids

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)

        if request.kind == "query":
            assert self.search_pmids is not None
            pmids = tuple(self.search_pmids(request.query))
        else:
            pmids = request.pmids

        documents: list[Document] = []
        for pmid in pmids:
            document = self._fetch_one(pmid, request.fields)
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
        return fetch_pubmed_record(
            pmid,
            timeout=self.timeout,
            enrichments=list(self.enrichments) if self.enrichments else None,
        )

    def _default_search_pmids(self, query: str) -> list[str]:
        return search_pubmed_pmids(
            query,
            max_results=self.max_query_results,
            timeout=self.timeout,
        )


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


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


__all__ = ["EntrezSource", "FetchRecordFn", "SearchPmidsFn"]

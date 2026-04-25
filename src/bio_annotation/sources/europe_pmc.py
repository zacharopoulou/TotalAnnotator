"""Europe PMC fetch source.

Europe PMC is a "metadata-rich" sibling of PubMed: every article record carries
citation counts, open-access flags, license, full-text URLs (DOI / PMC), and a
``inEPMC`` flag indicating whether the JATS XML body is available for direct
download. The same ``/search`` endpoint accepts both free-text queries and
ID-based lookups (``EXT_ID:`` for PMIDs, ``PMCID:`` for PMCIDs), so a single
client method covers four of our five supported input kinds.

Raw text is intentionally rejected: Europe PMC, like Entrez, is a lookup
service with no "submit text" endpoint. Use :class:`RawTextSource` instead.

The source stashes the full Europe PMC result dict in
``Document.metadata["epmc_meta"]`` so downstream consumers (UI, exporters,
annotators) can dig into MeSH terms, chemicals, references, citations, etc.
without a second network call. Top-level convenience copies of the most-asked
fields (``citation_count``, ``is_open_access``, ``in_epmc``, ``full_text_urls``)
are also exposed in ``metadata`` for cheap access from the orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bio_annotation.clients.europe_pmc import EuropePmcClient
from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import (
    FetchInput,
    FetchKind,
    check_supports,
)


_CORE_FIELDS = frozenset({"pmid", "pmcid", "title", "abstract", "year"})


@dataclass(slots=True)
class EuropePmcSource:
    """Fetch source backed by the Europe PMC REST API."""

    name: str = "europe_pmc"
    supported_inputs: frozenset[FetchKind] = frozenset(
        {"pmid", "pmid_list", "pmcid", "pmcid_list", "query"}
    )
    fields_provided: frozenset[str] = frozenset(
        {
            "pmid",
            "pmcid",
            "doi",
            "title",
            "abstract",
            "year",
            "authors",
            "journal",
            "mesh_terms",
            "keywords",
            "is_open_access",
            "in_epmc",
            "citation_count",
            "full_text_urls",
            "license",
        }
    )

    client: EuropePmcClient = field(default_factory=EuropePmcClient)
    max_search_pages: int = 1
    page_size: int | None = None

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)

        if request.kind in {"pmid", "pmid_list"}:
            payload = self.client.fetch_by_pmids(
                request.pmids,
                max_pages=self.max_search_pages,
                page_size=self.page_size,
            )
        elif request.kind in {"pmcid", "pmcid_list"}:
            payload = self.client.fetch_by_pmcids(
                request.pmcids,
                max_pages=self.max_search_pages,
                page_size=self.page_size,
            )
        elif request.kind == "query":
            payload = self.client.search(
                request.query,
                max_pages=self.max_search_pages,
                page_size=self.page_size,
            )
        else:  # pragma: no cover - guarded by check_supports
            return []

        results = self._extract_results(payload)
        documents = [self._build_document(result) for result in results]

        effective_fields = request.fields_for(self.name)
        if effective_fields is not None:
            documents = [
                self._apply_field_filter(d, effective_fields) for d in documents
            ]

        return documents

    @staticmethod
    def _extract_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
        result_list = payload.get("resultList") if isinstance(payload, dict) else None
        if not isinstance(result_list, dict):
            return []
        results = result_list.get("result", [])
        return [r for r in results if isinstance(r, dict)]

    def _build_document(self, result: dict[str, Any]) -> Document:
        pmid = _clean_str(result.get("pmid"))
        pmcid = _clean_str(result.get("pmcid"))
        title = _clean_str(result.get("title"))
        abstract = _clean_str(result.get("abstractText"))
        year = _clean_str(result.get("pubYear"))

        document_id = self._build_document_id(result, pmid=pmid, pmcid=pmcid)

        full_text_urls = _extract_full_text_urls(result)
        metadata: dict[str, Any] = {
            "epmc_meta": result,
            "epmc_id": _clean_str(result.get("id")),
            "epmc_source": _clean_str(result.get("source")),
        }
        if pmcid:
            metadata["pmcid"] = pmcid
        doi = _clean_str(result.get("doi"))
        if doi:
            metadata["doi"] = doi
        cited_by = result.get("citedByCount")
        if isinstance(cited_by, int):
            metadata["citation_count"] = cited_by
        is_oa = _yn_to_bool(result.get("isOpenAccess"))
        if is_oa is not None:
            metadata["is_open_access"] = is_oa
        in_epmc = _yn_to_bool(result.get("inEPMC"))
        if in_epmc is not None:
            metadata["in_epmc"] = in_epmc
        license_value = _clean_str(result.get("license"))
        if license_value:
            metadata["license"] = license_value
        if full_text_urls:
            metadata["full_text_urls"] = full_text_urls

        return Document(
            document_id=document_id,
            pmid=pmid or None,
            title=title,
            abstract=abstract,
            year=year or None,
            source="europe_pmc",
            metadata=metadata,
        )

    @staticmethod
    def _build_document_id(
        result: dict[str, Any],
        *,
        pmid: str,
        pmcid: str,
    ) -> str:
        if pmid:
            return f"PMID:{pmid}"
        if pmcid:
            return pmcid if pmcid.startswith("PMC") else f"PMC{pmcid}"
        epmc_id = _clean_str(result.get("id"))
        epmc_source = _clean_str(result.get("source")) or "EPMC"
        if epmc_id:
            return f"{epmc_source}:{epmc_id}"
        return "EPMC:UNKNOWN"

    @staticmethod
    def _apply_field_filter(
        document: Document,
        fields: frozenset[str],
    ) -> Document:
        """Trim metadata to fields the user asked for, keeping core fields."""

        keep = set(fields) | _CORE_FIELDS
        new_meta: dict[str, Any] = {}
        for key, value in document.metadata.items():
            if key in keep:
                new_meta[key] = value
        if "epmc_meta" in keep or "metadata" in keep:
            new_meta.setdefault("epmc_meta", document.metadata.get("epmc_meta", {}))
        document.metadata = new_meta
        return document


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _yn_to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"Y", "YES", "TRUE", "1"}:
        return True
    if text in {"N", "NO", "FALSE", "0"}:
        return False
    return None


def _extract_full_text_urls(result: dict[str, Any]) -> list[dict[str, str]]:
    container = result.get("fullTextUrlList")
    if not isinstance(container, dict):
        return []
    items = container.get("fullTextUrl", [])
    if not isinstance(items, list):
        return []
    extracted: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        extracted.append(
            {
                "url": _clean_str(item.get("url")),
                "site": _clean_str(item.get("site")),
                "availability": _clean_str(item.get("availability")),
                "document_style": _clean_str(item.get("documentStyle")),
            }
        )
    return extracted


__all__ = ["EuropePmcSource"]

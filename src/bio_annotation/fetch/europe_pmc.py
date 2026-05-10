"""Europe PMC fetch source: metadata-rich records (citations, OA, full-text URLs)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

from bio_annotation.clients.entrez import EntrezClient
from bio_annotation.clients.europe_pmc import EuropePmcClient
from bio_annotation.fetch.input import FetchInput, FetchKind, check_supports
from bio_annotation.schemas.document import Document

logger = logging.getLogger(__name__)

# Europe PMC ``result`` JSON keys for each logical :attr:`fields_provided` name.
_EPMC_RESULT_KEY_BY_LOGICAL: dict[str, str] = {
    "pmid": "pmid",
    "pmcid": "pmcid",
    "doi": "doi",
    "title": "title",
    "abstract": "abstractText",
    "year": "pubYear",
    "authors": "authorString",
    "journal": "journalTitle",
    "mesh_terms": "meshHeadingList",
    "keywords": "keywordList",
    "citation_count": "citedByCount",
    "is_open_access": "isOpenAccess",
    "in_epmc": "inEPMC",
    "full_text_urls": "fullTextUrlList",
    "license": "license",
}


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
            "full_text",
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
            has_query_controls = (
                request.query_max_results is not None
                or request.query_date_from is not None
                or request.query_date_to is not None
                or request.query_sort_by != "relevance"
                or bool(request.query_filters)
            )
            if has_query_controls:
                pmids = EntrezClient().search_pubmed(
                    request.query,
                    max_results=request.query_max_results,
                    date_from=request.query_date_from,
                    date_to=request.query_date_to,
                    sort_by=request.query_sort_by,
                    filters=list(request.query_filters),
                )
                payload = self.client.fetch_by_pmids(
                    tuple(pmids),
                    max_pages=self.max_search_pages,
                    page_size=self.page_size,
                )
            else:
                payload = self.client.search(
                    request.query,
                    max_pages=self.max_search_pages,
                    page_size=self.page_size,
                )
        else:
            return []

        results = self._extract_results(payload)
        documents = [self._build_document(result) for result in results]

        effective_fields = request.fields_for(self.name)
        if effective_fields is not None and "full_text" in effective_fields:
            self._enrich_full_text_xml(documents)

        if effective_fields is not None:
            documents = [self._apply_field_filter(d, effective_fields) for d in documents]

        return documents

    def _enrich_full_text_xml(self, documents: list[Document]) -> None:
        """Set :attr:`Document.full_text` from Europe PMC ``fullTextXML`` when a PMCID exists."""

        for document in documents:
            pmcid = _clean_str(document.metadata.get("pmcid"))
            raw_meta = document.metadata.get("epmc_meta")
            raw_dict = raw_meta if isinstance(raw_meta, dict) else None
            if not pmcid and raw_dict is not None:
                pmcid = _clean_str(raw_dict.get("pmcid"))
            if not pmcid:
                # Europe PMC uses inPMC=Y/N; N means no PubMed Central copy -> no fullTextXML.
                in_pmc = raw_dict.get("inPMC") if raw_dict is not None else None
                if str(in_pmc).strip().upper() in {"N", "FALSE", "0", "NO"}:
                    document.metadata["epmc_full_text_status"] = "not_in_pubmed_central"
                else:
                    document.metadata["epmc_full_text_status"] = "no_pmcid_in_record"
                continue
            try:
                xml = self.client.fetch_full_text_xml(pmcid)
            except ValueError as exc:
                document.metadata["epmc_full_text_status"] = f"xml_fetch_failed:{exc}"
                logger.debug("Europe PMC fullTextXML failed for %s: %s", pmcid, exc)
                continue
            plain = _jats_xml_to_plain(xml)
            if plain:
                document.full_text = plain
                document.metadata["epmc_full_text_status"] = "ok"
                document.metadata["epmc_full_text_xml_chars"] = len(xml)
            else:
                document.metadata["epmc_full_text_status"] = "empty_after_parse"

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
        """Respect logical ``fields``: trim document body and metadata to match."""

        prev = document.metadata
        raw = prev.get("epmc_meta")
        raw_dict = raw if isinstance(raw, dict) else {}

        if "title" not in fields:
            document.title = ""
        if "abstract" not in fields:
            document.abstract = ""
        if "year" not in fields:
            document.year = None
        if "full_text" not in fields:
            document.full_text = None

        new_meta: dict[str, Any] = {}
        slim: dict[str, Any] = {}
        for logical, api_key in _EPMC_RESULT_KEY_BY_LOGICAL.items():
            if logical not in fields or api_key not in raw_dict:
                continue
            # Title / abstract / year live on Document; avoid duplicating them in epmc_meta.
            if logical in {"title", "abstract", "year"}:
                continue
            slim[api_key] = raw_dict[api_key]

        if slim:
            new_meta["epmc_meta"] = slim
            eid = _clean_str(raw_dict.get("id"))
            src = _clean_str(raw_dict.get("source"))
            if eid:
                new_meta["epmc_id"] = eid
            if src:
                new_meta["epmc_source"] = src

        if "pmcid" in fields:
            v = prev.get("pmcid")
            if v:
                new_meta["pmcid"] = v
        if "doi" in fields:
            v = prev.get("doi")
            if v:
                new_meta["doi"] = v
        if "citation_count" in fields and "citation_count" in prev:
            new_meta["citation_count"] = prev["citation_count"]
        if "is_open_access" in fields and "is_open_access" in prev:
            new_meta["is_open_access"] = prev["is_open_access"]
        if "in_epmc" in fields and "in_epmc" in prev:
            new_meta["in_epmc"] = prev["in_epmc"]
        if "license" in fields and "license" in prev:
            new_meta["license"] = prev["license"]
        if "full_text_urls" in fields and prev.get("full_text_urls"):
            new_meta["full_text_urls"] = prev["full_text_urls"]

        if "full_text" in fields:
            for key in ("epmc_full_text_status", "epmc_full_text_xml_chars"):
                if key in prev:
                    new_meta[key] = prev[key]
            if document.full_text:
                new_meta["epmc_full_text_chars"] = len(document.full_text)

        document.metadata = new_meta
        return document


# A. JATS XML to plain text

def _jats_xml_to_plain(xml: str) -> str:
    """Extract narrative text (paragraphs and section titles) from Europe PMC JATS XML."""

    cleaned = (xml or "").strip()
    if not cleaned:
        return ""
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError:
        return ""
    body = _first_by_local_name(root, "body")
    if body is None:
        return ""
    blocks: list[str] = []
    for node in body.iter():
        name = _local_name(node.tag)
        if name in {"ref-list", "ack", "app", "table-wrap", "fig", "disp-formula"}:
            continue
        if name in {"title", "p"}:
            text = _normalize_ws(" ".join(node.itertext()))
            if text:
                blocks.append(text)
    if not blocks:
        return ""
    deduped: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        if block in seen:
            continue
        seen.add(block)
        deduped.append(block)
    return "\n\n".join(deduped)


def _normalize_ws(value: str) -> str:
    return " ".join((value or "").split())


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _first_by_local_name(root: ET.Element, name: str) -> ET.Element | None:
    for node in root.iter():
        if _local_name(node.tag) == name:
            return node
    return None


# B. Internal helpers

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

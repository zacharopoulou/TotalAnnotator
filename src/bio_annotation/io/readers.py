from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from urllib.parse import urlencode
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any


_EFETCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    "?db=pubmed&retmode=xml&id={pmid}"
)
_ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
_CROSSREF_URL = "https://api.crossref.org/works/{doi}"
_EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_EUROPE_PMC_REFERENCES_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/MED/{pmid}/references"
_EUROPE_PMC_CITATIONS_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/MED/{pmid}/citations"
_SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/PMID:{pmid}"
_SEMANTIC_SCHOLAR_REFERENCES_URL = "https://api.semanticscholar.org/graph/v1/paper/PMID:{pmid}/references"
_SEMANTIC_SCHOLAR_CITATIONS_URL = "https://api.semanticscholar.org/graph/v1/paper/PMID:{pmid}/citations"
_UNPAYWALL_URL = "https://api.unpaywall.org/v2/{doi}"
_BIORXIV_URL = "https://api.biorxiv.org/details/{server}/{doi}/na/json"
_SEMANTIC_SCHOLAR_FIELDS = ",".join(
    [
        "title",
        "year",
        "authors",
        "venue",
        "externalIds",
        "citationCount",
        "referenceCount",
        "openAccessPdf",
        "fieldsOfStudy",
        "s2FieldsOfStudy",
        "publicationTypes",
        "publicationDate",
        "journal",
        "tldr",
    ]
)
_SEMANTIC_SCHOLAR_LINK_FIELDS = "title,year,authors,externalIds,citationCount,venue"


def fetch_pubmed_record(pmid: str, *, timeout: int = 15) -> dict[str, Any]:
    """Fetch a richer PubMed record for one PMID."""

    url = _EFETCH_URL.format(pmid=_normalize_pmid(pmid))
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            xml_text = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise ValueError(f"Network error fetching PMID {pmid}: {exc}") from exc

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"Could not parse XML for PMID {pmid}: {exc}") from exc

    article = root.find(".//PubmedArticle")
    if article is None:
        raise ValueError(f"PMID {pmid} not found in PubMed response.")

    medline = article.find("MedlineCitation")
    pubmed_data = article.find("PubmedData")
    if medline is None:
        raise ValueError(f"PMID {pmid} is missing MedlineCitation data.")

    parsed = _parse_medline_article(medline, pubmed_data)
    parsed["pmid"] = _normalize_pmid(pmid)
    parsed["elinks"] = _build_enrichment_bundle(parsed, timeout=timeout)

    return parsed


def _parse_medline_article(medline: ET.Element, pubmed_data: ET.Element | None) -> dict[str, Any]:
    article = medline.find("Article")
    journal = article.find("Journal") if article is not None else None
    journal_issue = journal.find("JournalIssue") if journal is not None else None
    abstract_sections = _extract_abstract_sections(article)
    pub_date = journal_issue.find("PubDate") if journal_issue is not None else None
    year = _extract_year(pub_date)
    pubmed_ids = _extract_pubmed_ids(pubmed_data)

    authors = _extract_authors(article)
    affiliations = _unique_values(
        aff
        for author in authors
        for aff in author.get("affiliations", [])
    )

    history = _extract_history_dates(pubmed_data)
    medline_info = medline.find("MedlineJournalInfo")
    journal_issn = journal.find("ISSN") if journal is not None else None

    record = {
        "pmid": "",
        "pmcid": pubmed_ids.get("pmcid"),
        "doi": pubmed_ids.get("doi"),
        "pii": pubmed_ids.get("pii"),
        "issn": _node_text(journal_issn) or _node_text(medline.find("./MedlineJournalInfo/ISSNLinking")),
        "issn_type": journal_issn.get("IssnType", "") if journal_issn is not None else "",
        "nlm_unique_id": _node_text(medline.find("./MedlineJournalInfo/NlmUniqueID")),
        "title": _node_text(article.find("ArticleTitle")) if article is not None else "",
        "abstract": " ".join(
            f'{section["label"]}: {section["text"]}' if section["label"] else section["text"]
            for section in abstract_sections
            if section["text"]
        ).strip(),
        "structured_abstract": abstract_sections,
        "year": year,
        "journal": _node_text(journal.find("Title")) if journal is not None else "",
        "journal_abbrev": (
            _node_text(journal.find("ISOAbbreviation")) if journal is not None else ""
        ) or _node_text(medline.find("./MedlineJournalInfo/MedlineTA")),
        "volume": _node_text(journal_issue.find("Volume")) if journal_issue is not None else "",
        "issue": _node_text(journal_issue.find("Issue")) if journal_issue is not None else "",
        "pages": _node_text(article.find("./Pagination/MedlinePgn")) if article is not None else "",
        "language": _extract_text_list(article, "Language"),
        "publication_type": _extract_text_list(article.find("PublicationTypeList") if article is not None else None, "PublicationType"),
        "country": _node_text(medline.find("./MedlineJournalInfo/Country")),
        "pub_date": _extract_pub_date_text(pub_date),
        "epub_date": _extract_epub_date(article),
        "received_date": history.get("received"),
        "accepted_date": history.get("accepted"),
        "medline_date": history.get("medline"),
        "entrez_date": history.get("entrez"),
        "revision_date": _extract_simple_date(medline.find("DateRevised")),
        "authors": authors,
        "affiliations": affiliations,
        "keywords": _extract_text_list(medline.find("KeywordList"), "Keyword"),
        "mesh_terms": _extract_mesh_terms(medline.find("MeshHeadingList")),
        "chemicals": _extract_chemicals(medline.find("ChemicalList")),
        "gene_symbols": _extract_text_list(medline.find("GeneSymbolList"), "GeneSymbol"),
        "supplemental_mesh": _extract_supplemental_mesh(medline.find("SupplMeshList")),
        "grants": _extract_grants(article.find("GrantList") if article is not None else None),
        "citation_status": medline.get("Status", ""),
        "owner": medline.get("Owner", ""),
        "version": _extract_version(medline.find("PMID")),
        "comments_corrections": _extract_comments_corrections(pubmed_data.find("CommentsCorrectionsList") if pubmed_data is not None else None),
        "data_banks": _extract_data_banks(article.find("DataBankList") if article is not None else None),
        "elinks": {},
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    return record


def _node_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def _normalize_pmid(pmid: str) -> str:
    text = str(pmid).strip()
    if text.upper().startswith("PMID:"):
        text = text.split(":", 1)[1].strip()
    if not text:
        raise ValueError("PMID must not be empty.")
    return text


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _extract_pmcid(article: ET.Element) -> str | None:
    for article_id in article.findall(".//ArticleId"):
        id_type = (article_id.get("IdType") or article_id.get("idtype") or "").strip().lower()
        if id_type == "pmc":
            value = _node_text(article_id)
            if not value:
                continue
            return value if value.upper().startswith("PMC") else f"PMC{value}"
    return None


def _extract_pubmed_ids(pubmed_data: ET.Element | None) -> dict[str, str | None]:
    values: dict[str, str | None] = {"pmcid": None, "doi": None, "pii": None}
    if pubmed_data is None:
        return values
    for article_id in pubmed_data.findall(".//ArticleId"):
        id_type = (article_id.get("IdType") or article_id.get("idtype") or "").strip().lower()
        value = _node_text(article_id)
        if not value:
            continue
        if id_type == "pmc":
            values["pmcid"] = value if value.upper().startswith("PMC") else f"PMC{value}"
        elif id_type == "doi":
            values["doi"] = value
        elif id_type == "pii":
            values["pii"] = value
    return values


def _extract_abstract_sections(article: ET.Element | None) -> list[dict[str, str]]:
    if article is None:
        return []
    sections: list[dict[str, str]] = []
    for node in article.findall(".//AbstractText"):
        text = _node_text(node)
        if not text:
            continue
        label = (node.get("Label") or "").strip()
        nlm_category = (node.get("NlmCategory") or "").strip()
        sections.append({"label": label, "nlm_category": nlm_category, "text": text})
    return sections


def _extract_text_list(parent: ET.Element | None, tag: str) -> list[str]:
    if parent is None:
        return []
    values = [_node_text(node) for node in parent.findall(tag)]
    return [value for value in values if value]


def _extract_authors(article: ET.Element | None) -> list[dict[str, Any]]:
    if article is None:
        return []
    authors: list[dict[str, Any]] = []
    author_list = article.find("AuthorList")
    if author_list is None:
        return authors
    for author in author_list.findall("Author"):
        affiliations = [
            _node_text(affiliation.find("Affiliation"))
            for affiliation in author.findall("AffiliationInfo")
            if _node_text(affiliation.find("Affiliation"))
        ]
        orcid = ""
        for identifier in author.findall("Identifier"):
            source = (identifier.get("Source") or "").strip().upper()
            if source == "ORCID":
                orcid = _node_text(identifier).removeprefix("https://orcid.org/").strip()
                break
        authors.append(
            {
                "last": _node_text(author.find("LastName")),
                "first": _node_text(author.find("ForeName")),
                "initials": _node_text(author.find("Initials")),
                "orcid": orcid,
                "collective_name": _node_text(author.find("CollectiveName")),
                "affiliations": affiliations,
            }
        )
    return authors


def _extract_mesh_terms(mesh_list: ET.Element | None) -> list[dict[str, Any]]:
    if mesh_list is None:
        return []
    mesh_terms: list[dict[str, Any]] = []
    for heading in mesh_list.findall("MeshHeading"):
        descriptor = heading.find("DescriptorName")
        if descriptor is None:
            continue
        mesh_terms.append(
            {
                "descriptor": _node_text(descriptor),
                "descriptor_ui": descriptor.get("UI", ""),
                "major_topic": descriptor.get("MajorTopicYN", "N") == "Y",
                "qualifiers": [
                    {
                        "name": _node_text(qualifier),
                        "ui": qualifier.get("UI", ""),
                        "major_topic": qualifier.get("MajorTopicYN", "N") == "Y",
                    }
                    for qualifier in heading.findall("QualifierName")
                    if _node_text(qualifier)
                ],
            }
        )
    return mesh_terms


def _extract_grants(grant_list: ET.Element | None) -> list[dict[str, str]]:
    if grant_list is None:
        return []
    grants: list[dict[str, str]] = []
    for grant in grant_list.findall("Grant"):
        grants.append(
            {
                "grant_id": _node_text(grant.find("GrantID")),
                "acronym": _node_text(grant.find("Acronym")),
                "agency": _node_text(grant.find("Agency")),
                "country": _node_text(grant.find("Country")),
            }
        )
    return grants


def _extract_history_dates(pubmed_data: ET.Element | None) -> dict[str, str | None]:
    values: dict[str, str | None] = {"received": None, "accepted": None, "entrez": None, "medline": None}
    if pubmed_data is None:
        return values
    history = pubmed_data.find("History")
    if history is None:
        return values
    for pubmed_date in history.findall("PubMedPubDate"):
        status = (pubmed_date.get("PubStatus") or "").strip().lower()
        value = _extract_simple_date(pubmed_date)
        if status in values:
            values[status] = value
        elif status == "medlinerec":
            values["medline"] = value
    return values


def _extract_simple_date(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    year = _node_text(node.find("Year"))
    if not year:
        return None
    month = _node_text(node.find("Month")) or "01"
    day = _node_text(node.find("Day")) or "01"
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def _extract_pub_date_text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    medline_date = _node_text(node.find("MedlineDate"))
    if medline_date:
        return medline_date
    return _extract_simple_date(node)


def _extract_year(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    year = _node_text(node.find("Year"))
    if year:
        return year
    medline_date = _node_text(node.find("MedlineDate"))
    return medline_date or None


def _extract_epub_date(article: ET.Element | None) -> str | None:
    if article is None:
        return None
    for article_date in article.findall("ArticleDate"):
        if (article_date.get("DateType") or "").strip().lower() == "electronic":
            return _extract_simple_date(article_date)
    return None


def _extract_chemicals(chemical_list: ET.Element | None) -> list[dict[str, str]]:
    if chemical_list is None:
        return []
    chemicals: list[dict[str, str]] = []
    for chemical in chemical_list.findall("Chemical"):
        substance = chemical.find("NameOfSubstance")
        chemicals.append(
            {
                "registry_number": _node_text(chemical.find("RegistryNumber")),
                "name": _node_text(substance),
                "ui": substance.get("UI", "") if substance is not None else "",
            }
        )
    return chemicals


def _extract_supplemental_mesh(supplemental_list: ET.Element | None) -> list[dict[str, str]]:
    if supplemental_list is None:
        return []
    values: list[dict[str, str]] = []
    for entry in supplemental_list.findall("SupplMeshName"):
        values.append(
            {
                "name": _node_text(entry),
                "type": entry.get("Type", ""),
                "ui": entry.get("UI", ""),
            }
        )
    return values


def _extract_comments_corrections(comments_list: ET.Element | None) -> list[dict[str, str]]:
    if comments_list is None:
        return []
    values: list[dict[str, str]] = []
    for comment in comments_list.findall("CommentsCorrections"):
        values.append(
            {
                "ref_type": comment.get("RefType", ""),
                "ref_source": _node_text(comment.find("RefSource")),
                "pmid": _node_text(comment.find("PMID")),
            }
        )
    return values


def _extract_data_banks(data_bank_list: ET.Element | None) -> list[dict[str, Any]]:
    if data_bank_list is None:
        return []
    values: list[dict[str, Any]] = []
    for data_bank in data_bank_list.findall("DataBank"):
        values.append(
            {
                "name": _node_text(data_bank.find("DataBankName")),
                "accession_numbers": _extract_text_list(data_bank, "AccessionNumber"),
            }
        )
    return values


def _extract_version(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return (node.get("Version") or "").strip()


def _build_enrichment_bundle(record: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    bundle = _fetch_elinks(record.get("pmid"), timeout=timeout)
    _merge_dict(bundle, _fetch_crossref(record.get("doi"), timeout=timeout))
    _merge_dict(bundle, _fetch_europe_pmc(record.get("pmid"), timeout=timeout))
    _merge_dict(bundle, _fetch_semantic_scholar(record.get("pmid"), timeout=timeout))
    _merge_dict(bundle, _fetch_unpaywall(record.get("doi"), timeout=timeout))
    _merge_dict(bundle, _fetch_biorxiv(record.get("doi"), timeout=timeout))
    return bundle


def _fetch_elinks(pmid: Any, *, timeout: int) -> dict[str, Any]:
    normalized_pmid = _clean_optional_text(str(pmid) if pmid is not None else None)
    if normalized_pmid is None:
        return {}
    try:
        payload = _fetch_json(
            _ELINK_URL,
            params={
                "dbfrom": "pubmed",
                "db": "pubmed",
                "id": normalized_pmid,
                "cmd": "neighbor_score",
                "retmode": "json",
            },
            timeout=timeout,
        )
    except ValueError:
        return {}

    related_pmids: list[dict[str, Any]] = []
    cited_by_pmids: list[str] = []
    references_pmids: list[str] = []

    for linkset in payload.get("linksets", []):
        src_ids = linkset.get("ids", [])
        if not src_ids or str(src_ids[0]) != normalized_pmid:
            continue
        for linksetdb in linkset.get("linksetdbs", []):
            linkname = str(linksetdb.get("linkname") or "")
            links = linksetdb.get("links", [])
            if linkname == "pubmed_pubmed":
                related_pmids = [
                    {
                        "pmid": str(link.get("id", link) if isinstance(link, dict) else link),
                        "score": int(link.get("score", 0)) if isinstance(link, dict) else 0,
                    }
                    for link in links
                ]
            elif linkname == "pubmed_pubmed_citedin":
                cited_by_pmids = [str(link.get("id", link) if isinstance(link, dict) else link) for link in links]
            elif linkname == "pubmed_pubmed_refs":
                references_pmids = [str(link.get("id", link) if isinstance(link, dict) else link) for link in links]

    return {
        "related_pmids": related_pmids,
        "cited_by_pmids": cited_by_pmids,
        "references_pmids": references_pmids,
    }


def _fetch_crossref(doi: Any, *, timeout: int) -> dict[str, Any]:
    normalized_doi = _clean_optional_text(str(doi) if doi is not None else None)
    if normalized_doi is None:
        return {}
    try:
        payload = _fetch_json(_CROSSREF_URL.format(doi=normalized_doi), timeout=timeout)
    except ValueError:
        return {}
    message = payload.get("message")
    if not isinstance(message, dict):
        return {}
    return {
        "crossref_meta": message,
        "crossref_references": message.get("reference", []),
    }


def _fetch_europe_pmc(pmid: Any, *, timeout: int) -> dict[str, Any]:
    normalized_pmid = _clean_optional_text(str(pmid) if pmid is not None else None)
    if normalized_pmid is None:
        return {}
    try:
        meta_payload = _fetch_json(
            _EUROPE_PMC_SEARCH_URL,
            params={
                "query": f"EXT_ID:{normalized_pmid} AND SRC:MED",
                "format": "json",
                "resulttype": "core",
            },
            timeout=timeout,
        )
        references_payload = _fetch_json(
            _EUROPE_PMC_REFERENCES_URL.format(pmid=normalized_pmid),
            params={"format": "json"},
            timeout=timeout,
        )
        citations_payload = _fetch_json(
            _EUROPE_PMC_CITATIONS_URL.format(pmid=normalized_pmid),
            params={"format": "json"},
            timeout=timeout,
        )
    except ValueError:
        return {}

    meta_results = meta_payload.get("resultList", {}).get("result", [])
    meta = meta_results[0] if meta_results else None
    return {
        "epmc_meta": meta or {},
        "epmc_references": references_payload.get("referenceList", {}).get("reference", []),
        "epmc_citations": citations_payload.get("citationList", {}).get("citation", []),
    }


def _fetch_semantic_scholar(pmid: Any, *, timeout: int) -> dict[str, Any]:
    normalized_pmid = _clean_optional_text(str(pmid) if pmid is not None else None)
    if normalized_pmid is None:
        return {}
    try:
        paper = _fetch_json(
            _SEMANTIC_SCHOLAR_URL.format(pmid=normalized_pmid),
            params={"fields": _SEMANTIC_SCHOLAR_FIELDS},
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        references = _fetch_json(
            _SEMANTIC_SCHOLAR_REFERENCES_URL.format(pmid=normalized_pmid),
            params={"fields": _SEMANTIC_SCHOLAR_LINK_FIELDS, "limit": 100},
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        citations = _fetch_json(
            _SEMANTIC_SCHOLAR_CITATIONS_URL.format(pmid=normalized_pmid),
            params={"fields": _SEMANTIC_SCHOLAR_LINK_FIELDS, "limit": 100},
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
    except ValueError:
        return {}

    return {
        "s2_paper": paper,
        "s2_references": [item.get("citedPaper", {}) for item in references.get("data", [])],
        "s2_citations": [item.get("citingPaper", {}) for item in citations.get("data", [])],
    }


def _fetch_unpaywall(doi: Any, *, timeout: int) -> dict[str, Any]:
    normalized_doi = _clean_optional_text(str(doi) if doi is not None else None)
    contact_email = _clean_optional_text(os.getenv("NCBI_EMAIL"))
    if normalized_doi is None or contact_email is None:
        return {}
    try:
        payload = _fetch_json(
            _UNPAYWALL_URL.format(doi=normalized_doi),
            params={"email": contact_email},
            timeout=timeout,
        )
    except ValueError:
        return {}

    best_location = payload.get("best_oa_location") or {}
    return {
        "unpaywall": {
            "is_oa": payload.get("is_oa", False),
            "oa_status": payload.get("oa_status", ""),
            "pdf_url": best_location.get("url_for_pdf"),
            "license": best_location.get("license"),
        }
    }


def _fetch_biorxiv(doi: Any, *, timeout: int) -> dict[str, Any]:
    normalized_doi = _clean_optional_text(str(doi) if doi is not None else None)
    if normalized_doi is None or not normalized_doi.startswith("10.1101/"):
        return {}

    for server in ("biorxiv", "medrxiv"):
        try:
            payload = _fetch_json(_BIORXIV_URL.format(server=server, doi=normalized_doi), timeout=timeout)
        except ValueError:
            continue
        collection = payload.get("collection", [])
        if not collection:
            continue
        latest = collection[-1]
        return {
            "biorxiv": {
                "doi": latest.get("doi", ""),
                "title": latest.get("title", ""),
                "authors": latest.get("authors", ""),
                "date": latest.get("date", ""),
                "category": latest.get("category", ""),
                "abstract": latest.get("abstract", ""),
                "published": latest.get("published", "NA"),
                "version": latest.get("version", ""),
                "license": latest.get("license", ""),
                "jatsxml": latest.get("jatsxml", ""),
                "server": latest.get("server", server),
            }
        }
    return {}


def _fetch_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_url = _build_url(url, params)
    request = urllib.request.Request(request_url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise ValueError(f"Network error fetching {request_url}: {exc}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse JSON from {request_url}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object from {request_url}.")
    return data


def _build_url(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    cleaned = {
        key: value
        for key, value in params.items()
        if value is not None and value != ""
    }
    if not cleaned:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(cleaned)}"


def _merge_dict(target: dict[str, Any], extra: dict[str, Any]) -> None:
    for key, value in extra.items():
        target[key] = value


def _unique_values(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out

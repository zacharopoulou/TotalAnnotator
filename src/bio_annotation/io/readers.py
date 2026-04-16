from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any


_EFETCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    "?db=pubmed&retmode=xml&id={pmid}"
)


def fetch_pubmed_record(pmid: str, *, timeout: int = 15) -> dict[str, Any]:
    """Fetch a minimal PubMed record for one PMID."""

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

    title = _node_text(article.find(".//ArticleTitle"))
    abstract_parts: list[str] = []
    for node in article.findall(".//AbstractText"):
        text = _node_text(node)
        if not text:
            continue
        label = (node.get("Label") or "").strip()
        abstract_parts.append(f"{label}: {text}" if label else text)

    pub_date = article.find(".//PubDate")
    year: str | None = None
    if pub_date is not None:
        year = _clean_optional_text(pub_date.findtext("Year")) or _clean_optional_text(pub_date.findtext("MedlineDate"))

    return {
        "pmid": _normalize_pmid(pmid),
        "title": title,
        "abstract": " ".join(abstract_parts).strip(),
        "year": year,
    }


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

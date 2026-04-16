from __future__ import annotations

import json
from pathlib import Path
from urllib import error, parse, request


_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


def search_pubmed_pmids(
    query: str,
    *,
    max_results: int = 100,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "relevance",
    filters: list[str] | None = None,
    timeout: int = 30,
) -> list[str]:
    term = _build_query(query, date_from=date_from, date_to=date_to, filters=filters)
    params = parse.urlencode(
        {
            "db": "pubmed",
            "term": term,
            "retmax": min(max_results, 10_000),
            "retmode": "json",
            "sort": sort_by,
        }
    )
    target = f"{_ESEARCH_URL}?{params}"
    http_request = request.Request(target, headers={"Accept": "application/json"}, method="GET")

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to search PubMed for query {query!r}: {exc}") from exc

    id_list = payload.get("esearchresult", {}).get("idlist", [])
    if not isinstance(id_list, list):
        return []
    return [str(value).strip() for value in id_list if str(value).strip()]


def write_pmids(path: Path, pmids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{pmid}\n" for pmid in pmids), encoding="utf-8")


def _build_query(
    query: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    filters: list[str] | None = None,
) -> str:
    built = query.strip()
    if not built:
        raise ValueError("Query must not be empty.")
    if date_from and date_to:
        built += f' AND ("{date_from}"[Date - Publication] : "{date_to}"[Date - Publication])'
    elif date_from:
        built += f' AND ("{date_from}"[Date - Publication] : "3000"[Date - Publication])'
    for clause in filters or []:
        cleaned = clause.strip()
        if cleaned:
            built += f" AND {cleaned}"
    return built

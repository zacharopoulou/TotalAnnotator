from __future__ import annotations

import calendar
import json
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib import error, parse, request


_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_CAP = 10_000
_MIN_INTERVAL = 0.34  # 3 req/sec NCBI limit (unauthenticated)

_last_request = 0.0


def _esearch(term: str, *, sort_by: str = "relevance", timeout: int = 30) -> dict[str, Any]:
    global _last_request
    wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    params = parse.urlencode(
        {"db": "pubmed", "term": term, "retmax": _CAP, "retmode": "json", "sort": sort_by}
    )
    req = request.Request(f"{_ESEARCH_URL}?{params}", headers={"Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, json.JSONDecodeError) as exc:
        raise ValueError(f"PubMed search failed for {term!r}: {exc}") from exc
    _last_request = time.monotonic()
    result = payload.get("esearchresult") or {}
    pmids = [str(x).strip() for x in result.get("idlist") or [] if str(x).strip()]
    return {"count": int(result.get("count") or len(pmids)), "pmids": pmids}


def search_pubmed_pmids(
    query: str,
    *,
    max_results: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "relevance",
    filters: list[str] | None = None,
    timeout: int = 30,
    esearch_fn: Callable[[str], dict[str, Any]] | None = None,
) -> list[str]:
    term = query.strip()
    if not term:
        raise ValueError("Query must not be empty.")
    for clause in filters or []:
        if clause.strip():
            term += f" AND {clause.strip()}"
    fn = esearch_fn or (lambda t: _esearch(t, sort_by=sort_by, timeout=timeout))

    lo = _parse_date(date_from, upper=False) if date_from else date(1950, 1, 1)
    hi = _parse_date(date_to, upper=True) if date_to else date(2100, 12, 31)

    pmids: dict[str, None] = {}
    stack = [(lo, hi)]
    while stack:
        start, end = stack.pop()
        window = f'{term} AND ("{start:%Y/%m/%d}"[Date - Publication] : "{end:%Y/%m/%d}"[Date - Publication])'
        result = fn(window)
        if result["count"] <= _CAP:
            for pmid in result["pmids"]:
                pmids.setdefault(pmid, None)
            continue
        if start == end: # window has 1-day size and still more than 10000 results
            raise ValueError(f"Window {start:%Y/%m/%d} has {result['count']} results, exceeds {_CAP} cap.")
        mid = start + (end - start) // 2
        stack.append((start, mid))
        stack.append((mid + timedelta(days=1), end))
    collected = list(pmids)
    return collected[:max_results] if max_results is not None else collected


def write_pmids(path: Path, pmids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{pmid}\n" for pmid in pmids), encoding="utf-8")


def _parse_date(value: str, *, upper: bool) -> date:
    parts = [int(p) for p in value.strip().replace("-", "/").split("/")]
    year = parts[0]
    month = parts[1] if len(parts) > 1 else (12 if upper else 1)
    if len(parts) > 2:
        day = parts[2]
    else:
        day = calendar.monthrange(year, month)[1] if upper else 1
    return date(year, month, day)

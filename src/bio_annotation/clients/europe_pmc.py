from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any, Callable, Iterable
from urllib import error, parse, request


EUROPE_PMC_API_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 1000

RequestOpener = Callable[[request.Request, int], bytes]


def _default_open(http_request: request.Request, timeout: int) -> bytes:
    with request.urlopen(http_request, timeout=timeout) as response:
        return response.read()


def _clean(values: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


@dataclass(slots=True)
class EuropePmcClient:
    base_url: str = EUROPE_PMC_API_BASE_URL
    timeout: int = 60
    opener: RequestOpener = _default_open
    page_size: int = DEFAULT_PAGE_SIZE
    user_agent: str = "TotalAnnotator/0.1 (+https://github.com)"

    def search(
        self,
        query: str,
        *,
        result_type: str = "core",
        max_pages: int = 1,
        page_size: int | None = None,
        synonym: bool = False,
    ) -> dict[str, Any]:
        if not query or not query.strip():
            raise ValueError("Query must not be empty.")
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1.")
        size = self._resolve_page_size(page_size)

        cursor = "*"
        merged: dict[str, Any] | None = None
        merged_results: list[Any] = []

        for _ in range(max_pages):
            page = self._search_page(
                query,
                cursor=cursor,
                result_type=result_type,
                page_size=size,
                synonym=synonym,
            )
            if merged is None:
                merged = dict(page)
            page_results = (
                page.get("resultList", {}).get("result", [])
                if isinstance(page.get("resultList"), dict)
                else []
            )
            merged_results.extend(page_results)
            next_cursor = page.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor or not page_results:
                break
            cursor = next_cursor

        if merged is None:
            return {"resultList": {"result": []}}
        merged.setdefault("resultList", {})["result"] = merged_results
        return merged

    def fetch_by_pmids(
        self,
        pmids: Iterable[str],
        *,
        max_pages: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        cleaned = _clean(pmids)
        if not cleaned:
            return {"resultList": {"result": []}}
        terms = " OR ".join(f"EXT_ID:{pmid}" for pmid in cleaned)
        query = f"({terms}) AND SRC:MED"
        return self.search(
            query,
            max_pages=max_pages,
            page_size=page_size,
        )

    def fetch_by_pmcids(
        self,
        pmcids: Iterable[str],
        *,
        max_pages: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        cleaned = _clean(pmcids)
        if not cleaned:
            return {"resultList": {"result": []}}
        terms = " OR ".join(f"PMCID:{_normalize_pmcid(pmcid)}" for pmcid in cleaned)
        return self.search(
            terms,
            max_pages=max_pages,
            page_size=page_size,
        )

    def fetch_full_text_xml(self, pmcid: str) -> str:
        normalized = _normalize_pmcid(pmcid)
        endpoint = f"{self.base_url.rstrip('/')}/{normalized}/fullTextXML"
        http_request = request.Request(
            endpoint,
            headers={"Accept": "application/xml", "User-Agent": self.user_agent},
            method="GET",
        )
        return self._send_text(http_request)

    def _resolve_page_size(self, page_size: int | None) -> int:
        size = page_size if page_size is not None else self.page_size
        if size < 1:
            raise ValueError("page_size must be >= 1.")
        if size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be <= {MAX_PAGE_SIZE}.")
        return size

    def _search_page(
        self,
        query: str,
        *,
        cursor: str,
        result_type: str,
        page_size: int,
        synonym: bool,
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "query": query,
            "format": "json",
            "resulttype": result_type,
            "cursorMark": cursor,
            "pageSize": str(page_size),
            "synonym": "true" if synonym else "false",
        }
        url = f"{self.base_url.rstrip('/')}/search?{parse.urlencode(params)}"
        http_request = request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": self.user_agent},
            method="GET",
        )
        return self._send_json(http_request)

    def _send_json(self, http_request: request.Request) -> dict[str, Any]:
        try:
            body = self.opener(http_request, self.timeout)
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise ValueError(f"Europe PMC request failed: {exc}") from exc
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Europe PMC returned non-JSON payload: {exc}") from exc

    def _send_text(self, http_request: request.Request) -> str:
        try:
            return self.opener(http_request, self.timeout).decode("utf-8")
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise ValueError(f"Europe PMC request failed: {exc}") from exc


def _normalize_pmcid(value: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError("PMCID must not be empty.")
    upper = cleaned.upper()
    if upper.startswith("PMC:"):
        upper = upper.split(":", 1)[1]
    if not upper.startswith("PMC"):
        upper = f"PMC{upper}"
    digits = upper[3:]
    if not digits.isdigit():
        raise ValueError(f"PMCID {value!r} must be of the form 'PMC<digits>'.")
    return upper


__all__ = [
    "EUROPE_PMC_API_BASE_URL",
    "EuropePmcClient",
    "MAX_PAGE_SIZE",
    "RequestOpener",
]

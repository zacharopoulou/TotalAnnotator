from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable
from urllib import error, parse, request


PUBTATOR3_API_BASE_URL = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"
PUBTATOR_RAW_TEXT_REQUEST_URL = "https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/RESTful/request.cgi"
PUBTATOR_RAW_TEXT_RETRIEVE_URL = "https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/RESTful/retrieve.cgi"
DEFAULT_EXPORT_FORMAT = "biocjson"
DEFAULT_GET_BATCH_SIZE = 100
DEFAULT_POST_BATCH_SIZE = 1000
DEFAULT_BIOCONCEPT = "All"
DEFAULT_TEXT_MAX_ATTEMPTS = 20
DEFAULT_TEXT_POLL_INTERVAL = 2.0
DEFAULT_TEXT_POLL_BACKOFF = 1.5
DEFAULT_TEXT_MAX_POLL_INTERVAL = 15.0

RequestOpener = Callable[[request.Request, int], bytes]


class PubTator3PendingError(ValueError):
    """Raised when a raw-text PubTator3 job is not ready yet."""


def _default_open(http_request: request.Request, timeout: int) -> bytes:
    with request.urlopen(http_request, timeout=timeout) as response:
        return response.read()


def _clean_identifiers(identifiers: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for identifier in identifiers:
        text = str(identifier).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _chunked(values: list[str], size: int) -> list[list[str]]:
    if size < 1:
        raise ValueError("Batch size must be at least 1.")
    return [values[index : index + size] for index in range(0, len(values), size)]


def _merge_biocjson_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    documents: list[Any] = []
    for payload in payloads:
        documents.extend(_extract_bioc_documents(payload))
    return {"documents": documents}


def _extract_bioc_documents(payload: dict[str, Any]) -> list[Any]:
    if "documents" in payload and isinstance(payload["documents"], list):
        return list(payload["documents"])
    if "PubTator3" in payload and isinstance(payload["PubTator3"], list):
        return list(payload["PubTator3"])
    return []


@dataclass(slots=True)
class PubTator3Client:
    base_url: str = PUBTATOR3_API_BASE_URL
    timeout: int = 60
    opener: RequestOpener = _default_open
    get_batch_size: int = DEFAULT_GET_BATCH_SIZE
    post_batch_size: int = DEFAULT_POST_BATCH_SIZE

    def fetch_publications_by_pmids(
        self,
        pmids: Iterable[str],
        *,
        format: str = DEFAULT_EXPORT_FORMAT,
        concepts: Iterable[str] | None = None,
        full: bool = False,
    ) -> Any:
        if full and format == "pubtator":
            raise ValueError("PubTator3 full-text export is only available in biocxml or biocjson formats.")
        return self._fetch_publications(
            "pmids",
            pmids,
            format=format,
            concepts=concepts,
            full=full,
        )

    def fetch_publications_by_pmcids(
        self,
        pmcids: Iterable[str],
        *,
        format: str = DEFAULT_EXPORT_FORMAT,
        concepts: Iterable[str] | None = None,
        full: bool = False,
    ) -> Any:
        if format not in {"biocxml", "biocjson"}:
            raise ValueError("PubTator3 PMCID export only supports biocxml or biocjson formats.")
        return self._fetch_publications(
            "pmcids",
            pmcids,
            format=format,
            concepts=concepts,
            full=full,
            endpoint_path="publications/pmc_export",
        )

    def search_publications(
        self,
        query: str,
        *,
        page: int = 1,
        max_pages: int = 1,
    ) -> dict[str, Any]:
        """Call the PubTator3 ``/search/`` endpoint and return the JSON payload.

        ``page`` is 1-based. PubTator3 returns 10 hits per page; pass
        ``max_pages > 1`` to merge several consecutive pages of ``results``
        into a single dict (other top-level fields are taken from the first
        page response).
        """

        if not query or not query.strip():
            raise ValueError("Query must not be empty.")
        if page < 1:
            raise ValueError("page must be >= 1.")
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1.")

        first = self._search_page(query, page=page)
        if max_pages == 1:
            return first

        merged = dict(first)
        merged_results = list(first.get("results", []))
        for offset in range(1, max_pages):
            extra = self._search_page(query, page=page + offset)
            extra_results = extra.get("results")
            if not isinstance(extra_results, list) or not extra_results:
                break
            merged_results.extend(extra_results)
        merged["results"] = merged_results
        return merged

    def _search_page(self, query: str, *, page: int) -> dict[str, Any]:
        params = {"text": query, "page": str(page)}
        endpoint = f"{self.base_url.rstrip('/')}/search/?{parse.urlencode(params)}"
        http_request = request.Request(endpoint, method="GET")
        return self._send_json(http_request)

    def submit_text_annotation(
        self,
        payload: bytes | str,
        *,
        bioconcept: str = DEFAULT_BIOCONCEPT,
    ) -> str:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        body = parse.urlencode({"text": text, "bioconcept": bioconcept}).encode("utf-8")
        http_request = request.Request(
            PUBTATOR_RAW_TEXT_REQUEST_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        response_body = self._send_json(http_request)
        session_id = str(response_body.get("id") or "").strip()
        if not session_id:
            raise ValueError("PubTator3 submit endpoint returned an empty session ID.")
        return session_id

    def retrieve_text_annotation(self, session_id: str) -> str:
        endpoint = f"{PUBTATOR_RAW_TEXT_RETRIEVE_URL}?{parse.urlencode({'id': session_id.strip()})}"
        http_request = request.Request(endpoint, method="GET")
        try:
            return self._send_text(http_request)
        except ValueError as exc:
            if "HTTP Error 404" in str(exc) or "HTTP Error 400" in str(exc):
                raise PubTator3PendingError("PubTator3 annotation job is not ready yet.") from exc
            raise

    def annotate_text(
        self,
        payload: bytes | str,
        *,
        bioconcept: str = DEFAULT_BIOCONCEPT,
        max_attempts: int = DEFAULT_TEXT_MAX_ATTEMPTS,
        poll_interval: float = DEFAULT_TEXT_POLL_INTERVAL,
        poll_backoff: float = DEFAULT_TEXT_POLL_BACKOFF,
        max_poll_interval: float = DEFAULT_TEXT_MAX_POLL_INTERVAL,
    ) -> str:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if poll_interval < 0:
            raise ValueError("poll_interval must be non-negative.")
        if poll_backoff < 1.0:
            raise ValueError("poll_backoff must be at least 1.0.")
        if max_poll_interval <= 0:
            raise ValueError("max_poll_interval must be greater than 0.")

        session_id = self.submit_text_annotation(payload, bioconcept=bioconcept)
        last_error: PubTator3PendingError | None = None
        delay = poll_interval
        for attempt in range(max_attempts):
            try:
                return self.retrieve_text_annotation(session_id)
            except PubTator3PendingError as exc:
                last_error = exc
                if attempt == max_attempts - 1:
                    break
                time.sleep(delay)
                delay = min(delay * poll_backoff, max_poll_interval)

        raise ValueError(
            f"PubTator3 annotation job {session_id} was not ready after {max_attempts} attempts."
        ) from last_error

    def _fetch_publications(
        self,
        identifier_type: str,
        identifiers: Iterable[str],
        *,
        format: str,
        concepts: Iterable[str] | None,
        full: bool = False,
        endpoint_path: str = "publications/export",
    ) -> Any:
        cleaned_identifiers = _clean_identifiers(identifiers)
        if not cleaned_identifiers:
            return {"documents": []} if format == "biocjson" else ""

        cleaned_concepts = _clean_identifiers(concepts or [])
        if format == "biocjson" and cleaned_concepts:
            raise ValueError("PubTator3 concepts filtering is not supported with biocjson export.")

        if len(cleaned_identifiers) <= self.get_batch_size:
            payloads = [
                self._fetch_export_batch(
                    identifier_type,
                    cleaned_identifiers,
                    format=format,
                    concepts=cleaned_concepts,
                    full=full,
                    endpoint_path=endpoint_path,
                )
            ]
        else:
            payloads = [
                self._fetch_export_batch(
                    identifier_type,
                    batch,
                    format=format,
                    concepts=cleaned_concepts,
                    full=full,
                    endpoint_path=endpoint_path,
                )
                for batch in _chunked(cleaned_identifiers, self.post_batch_size)
            ]

        if format == "biocjson":
            return _merge_biocjson_payloads(payloads)
        return "\n".join(str(payload).strip() for payload in payloads if str(payload).strip())

    def _fetch_export_batch(
        self,
        identifier_type: str,
        identifiers: list[str],
        *,
        format: str,
        concepts: list[str],
        full: bool = False,
        endpoint_path: str = "publications/export",
    ) -> Any:
        endpoint = f"{self.base_url.rstrip('/')}/{endpoint_path}/{format}"
        params: dict[str, str] = {identifier_type: ",".join(identifiers)}
        if concepts:
            params["concepts"] = ",".join(concepts)
        if full:
            params["full"] = "true"

        if len(identifiers) <= self.get_batch_size:
            url = f"{endpoint}?{parse.urlencode(params)}"
            http_request = request.Request(url, method="GET")
        else:
            body = parse.urlencode(params).encode("utf-8")
            http_request = request.Request(
                endpoint,
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )

        if format == "biocjson":
            return self._send_json(http_request)
        return self._send_text(http_request)

    def _send_json(self, http_request: request.Request) -> dict[str, Any]:
        try:
            return json.loads(self.opener(http_request, self.timeout).decode("utf-8"))
        except (error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError) as exc:
            raise ValueError(f"PubTator3 request failed: {exc}") from exc

    def _send_text(self, http_request: request.Request) -> str:
        try:
            return self.opener(http_request, self.timeout).decode("utf-8")
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise ValueError(f"PubTator3 request failed: {exc}") from exc

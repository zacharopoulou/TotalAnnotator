from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable
from urllib import error, parse, request


PUBTATOR3_API_BASE_URL = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"
DEFAULT_EXPORT_FORMAT = "biocjson"
DEFAULT_GET_BATCH_SIZE = 100
DEFAULT_POST_BATCH_SIZE = 1000
DEFAULT_BIOCONCEPT = "BioConcept"

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


def _raw_text_base_url(base_url: str) -> str:
    return base_url.rstrip("/").replace("/pubtator3-api", "/pubtator-api")


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
    ) -> Any:
        return self._fetch_publications("pmids", pmids, format=format, concepts=concepts)

    def fetch_publications_by_pmcids(
        self,
        pmcids: Iterable[str],
        *,
        format: str = DEFAULT_EXPORT_FORMAT,
        concepts: Iterable[str] | None = None,
    ) -> Any:
        if format not in {"biocxml", "biocjson"}:
            raise ValueError("PubTator3 PMCID export only supports biocxml or biocjson formats.")
        return self._fetch_publications("pmcids", pmcids, format=format, concepts=concepts)

    def submit_text_annotation(
        self,
        payload: bytes | str,
        *,
        bioconcept: str = DEFAULT_BIOCONCEPT,
    ) -> str:
        body = payload.encode("utf-8") if isinstance(payload, str) else payload
        endpoint = f"{_raw_text_base_url(self.base_url)}/annotations/annotate/submit/{bioconcept}"
        http_request = request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        response_body = self._send_text(http_request)
        session_id = response_body.strip()
        if not session_id:
            raise ValueError("PubTator3 submit endpoint returned an empty session ID.")
        return session_id

    def retrieve_text_annotation(self, session_id: str) -> str:
        endpoint = f"{_raw_text_base_url(self.base_url)}/annotations/annotate/retrieve/{session_id.strip()}"
        http_request = request.Request(endpoint, method="GET")
        try:
            return self._send_text(http_request)
        except ValueError as exc:
            if "HTTP Error 404" in str(exc):
                raise PubTator3PendingError("PubTator3 annotation job is not ready yet.") from exc
            raise

    def annotate_text(
        self,
        payload: bytes | str,
        *,
        bioconcept: str = DEFAULT_BIOCONCEPT,
        max_attempts: int = 10,
        poll_interval: float = 1.0,
    ) -> str:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")

        session_id = self.submit_text_annotation(payload, bioconcept=bioconcept)
        last_error: PubTator3PendingError | None = None
        for attempt in range(max_attempts):
            try:
                return self.retrieve_text_annotation(session_id)
            except PubTator3PendingError as exc:
                last_error = exc
                if attempt == max_attempts - 1:
                    break
                time.sleep(poll_interval)

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
    ) -> Any:
        cleaned_identifiers = _clean_identifiers(identifiers)
        if not cleaned_identifiers:
            return {"documents": []} if format == "biocjson" else ""

        cleaned_concepts = _clean_identifiers(concepts or [])
        if format == "biocjson" and cleaned_concepts:
            raise ValueError("PubTator3 concepts filtering is not supported with biocjson export.")

        if len(cleaned_identifiers) <= self.get_batch_size:
            payloads = [self._fetch_export_batch(identifier_type, cleaned_identifiers, format=format, concepts=cleaned_concepts)]
        else:
            payloads = [
                self._fetch_export_batch(identifier_type, batch, format=format, concepts=cleaned_concepts)
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
    ) -> Any:
        endpoint = f"{self.base_url.rstrip('/')}/publications/export/{format}"
        params: dict[str, str] = {identifier_type: ",".join(identifiers)}
        if concepts:
            params["concepts"] = ",".join(concepts)

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

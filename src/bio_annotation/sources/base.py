"""Core contracts shared by every fetch source.

The :class:`FetchSource` protocol defines a tiny, uniform interface so the
orchestrator (and the Streamlit UI) can treat Entrez, Europe PMC, PubTator3,
and raw-text inputs interchangeably. A source declares:

* ``name`` - short identifier shown in the UI / logs
* ``supported_inputs`` - which kinds of :class:`FetchInput` it accepts
* ``fields_provided`` - which ``Document`` fields it can populate
* ``fetch(request)`` - the actual work
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from bio_annotation.schemas.document import Document

FetchKind = Literal["pmid", "pmid_list", "query", "raw_text"]


class UnsupportedInputError(ValueError):
    """Raised when a source is asked to handle an input kind it does not support."""


@dataclass(frozen=True, slots=True)
class FetchInput:
    """Request payload describing what the user wants to fetch.

    Construct via the ``from_*`` factory methods to keep call sites readable.
    """

    kind: FetchKind
    pmids: tuple[str, ...] = ()
    query: str = ""
    text: str = ""
    text_id: str = ""
    fields: frozenset[str] | None = None

    @classmethod
    def from_pmid(
        cls,
        pmid: str,
        *,
        fields: frozenset[str] | None = None,
    ) -> "FetchInput":
        cleaned = pmid.strip()
        if not cleaned:
            raise ValueError("PMID must not be empty.")
        return cls(kind="pmid", pmids=(cleaned,), fields=fields)

    @classmethod
    def from_pmid_list(
        cls,
        pmids: list[str],
        *,
        fields: frozenset[str] | None = None,
    ) -> "FetchInput":
        cleaned = tuple(p.strip() for p in pmids if p and p.strip())
        if not cleaned:
            raise ValueError("PMID list must contain at least one non-empty value.")
        return cls(kind="pmid_list", pmids=cleaned, fields=fields)

    @classmethod
    def from_query(
        cls,
        query: str,
        *,
        fields: frozenset[str] | None = None,
    ) -> "FetchInput":
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("Query must not be empty.")
        return cls(kind="query", query=cleaned, fields=fields)

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        text_id: str = "RAW:1",
    ) -> "FetchInput":
        if not text or not text.strip():
            raise ValueError("Raw text must not be empty.")
        return cls(kind="raw_text", text=text, text_id=text_id)


@runtime_checkable
class FetchSource(Protocol):
    """Uniform interface every fetch source implements.

    Implementations are typically dataclasses or simple classes that hold any
    configuration needed to talk to their backend (API base URL, timeout,
    API key, etc.) and expose a single :meth:`fetch` entry point.
    """

    name: str
    supported_inputs: frozenset[FetchKind]
    fields_provided: frozenset[str]

    def fetch(self, request: FetchInput) -> list[Document]: ...


def check_supports(source: FetchSource, request: FetchInput) -> None:
    """Validate that *source* can handle *request*; raise otherwise.

    Useful as a guard at the top of every source's ``fetch`` implementation
    so error messages are uniform across sources.
    """

    if request.kind not in source.supported_inputs:
        raise UnsupportedInputError(
            f"Source {source.name!r} does not support input kind {request.kind!r}. "
            f"Supported kinds: {sorted(source.supported_inputs)}."
        )

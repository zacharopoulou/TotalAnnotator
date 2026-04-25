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

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from bio_annotation.schemas.document import Document

FetchKind = Literal[
    "pmid",
    "pmid_list",
    "pmcid",
    "pmcid_list",
    "query",
    "raw_text",
]


class UnsupportedInputError(ValueError):
    """Raised when a source is asked to handle an input kind it does not support."""


@dataclass(frozen=True, slots=True)
class FetchInput:
    """Request payload describing what the user wants to fetch.

    Construct via the ``from_*`` factory methods to keep call sites readable.

    Field-filter semantics
    ----------------------
    Two complementary mechanisms control which fields each source keeps in
    ``Document.metadata``:

    * ``fields`` - a single set applied to **every** source (legacy / global).
    * ``fields_per_source`` - a per-source override, e.g.
      ``{"entrez": frozenset({"mesh_terms"}), "europe_pmc": frozenset(...)}``.
      A source is filtered using its own slice when present, even if it is
      empty, in which case only the source's core fields are kept.

    Sources should always read filters via :meth:`fields_for` so they get the
    right slice without caring which mechanism was used.
    """

    kind: FetchKind
    pmids: tuple[str, ...] = ()
    pmcids: tuple[str, ...] = ()
    query: str = ""
    text: str = ""
    text_id: str = ""
    fields: frozenset[str] | None = None
    fields_per_source: Mapping[str, frozenset[str]] | None = None

    def fields_for(self, source_name: str) -> frozenset[str] | None:
        """Return the field filter that applies to *source_name*.

        Resolution order:

        1. ``fields_per_source[source_name]`` if present (per-source wins).
        2. ``fields`` if set (legacy global filter).
        3. ``None`` (no filter; source returns all fields it normally would).
        """

        if self.fields_per_source is not None and source_name in self.fields_per_source:
            return self.fields_per_source[source_name]
        return self.fields

    @classmethod
    def from_pmid(
        cls,
        pmid: str,
        *,
        fields: frozenset[str] | None = None,
        fields_per_source: Mapping[str, frozenset[str]] | None = None,
    ) -> "FetchInput":
        cleaned = pmid.strip()
        if not cleaned:
            raise ValueError("PMID must not be empty.")
        return cls(
            kind="pmid",
            pmids=(cleaned,),
            fields=fields,
            fields_per_source=fields_per_source,
        )

    @classmethod
    def from_pmid_list(
        cls,
        pmids: list[str],
        *,
        fields: frozenset[str] | None = None,
        fields_per_source: Mapping[str, frozenset[str]] | None = None,
    ) -> "FetchInput":
        cleaned = tuple(p.strip() for p in pmids if p and p.strip())
        if not cleaned:
            raise ValueError("PMID list must contain at least one non-empty value.")
        return cls(
            kind="pmid_list",
            pmids=cleaned,
            fields=fields,
            fields_per_source=fields_per_source,
        )

    @classmethod
    def from_pmcid(
        cls,
        pmcid: str,
        *,
        fields: frozenset[str] | None = None,
        fields_per_source: Mapping[str, frozenset[str]] | None = None,
    ) -> "FetchInput":
        cleaned = _normalize_pmcid(pmcid)
        return cls(
            kind="pmcid",
            pmcids=(cleaned,),
            fields=fields,
            fields_per_source=fields_per_source,
        )

    @classmethod
    def from_pmcid_list(
        cls,
        pmcids: list[str],
        *,
        fields: frozenset[str] | None = None,
        fields_per_source: Mapping[str, frozenset[str]] | None = None,
    ) -> "FetchInput":
        cleaned = tuple(_normalize_pmcid(p) for p in pmcids if p and p.strip())
        if not cleaned:
            raise ValueError("PMCID list must contain at least one non-empty value.")
        return cls(
            kind="pmcid_list",
            pmcids=cleaned,
            fields=fields,
            fields_per_source=fields_per_source,
        )

    @classmethod
    def from_query(
        cls,
        query: str,
        *,
        fields: frozenset[str] | None = None,
        fields_per_source: Mapping[str, frozenset[str]] | None = None,
    ) -> "FetchInput":
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("Query must not be empty.")
        return cls(
            kind="query",
            query=cleaned,
            fields=fields,
            fields_per_source=fields_per_source,
        )

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


def _normalize_pmcid(value: str) -> str:
    """Return a PMCID with the canonical ``PMC`` prefix.

    PubTator3 and Europe PMC both expect the ``PMC`` prefix; users often paste
    the bare digits. Accept either form so call sites stay friendly.
    """

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

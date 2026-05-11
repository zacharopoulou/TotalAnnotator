"""Request payload (FetchInput), source protocol (FetchSource), and per-source field catalogs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from bio_annotation.schemas.document import Document


#A. Per-source field catalogs 

# PubTator3: BioC export and embedded annotations.
PUBTATOR3_FIELDS = frozenset(
    {
        "pmid",
        "pmcid",
        "title",
        "abstract",
        "full_text",
        "annotations",
    }
)

# NCBI E-utilities, parsed PubMed record (--> io.readers.fetch_pubmed_record).
ENTREZ_FIELDS = frozenset(
    {
        "pmid",
        "pmcid",
        "doi",
        "title",
        "abstract",
        "structured_abstract",
        "year",
        "authors",
        "affiliations",
        "journal",
        "journal_abbrev",
        "volume",
        "issue",
        "pages",
        "language",
        "publication_type",
        "country",
        "pub_date",
        "epub_date",
        "received_date",
        "accepted_date",
        "medline_date",
        "entrez_date",
        "revision_date",
        "keywords",
        "mesh_terms",
        "chemicals",
        "gene_symbols",
        "supplemental_mesh",
        "grants",
        "elinks",
    }
)

# Europe PMC: citations, OA flags, full-text URLs, JATS body.
EUROPE_PMC_FIELDS = frozenset(
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

FIELD_OWNERS: dict[str, frozenset[str]] = {
    "pubtator3": PUBTATOR3_FIELDS,
    "entrez": ENTREZ_FIELDS,
    "europe_pmc": EUROPE_PMC_FIELDS,
}


def sources_for_field(field: str) -> list[str]:
    """Return backend names that advertise *field* in their catalog."""

    return sorted(name for name, fields in FIELD_OWNERS.items() if field in fields)


# B.  Request shape 

FetchKind = Literal[
    "pmid",
    "pmid_list",
    "pmcid",
    "pmcid_list",
]


class UnsupportedInputError(ValueError):
    """Raised when a source cannot handle the given input kind."""


@dataclass(frozen=True, slots=True)
class FetchInput:
    """What to fetch: known PMIDs or PMCIDs (no query support; use search-pmids upstream)."""

    kind: FetchKind
    pmids: tuple[str, ...] = ()
    pmcids: tuple[str, ...] = ()
    fields: frozenset[str] | None = None
    fields_per_source: Mapping[str, frozenset[str]] | None = None

    def fields_for(self, source_name: str) -> frozenset[str] | None:
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
    ) -> FetchInput:
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
    ) -> FetchInput:
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
    ) -> FetchInput:
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
    ) -> FetchInput:
        cleaned = tuple(_normalize_pmcid(p) for p in pmcids if p and p.strip())
        if not cleaned:
            raise ValueError("PMCID list must contain at least one non-empty value.")
        return cls(
            kind="pmcid_list",
            pmcids=cleaned,
            fields=fields,
            fields_per_source=fields_per_source,
        )

# C. Source protocol

@runtime_checkable
class FetchSource(Protocol):
    """One backend that turns a class `FetchInput` into class `Document` rows."""

    name: str
    supported_inputs: frozenset[FetchKind]
    fields_provided: frozenset[str]

    def fetch(self, request: FetchInput) -> list[Document]: ...


def check_supports(source: FetchSource, request: FetchInput) -> None:
    if request.kind not in source.supported_inputs:
        raise UnsupportedInputError(
            f"Source {source.name!r} does not support input kind {request.kind!r}. "
            f"Supported kinds: {sorted(source.supported_inputs)}."
        )


# D. Internal helpers 

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
    "ENTREZ_FIELDS",
    "EUROPE_PMC_FIELDS",
    "FetchInput",
    "FetchKind",
    "FetchSource",
    "FIELD_OWNERS",
    "PUBTATOR3_FIELDS",
    "UnsupportedInputError",
    "check_supports",
    "sources_for_field",
]

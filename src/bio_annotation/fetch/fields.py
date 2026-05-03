"""Which logical fields each fetch backend can populate on/in :class:`~bio_annotation.schemas.document.Document`.

Use this to decide when to call Entrez, Europe PMC, etc., beyond the default
PubTator3 pass. Keys align with :attr:`FetchSource.fields_provided` on each
source implementation.
"""

from __future__ import annotations

# PubTator3: BioC export + embedded annotations; search scores when using query.
PUBTATOR3_FIELDS = frozenset(
    {
        "pmid",
        "pmcid",
        "title",
        "abstract",
        "full_text",
        "annotations",
        "score",
    }
)

# NCBI E-utilities / parsed PubMed record (see io.readers.fetch_pubmed_record).
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

# Reserved for Europe PMC client when wired (citations, OA, full-text URLs).
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


__all__ = [
    "ENTREZ_FIELDS",
    "EUROPE_PMC_FIELDS",
    "FIELD_OWNERS",
    "PUBTATOR3_FIELDS",
    "sources_for_field",
]

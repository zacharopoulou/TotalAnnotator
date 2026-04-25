"""Entrez (NCBI E-utilities) fetch source - stub.

Will provide rich PubMed metadata (title, abstract, authors, MeSH terms,
journal, dates, DOI, PMCID, ...) via ``efetch`` plus PMID resolution via
``esearch``. To be ported from the ``total_fetcher`` branch in the next
chunk of work.
"""

from __future__ import annotations

from dataclasses import dataclass

from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import FetchInput, FetchKind, check_supports


@dataclass(slots=True)
class EntrezSource:
    """Fetch source backed by NCBI E-utilities (efetch + esearch)."""

    name: str = "entrez"
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid", "pmid_list", "query"})
    fields_provided: frozenset[str] = frozenset(
        {
            "pmid",
            "title",
            "abstract",
            "year",
            "authors",
            "journal",
            "mesh_terms",
            "doi",
            "pmcid",
            "publication_types",
            "keywords",
        }
    )

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)
        raise NotImplementedError(
            "EntrezSource.fetch is scheduled for the next chunk of work."
        )

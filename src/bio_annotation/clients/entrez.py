from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from bio_annotation.io.readers import fetch_pubmed_record
from bio_annotation.io.search import search_pubmed_pmids


@dataclass(slots=True)
class EntrezClient:
    """Thin wrapper around PubMed efetch (record) and esearch (PMID lists)."""

    timeout: int = 30

    def fetch_pubmed(
        self,
        pmid: str,
        *,
        enrichments: list[str] | None = None,
    ) -> dict[str, Any]:
        return fetch_pubmed_record(pmid, timeout=self.timeout, enrichments=enrichments)

    def search_pubmed(
        self,
        query: str,
        *,
        max_results: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_by: str = "relevance",
        filters: list[str] | None = None,
        esearch_fn: Callable[[str], dict[str, Any]] | None = None,
    ) -> list[str]:
        return search_pubmed_pmids(
            query,
            max_results=max_results,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            filters=filters,
            timeout=self.timeout,
            esearch_fn=esearch_fn,
        )


__all__ = ["EntrezClient"]

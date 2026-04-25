"""Europe PMC fetch source - stub.

Will provide citation counts, open-access flags, and JATS full text for
articles available through Europe PMC. To be ported from the
``total_fetcher`` branch in a follow-up chunk.
"""

from __future__ import annotations

from dataclasses import dataclass

from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import FetchInput, FetchKind, check_supports


@dataclass(slots=True)
class EuropePmcSource:
    """Fetch source backed by the Europe PMC REST API."""

    name: str = "europe_pmc"
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid", "pmid_list", "query"})
    fields_provided: frozenset[str] = frozenset(
        {
            "pmid",
            "pmcid",
            "title",
            "abstract",
            "full_text",
            "is_open_access",
            "citation_count",
        }
    )

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)
        raise NotImplementedError(
            "EuropePmcSource.fetch is scheduled for a follow-up chunk."
        )

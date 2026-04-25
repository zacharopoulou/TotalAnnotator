"""PubTator3 fetch source - stub.

Will use the existing ``bio_annotation.clients.pubtator3.PubTator3Client``
to retrieve title, abstract, and pre-computed entity annotations in one
shot. The annotations come back already populated, so downstream
"annotation" becomes a no-op for this source (or a normalization pass).

To be wired up in a follow-up chunk.
"""

from __future__ import annotations

from dataclasses import dataclass

from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import FetchInput, FetchKind, check_supports


@dataclass(slots=True)
class PubTator3Source:
    """Fetch source backed by the PubTator3 publication-export API."""

    name: str = "pubtator3"
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid", "pmid_list"})
    fields_provided: frozenset[str] = frozenset(
        {
            "pmid",
            "pmcid",
            "title",
            "abstract",
            "annotations",
        }
    )

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)
        raise NotImplementedError(
            "PubTator3Source.fetch is scheduled for a follow-up chunk."
        )

"""Raw-text fetch source - stub.

Wraps user-pasted text into a single :class:`Document`. No network call.
Implementation is trivial and will be added in a follow-up chunk.
"""

from __future__ import annotations

from dataclasses import dataclass

from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import FetchInput, FetchKind, check_supports


@dataclass(slots=True)
class RawTextSource:
    """Fetch source that wraps a user-supplied string with no network I/O."""

    name: str = "raw_text"
    supported_inputs: frozenset[FetchKind] = frozenset({"raw_text"})
    fields_provided: frozenset[str] = frozenset({"abstract"})

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)
        raise NotImplementedError(
            "RawTextSource.fetch is scheduled for a follow-up chunk."
        )

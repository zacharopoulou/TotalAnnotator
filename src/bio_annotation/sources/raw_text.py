"""Raw-text fetch source.

Wraps a user-supplied string in a :class:`Document` with no network call.
The text lands in :attr:`Document.abstract` so existing annotators (which
already operate on title + abstract) pick it up unchanged.

If the caller wants the text annotated by PubTator3 they should either:

1. Use :class:`bio_annotation.sources.pubtator3.PubTator3Source` with a
   ``raw_text`` :class:`FetchInput` (one source, one call), or
2. Use this source to wrap the text into a :class:`Document`, then run the
   PubTator3 annotator on that document (two stages, more flexible).
"""

from __future__ import annotations

from dataclasses import dataclass

from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import FetchInput, FetchKind, check_supports


@dataclass(slots=True)
class RawTextSource:
    """Wraps user-pasted text in a :class:`Document`. No HTTP."""

    name: str = "raw_text"
    supported_inputs: frozenset[FetchKind] = frozenset({"raw_text"})
    fields_provided: frozenset[str] = frozenset({"abstract"})

    def fetch(self, request: FetchInput) -> list[Document]:
        check_supports(self, request)
        text = (request.text or "").strip()
        if not text:
            return []

        document_id = (request.text_id or "").strip() or "RAW:1"
        return [
            Document(
                document_id=document_id,
                pmid=None,
                title="",
                abstract=text,
                full_text=None,
                source="raw_text",
                metadata={},
            )
        ]


__all__ = ["RawTextSource"]

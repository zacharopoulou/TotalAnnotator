"""Raw-text fetch source — wraps pasted text in a :class:`~bio_annotation.schemas.document.Document` (no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass

from bio_annotation.fetch.input import FetchInput, FetchKind, check_supports
from bio_annotation.schemas.document import Document


@dataclass(slots=True)
class RawTextSource:
    """User-supplied string → ``Document`` with text in :attr:`Document.abstract`."""

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

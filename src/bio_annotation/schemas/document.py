from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Document:
    """Canonical document container shared by all annotator adapters."""

    document_id: str
    pmid: str | None = None
    title: str = ""
    abstract: str = ""
    full_text: str | None = None
    source: str = "unknown"
    year: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_text(self, *, prefer_full_text: bool = True, include_title: bool = True) -> str:
        """Return the text that annotators should process."""

        parts: list[str] = []
        if include_title and self.title:
            parts.append(self.title.strip())

        body = self.full_text if prefer_full_text and self.full_text else self.abstract
        if body:
            parts.append(body.strip())

        return "\n\n".join(part for part in parts if part)

    @property
    def text(self) -> str:
        """Convenience alias for the default annotator text."""

        return self.get_text()

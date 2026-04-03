from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Annotation:
    """Unified entity annotation returned by every annotator adapter."""

    annotation_id: str
    source: str
    span_text: str
    start: int | None
    end: int | None
    entity_type: str
    canonical_id: str | None = None
    canonical_name: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

from bio_annotation.entity_proposal.clinicalbert_proposer import (
    DEFAULT_CLINICALBERT_MODEL,
    annotate_with_clinicalbert,
    parse_clinicalbert_response,
)

__all__ = [
    "DEFAULT_CLINICALBERT_MODEL",
    "annotate_with_clinicalbert",
    "parse_clinicalbert_response",
]

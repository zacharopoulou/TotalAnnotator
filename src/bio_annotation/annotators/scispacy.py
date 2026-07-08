from __future__ import annotations

from bio_annotation.entity_proposal.scispacy_proposer import (
    SCISPACY_INSTALL_HINT,
    SCISPACY_MODEL_BY_ANNOTATOR,
    SCISPACY_UMLS_ANNOTATOR,
    _load_scispacy_model,
    annotate_with_scispacy,
    annotate_with_scispacy_bc5cdr,
    annotate_with_scispacy_bionlp13cg,
    annotate_with_scispacy_jnlpba,
    annotate_with_scispacy_umls,
    parse_scispacy_response,
)

__all__ = [
    "SCISPACY_INSTALL_HINT",
    "SCISPACY_MODEL_BY_ANNOTATOR",
    "SCISPACY_UMLS_ANNOTATOR",
    "_load_scispacy_model",
    "annotate_with_scispacy",
    "annotate_with_scispacy_bc5cdr",
    "annotate_with_scispacy_bionlp13cg",
    "annotate_with_scispacy_jnlpba",
    "annotate_with_scispacy_umls",
    "parse_scispacy_response",
]

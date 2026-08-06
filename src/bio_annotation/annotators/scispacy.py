from __future__ import annotations

from bio_annotation.entity_proposal.scispacy_proposer import (
    SCISPACY_INSTALL_HINT,
    SCISPACY_LINKER_ANNOTATORS,
    SCISPACY_LINKER_NAME_BY_ANNOTATOR,
    SCISPACY_MODEL_BY_ANNOTATOR,
    SCISPACY_SCIBERT_ANNOTATOR,
    _load_scispacy_model,
    annotate_with_scispacy,
    annotate_with_scispacy_bc5cdr,
    annotate_with_scispacy_bionlp13cg,
    annotate_with_scispacy_craft,
    annotate_with_scispacy_jnlpba,
    annotate_with_scispacy_md,
    annotate_with_scispacy_scibert,
    parse_scispacy_response,
)

__all__ = [
    "SCISPACY_INSTALL_HINT",
    "SCISPACY_LINKER_ANNOTATORS",
    "SCISPACY_LINKER_NAME_BY_ANNOTATOR",
    "SCISPACY_MODEL_BY_ANNOTATOR",
    "SCISPACY_SCIBERT_ANNOTATOR",
    "_load_scispacy_model",
    "annotate_with_scispacy",
    "annotate_with_scispacy_bc5cdr",
    "annotate_with_scispacy_bionlp13cg",
    "annotate_with_scispacy_craft",
    "annotate_with_scispacy_jnlpba",
    "annotate_with_scispacy_md",
    "annotate_with_scispacy_scibert",
    "parse_scispacy_response",
]

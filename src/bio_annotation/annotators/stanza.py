from __future__ import annotations

from bio_annotation.entity_proposal.stanza_proposer import (
    STANZA_ANNOTATORS,
    STANZA_MODELS,
    annotate_with_stanza,
    parse_stanza_entities,
    stanza_model_for_annotator,
    stanza_source,
)

__all__ = [
    "STANZA_ANNOTATORS",
    "STANZA_MODELS",
    "annotate_with_stanza",
    "parse_stanza_entities",
    "stanza_model_for_annotator",
    "stanza_source",
]

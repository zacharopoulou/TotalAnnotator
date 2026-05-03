from __future__ import annotations

from bio_annotation.entity_proposal.flair_proposer import (
    annotate_with_flair,
    collect_flair_annotations_from_sentence,
    flair_sentence_to_jsonable,
    parse_flair_labels,
    parse_flair_spans,
    run_flair_on_document,
)

__all__ = [
    "annotate_with_flair",
    "collect_flair_annotations_from_sentence",
    "flair_sentence_to_jsonable",
    "parse_flair_labels",
    "parse_flair_spans",
    "run_flair_on_document",
]

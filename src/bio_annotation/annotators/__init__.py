"""Primary annotator adapter package."""

from __future__ import annotations

from bio_annotation.entity_proposal import (
    annotate_with_bern2,
    annotate_with_flair,
    annotate_with_pubtator,
    flatten_annotations,
    run_all_annotators,
)

__all__ = [
    "annotate_with_bern2",
    "annotate_with_flair",
    "annotate_with_pubtator",
    "flatten_annotations",
    "run_all_annotators",
]

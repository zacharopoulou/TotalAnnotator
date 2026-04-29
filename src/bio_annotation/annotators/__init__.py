"""Primary annotator adapter package."""

from __future__ import annotations

from typing import Any

from bio_annotation.annotators.bern2 import annotate_with_bern2
from bio_annotation.annotators.flair import annotate_with_flair
from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation


def run_all_annotators(
    document: Document,
    *,
    bern2_response: Any = None,
    bern2_request_fn: Any = None,
    bern2_endpoint: str | None = None,
    flair_spans: Any = None,
    flair_tagger: Any = None,
    flair_sentence_factory: Any = None,
    pubtator3_response: Any = None,
    pubtator3_request_fn: Any = None,
    pubtator3_endpoint: str | None = None,
) -> dict[str, list[Annotation]]:
    return {
        "bern2": annotate_with_bern2(
            document,
            response=bern2_response,
            request_fn=bern2_request_fn,
            endpoint=bern2_endpoint,
        ),
        "flair": annotate_with_flair(
            document,
            spans=flair_spans,
            tagger=flair_tagger,
            sentence_factory=flair_sentence_factory,
        ),
        "pubtator3": annotate_with_pubtator3(
            document,
            response=pubtator3_response,
            request_fn=pubtator3_request_fn,
            endpoint=pubtator3_endpoint,
        ),
    }


def flatten_annotations(results: dict[str, list[Annotation]]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for source in ("bern2", "flair", "pubtator3"):
        annotations.extend(results.get(source, []))
    return annotations

__all__ = [
    "annotate_with_bern2",
    "annotate_with_flair",
    "annotate_with_pubtator3",
    "flatten_annotations",
    "run_all_annotators",
]

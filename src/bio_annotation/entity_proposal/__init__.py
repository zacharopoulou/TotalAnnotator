"""Annotator adapters and runner utilities."""

from __future__ import annotations

from typing import Any

from bio_annotation.entity_proposal.bern2_proposer import annotate_with_bern2
from bio_annotation.entity_proposal.flair_proposer import annotate_with_flair
from bio_annotation.entity_proposal.pubtator_proposer import annotate_with_pubtator
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
    pubtator_response: Any = None,
    pubtator_request_fn: Any = None,
    pubtator_endpoint: str | None = None,
) -> dict[str, list[Annotation]]:
    """Run all configured annotator adapters and return normalized outputs."""

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
        "pubtator": annotate_with_pubtator(
            document,
            response=pubtator_response,
            request_fn=pubtator_request_fn,
            endpoint=pubtator_endpoint,
        ),
    }


def flatten_annotations(results: dict[str, list[Annotation]]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for source in ("bern2", "flair", "pubtator"):
        annotations.extend(results.get(source, []))
    return annotations


__all__ = [
    "annotate_with_bern2",
    "annotate_with_flair",
    "annotate_with_pubtator",
    "flatten_annotations",
    "run_all_annotators",
]

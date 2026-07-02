"""Annotator adapters and runner utilities."""

from __future__ import annotations

import sys
from typing import Any

from bio_annotation.entity_proposal.apollo_proposer import annotate_with_apollo
from bio_annotation.entity_proposal.bern2_proposer import annotate_with_bern2
from bio_annotation.entity_proposal.flair_proposer import annotate_with_flair
from bio_annotation.entity_proposal.medcat_proposer import annotate_with_medcat
from bio_annotation.entity_proposal.pubtator3_proposer import annotate_with_pubtator3
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

# AIONER's subprocess runner differs on Windows (see aioner_windows); resolve the
# same platform-specific implementation the annotators.aioner shim uses so this
# package's public API and run_all_annotators don't bypass it on Windows.
if sys.platform == "win32":
    from bio_annotation.entity_proposal.aioner_windows import annotate_with_aioner
else:
    from bio_annotation.entity_proposal.aioner_proposer import annotate_with_aioner


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
    aioner_response: Any = None,
    aioner_request_fn: Any = None,
    apollo_response: Any = None,
    apollo_request_fn: Any = None,
    apollo_pipeline: Any = None,
    medcat_response: Any = None,
    medcat_request_fn: Any = None,
    medcat_endpoint: str | None = None,
) -> dict[str, list[Annotation]]:
    """Run all configured annotator adapters and return normalized outputs."""

    results = {
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
    # Only invoke AIONER when a response or request function is provided.
    if aioner_response is not None or aioner_request_fn is not None:
        results["aioner"] = annotate_with_aioner(
            document,
            response=aioner_response,
            request_fn=aioner_request_fn,
        )
    # Only invoke apollo when a response, request function, or pipeline is provided.
    if (
        apollo_response is not None
        or apollo_request_fn is not None
        or apollo_pipeline is not None
    ):
        results["apollo"] = annotate_with_apollo(
            document,
            response=apollo_response,
            request_fn=apollo_request_fn,
            pipeline=apollo_pipeline,
        )
    # Only invoke MedCAT when a response, request function, or endpoint is provided.
    if (
        medcat_response is not None
        or medcat_request_fn is not None
        or medcat_endpoint is not None
    ):
        results["medcat"] = annotate_with_medcat(
            document,
            response=medcat_response,
            request_fn=medcat_request_fn,
            endpoint=medcat_endpoint,
        )
    return results


def flatten_annotations(results: dict[str, list[Annotation]]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for source in ("bern2", "flair", "pubtator3", "aioner", "apollo", "medcat"):
        annotations.extend(results.get(source, []))
    return annotations


__all__ = [
    "annotate_with_aioner",
    "annotate_with_apollo",
    "annotate_with_bern2",
    "annotate_with_flair",
    "annotate_with_medcat",
    "annotate_with_pubtator3",
    "flatten_annotations",
    "run_all_annotators",
]

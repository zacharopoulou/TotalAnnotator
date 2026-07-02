"""Primary annotator adapter package."""

from __future__ import annotations

from typing import Any

from bio_annotation.annotators.aioner import annotate_with_aioner
from bio_annotation.annotators.apollo import annotate_with_apollo
from bio_annotation.annotators.bern2 import annotate_with_bern2
from bio_annotation.annotators.d4data import annotate_with_d4data
from bio_annotation.annotators.flair import annotate_with_flair
from bio_annotation.annotators.medcat import annotate_with_medcat
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
    aioner_response: Any = None,
    aioner_request_fn: Any = None,
    d4data_response: Any = None,
    d4data_request_fn: Any = None,
    d4data_pipeline: Any = None,
    apollo_response: Any = None,
    apollo_request_fn: Any = None,
    apollo_pipeline: Any = None,
    medcat_response: Any = None,
    medcat_request_fn: Any = None,
    medcat_endpoint: str | None = None,
) -> dict[str, list[Annotation]]:
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
    # AIONER runs in a separate environment, so only invoke it when an explicit
    # response or request function is supplied (avoids spawning the subprocess in
    # callers that don't use it, e.g. the demo command).
    if aioner_response is not None or aioner_request_fn is not None:
        results["aioner"] = annotate_with_aioner(
            document,
            response=aioner_response,
            request_fn=aioner_request_fn,
        )
    # d4data loads a local HuggingFace model, so only invoke it when an explicit
    # response, request function, or loaded pipeline is supplied (avoids loading
    # the model in callers that don't use it, e.g. the demo command).
    if (
        d4data_response is not None
        or d4data_request_fn is not None
        or d4data_pipeline is not None
    ):
        results["d4data"] = annotate_with_d4data(
            document,
            response=d4data_response,
            request_fn=d4data_request_fn,
            pipeline=d4data_pipeline,
        )
    # apollo loads a local HuggingFace model, so only invoke it when an explicit
    # response, request function, or loaded pipeline is supplied (avoids loading
    # the model in callers that don't use it, e.g. the demo command).
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
    # MedCAT calls a remote service, so only invoke it when an explicit response,
    # request function, or endpoint is supplied (avoids hitting a service in
    # callers that don't use it, e.g. the demo command).
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
    for source in ("bern2", "flair", "pubtator3", "aioner", "d4data", "apollo", "medcat"):
        annotations.extend(results.get(source, []))
    return annotations

__all__ = [
    "annotate_with_aioner",
    "annotate_with_apollo",
    "annotate_with_bern2",
    "annotate_with_d4data",
    "annotate_with_flair",
    "annotate_with_medcat",
    "annotate_with_pubtator3",
    "flatten_annotations",
    "run_all_annotators",
]

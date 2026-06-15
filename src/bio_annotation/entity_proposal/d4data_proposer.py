from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

DEFAULT_D4DATA_MODEL = "d4data/biomedical-ner-all"


def parse_d4data_response(
    document: Document,
    payload: Iterable[Any] | None,
) -> list[Annotation]:
    """Parse HuggingFace token-classification output into Annotations.

    The transformers NER pipeline uses ``aggregation_strategy="first"``; clinical
    labels without a canonical mapping pass through as their normalized form.
    """

    if not payload:
        return []

    annotations: list[Annotation] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        label = item.get("entity_group") or item.get("entity")
        start = item.get("start")
        end = item.get("end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end:
            span_text = document.text[start:end]
        else:
            span_text = item.get("word")
            start = end = None
        if not span_text:
            continue

        annotations.append(
            make_annotation(
                document=document,
                source="d4data",
                span_text=span_text,
                entity_type=label,
                start=start,
                end=end,
                confidence=item.get("score"),
            )
        )

    return annotations


@lru_cache(maxsize=2)
def _load_d4data_pipeline(model: str) -> Any:
    from transformers import pipeline

    # "first" groups sub-word tokens into whole words: this model tags every
    # sub-word as a B- entity, so "simple" would split "glioblastoma" into
    # "g"+"##lioblastoma". "first" merges them and keeps the first sub-word's label.
    return pipeline(
        "ner",
        model=model,
        tokenizer=model,
        aggregation_strategy="first",
    )


def annotate_with_d4data(
    document: Document,
    *,
    response: Any = None,
    request_fn: Callable[[Document], Any] | None = None,
    pipeline: Any = None,
    model: str | None = None,
    pipeline_loader: Callable[[str], Any] | None = None,
) -> list[Annotation]:
    payload = response
    if payload is None and request_fn is not None:
        payload = request_fn(document)
    if payload is None:
        if pipeline is None and model:
            loader = pipeline_loader or _load_d4data_pipeline
            pipeline = loader(model)
        if pipeline is not None:
            payload = pipeline(document.text)
    return parse_d4data_response(document, payload)

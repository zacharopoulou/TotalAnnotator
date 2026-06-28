from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

# i2b2-2010 clinical NER (problem / test / treatment), fine-tuned from BERT.
DEFAULT_CLINICALBERT_MODEL = "samrawal/bert-base-uncased_clinical-ner"


def parse_clinicalbert_response(
    document: Document,
    payload: Iterable[Any] | None,
) -> list[Annotation]:
    """Parse HuggingFace token-classification output into Annotations.

    The transformers NER pipeline uses ``aggregation_strategy="first"``. The
    clinical labels (problem / test / treatment) are kept as their own types
    rather than mapped onto the canonical biomedical set.
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
                source="clinicalbert",
                span_text=span_text,
                entity_type=label,
                start=start,
                end=end,
                confidence=item.get("score"),
            )
        )

    return annotations


@lru_cache(maxsize=2)
def _load_clinicalbert_pipeline(model: str) -> Any:
    from transformers import pipeline

    # "first" groups sub-word tokens into whole words and keeps the first
    # sub-word's label, which is what this B-/I- tagging model needs.
    return pipeline(
        "ner",
        model=model,
        tokenizer=model,
        aggregation_strategy="first",
    )


def annotate_with_clinicalbert(
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
            loader = pipeline_loader or _load_clinicalbert_pipeline
            pipeline = loader(model)
        if pipeline is not None:
            payload = pipeline(document.text)
    return parse_clinicalbert_response(document, payload)

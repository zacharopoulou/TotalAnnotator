from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

DEFAULT_APOLLO_MODEL = "Clinical-AI-Apollo/Medical-NER"

APOLLO_INSTALL_HINT = (
    "The apollo annotator requires the optional Hugging Face dependencies. "
    "Install them with: uv sync --extra apollo"
)

# Apollo can emit spans with leading/trailing punctuation (e.g. "glioblastoma:",
# "clinical behavior."); trim those boundary characters off the edges while
# keeping offsets correct. Hyphen and slash are excluded since they occur inside
# clinical terms (e.g. "mg/dL", "5-HT").
_BOUNDARY_CHARS = " \t\n\r\f\v.,;:!?()[]{}\"'"


def _trim_boundary(
    text: str, start: int | None, end: int | None
) -> tuple[str, int | None, int | None]:
    inner = text.strip(_BOUNDARY_CHARS)
    if not inner or not isinstance(start, int) or not isinstance(end, int):
        return inner, start, end
    lead = len(text) - len(text.lstrip(_BOUNDARY_CHARS))
    new_start = start + lead
    return inner, new_start, new_start + len(inner)


def parse_apollo_response(
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
        span_text, start, end = _trim_boundary(span_text, start, end)
        if not span_text:
            continue

        annotations.append(
            make_annotation(
                document=document,
                source="apollo",
                span_text=span_text,
                entity_type=label,
                start=start,
                end=end,
                confidence=item.get("score"),
            )
        )

    return annotations


@lru_cache(maxsize=2)
def _load_apollo_pipeline(model: str) -> Any:
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise RuntimeError(APOLLO_INSTALL_HINT) from exc

    return pipeline(
        "ner",
        model=model,
        tokenizer=model,
        aggregation_strategy="first",
    )


def annotate_with_apollo(
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
            loader = pipeline_loader or _load_apollo_pipeline
            pipeline = loader(model)
        if pipeline is not None:
            payload = pipeline(document.text)
    return parse_apollo_response(document, payload)

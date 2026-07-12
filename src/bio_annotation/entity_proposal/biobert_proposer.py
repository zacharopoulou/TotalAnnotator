from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

# BioBERT NER is published as per-entity fine-tuned checkpoints rather than a
# single multi-type model. The biobert annotator runs one HuggingFace token-
# classification model per canonical type and merges them, so a single "biobert"
# source covers gene / disease / chemical. Each checkpoint recognises one family,
# so the producing model decides the entity type; the raw label is read only to
# drop the model's non-entity ("outside") tokens.
DEFAULT_BIOBERT_MODELS: dict[str, str] = {
    "gene": "alvaroalon2/biobert_genetic_ner",
    "disease": "alvaroalon2/biobert_diseases_ner",
    "drug": "alvaroalon2/biobert_chemical_ner",
}

# The "outside" (non-entity) tag varies across checkpoints. The diseases model
# mislabels it as "0" instead of the standard "O", so the transformers pipeline
# surfaces bogus "0" spans covering plain text. Treat both as outside and drop.
_OUTSIDE_LABELS = {"O", "0", ""}

BIOBERT_INSTALL_HINT = (
    "The BioBERT annotator requires the optional Hugging Face dependencies. "
    "Install them with: uv sync --extra biobert"
)

# Trim leading/trailing punctuation off spans while keeping offsets correct.
# Hyphen and slash are excluded since they occur inside biomedical terms
# (e.g. "5-HT", "mg/dL", "IL-2").
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


def parse_biobert_response(
    document: Document,
    payload: Iterable[Any] | None,
    *,
    entity_type: str,
) -> list[Annotation]:
    """Parse one BioBERT checkpoint's HuggingFace token-classification output.

    Every returned span is stamped with ``entity_type`` because each checkpoint
    recognises a single entity family. The pipeline uses
    ``aggregation_strategy="first"``, so spans are already word-grouped.
    """

    if not payload:
        return []

    annotations: list[Annotation] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        # The producing model sets the type; the label is only used to skip the
        # model's "outside" tokens (some checkpoints emit "0" instead of "O").
        label = item.get("entity_group") or item.get("entity")
        if label is not None and str(label).strip().upper() in _OUTSIDE_LABELS:
            continue
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
        # Drop pure-punctuation spans, but keep short gene names (e.g. "p53").
        if not span_text or not any(ch.isalnum() for ch in span_text):
            continue

        annotations.append(
            make_annotation(
                document=document,
                source="biobert",
                span_text=span_text,
                entity_type=entity_type,
                start=start,
                end=end,
                confidence=item.get("score"),
            )
        )

    return annotations


@lru_cache(maxsize=8)
def _load_biobert_pipeline(model: str) -> Any:
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise RuntimeError(BIOBERT_INSTALL_HINT) from exc

    # "first" groups sub-word tokens into whole words and keeps the first
    # sub-word's label, matching these B-/I- tagging checkpoints.
    return pipeline(
        "ner",
        model=model,
        tokenizer=model,
        aggregation_strategy="first",
    )


def load_biobert_pipelines(
    models: dict[str, str] | None = None,
    *,
    pipeline_loader: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Load one pipeline per entity family, so a run reuses them across documents."""
    models = models or DEFAULT_BIOBERT_MODELS
    loader = pipeline_loader or _load_biobert_pipeline
    return {entity_type: loader(model) for entity_type, model in models.items()}


def annotate_with_biobert(
    document: Document,
    *,
    response: dict[str, Any] | None = None,
    request_fn: Callable[[Document], dict[str, Any]] | None = None,
    pipelines: dict[str, Any] | None = None,
    models: dict[str, str] | None = None,
    pipeline_loader: Callable[[str], Any] | None = None,
) -> list[Annotation]:
    """Run each BioBERT checkpoint and merge into one ``biobert`` result set.

    ``response`` / ``request_fn`` supply pre-computed output as a mapping of
    entity type -> HuggingFace payload; ``pipelines`` supplies preloaded
    pipelines keyed the same way.
    """
    models = models or DEFAULT_BIOBERT_MODELS

    payloads = response
    if payloads is None and request_fn is not None:
        payloads = request_fn(document)

    annotations: list[Annotation] = []
    if payloads is not None:
        for entity_type, payload in payloads.items():
            annotations.extend(
                parse_biobert_response(document, payload, entity_type=entity_type)
            )
        return annotations

    loader = pipeline_loader or _load_biobert_pipeline
    for entity_type, model in models.items():
        pipe = pipelines.get(entity_type) if pipelines else None
        if pipe is None:
            pipe = loader(model)
        payload = pipe(document.text)
        annotations.extend(
            parse_biobert_response(document, payload, entity_type=entity_type)
        )
    return annotations

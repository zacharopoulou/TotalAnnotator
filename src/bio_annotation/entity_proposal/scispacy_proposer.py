from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

SCISPACY_INSTALL_HINT = (
    "The scispaCy annotators require scispaCy and the selected model package. "
    "Install dependencies with: uv sync --extra scispacy, then install the model "
    "package from https://allenai.github.io/scispacy/"
)

SCISPACY_MODEL_BY_ANNOTATOR: dict[str, str] = {
    "scispacy_jnlpba": "en_ner_jnlpba_md",
    "scispacy_bc5cdr": "en_ner_bc5cdr_md",
    "scispacy_bionlp13cg": "en_ner_bionlp13cg_md",
}


@lru_cache(maxsize=3)
def _load_scispacy_model(model: str) -> Any:
    try:
        import scispacy  # noqa: F401
        import spacy
    except ImportError as exc:
        raise RuntimeError(SCISPACY_INSTALL_HINT) from exc

    try:
        return spacy.load(model)
    except OSError as exc:
        raise RuntimeError(
            f"scispaCy model '{model}' is not installed. {SCISPACY_INSTALL_HINT}"
        ) from exc


def parse_scispacy_response(
    document: Document,
    payload: Iterable[Any] | None,
    *,
    source: str,
) -> list[Annotation]:
    if not payload:
        return []

    annotations: list[Annotation] = []
    for entity in payload:
        span_text = getattr(entity, "text", None)
        label = getattr(entity, "label_", None)
        start = getattr(entity, "start_char", None)
        end = getattr(entity, "end_char", None)
        if not span_text:
            continue
        annotations.append(
            make_annotation(
                document=document,
                source=source,
                span_text=span_text,
                entity_type=label,
                start=start,
                end=end,
            )
        )
    return annotations


def annotate_with_scispacy(
    document: Document,
    *,
    source: str,
    model: str,
    response: Any = None,
    request_fn: Callable[[Document], Any] | None = None,
    nlp: Any = None,
    model_loader: Callable[[str], Any] | None = None,
) -> list[Annotation]:
    payload = response
    if payload is None and request_fn is not None:
        payload = request_fn(document)
    if payload is None:
        if nlp is None:
            loader = model_loader or _load_scispacy_model
            nlp = loader(model)
        payload = getattr(nlp(document.text), "ents", None)
    return parse_scispacy_response(document, payload, source=source)


def annotate_with_scispacy_jnlpba(
    document: Document,
    **kwargs: Any,
) -> list[Annotation]:
    model = kwargs.pop("model", SCISPACY_MODEL_BY_ANNOTATOR["scispacy_jnlpba"])
    return annotate_with_scispacy(
        document,
        source="scispacy_jnlpba",
        model=model,
        **kwargs,
    )


def annotate_with_scispacy_bc5cdr(
    document: Document,
    **kwargs: Any,
) -> list[Annotation]:
    model = kwargs.pop("model", SCISPACY_MODEL_BY_ANNOTATOR["scispacy_bc5cdr"])
    return annotate_with_scispacy(
        document,
        source="scispacy_bc5cdr",
        model=model,
        **kwargs,
    )


def annotate_with_scispacy_bionlp13cg(
    document: Document,
    **kwargs: Any,
) -> list[Annotation]:
    model = kwargs.pop("model", SCISPACY_MODEL_BY_ANNOTATOR["scispacy_bionlp13cg"])
    return annotate_with_scispacy(
        document,
        source="scispacy_bionlp13cg",
        model=model,
        **kwargs,
    )

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

FLAIR_INSTALL_HINT = (
    "The Flair annotator requires the optional Flair dependency. "
    "Install it with: uv sync --extra flair"
)


def _extract_flair_label(span: Any) -> tuple[Any, Any]:
    if hasattr(span, "get_label"):
        label = span.get_label("ner")
        return getattr(label, "value", None), getattr(label, "score", None)

    labels = getattr(span, "labels", None)
    if labels:
        first = labels[0]
        return getattr(first, "value", None), getattr(first, "score", None)

    return getattr(span, "tag", None), getattr(span, "score", None)


def parse_flair_spans(document: Document, spans: Iterable[Any]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for span in spans:
        label, score = _extract_flair_label(span)
        text = getattr(span, "text", None)
        if text is None and hasattr(span, "to_original_text"):
            text = span.to_original_text()
        if not text:
            continue

        annotations.append(
            make_annotation(
                document=document,
                source="flair",
                span_text=text,
                entity_type=label,
                start=getattr(span, "start_position", None),
                end=getattr(span, "end_position", None),
                confidence=score,
            )
        )

    return annotations


@lru_cache(maxsize=4)
def _load_flair_tagger(model: str) -> Any:
    from flair.models import SequenceTagger

    return SequenceTagger.load(model)


def parse_flair_labels(document: Document, labels: Iterable[Any]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for label in labels:
        span = getattr(label, "data_point", None)
        if span is None:
            continue
        text = getattr(span, "text", None)
        if not text:
            continue

        annotations.append(
            make_annotation(
                document=document,
                source="flair",
                span_text=text,
                entity_type=getattr(label, "value", None),
                start=getattr(span, "start_position", None),
                end=getattr(span, "end_position", None),
                confidence=getattr(label, "score", None),
            )
        )

    return annotations


def annotate_with_flair(
    document: Document,
    *,
    spans: Iterable[Any] | None = None,
    tagger: Any = None,
    model: str | None = None,
    tagger_loader: Callable[[str], Any] | None = None,
    sentence_factory: Callable[[str], Any] | None = None,
) -> list[Annotation]:
    if spans is not None:
        return parse_flair_spans(document, spans)

    if tagger is None and model:
        loader = tagger_loader or _load_flair_tagger
        tagger = loader(model)

    if tagger is not None:
        if sentence_factory is None:
            try:
                from flair.data import Sentence
            except ImportError:
                return []
            sentence = Sentence(document.text)
        else:
            sentence = sentence_factory(document.text)

        tagger.predict(sentence)
        if hasattr(sentence, "get_labels"):
            return parse_flair_labels(document, sentence.get_labels())
        if hasattr(sentence, "get_spans"):
            return parse_flair_spans(document, sentence.get_spans("ner"))
        return []

    return []

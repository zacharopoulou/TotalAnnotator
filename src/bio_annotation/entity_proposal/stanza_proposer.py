from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

STANZA_MODELS: tuple[str, ...] = ("bc5cdr", "bionlp13cg", "jnlpba")
DEFAULT_STANZA_PACKAGE = "craft"

STANZA_INSTALL_HINT = (
    "The Stanza annotators require the optional Stanza dependency. "
    "Install it with: uv sync --extra stanza"
)


def stanza_source(model: str) -> str:
    return f"stanza_{model}"


def stanza_model_for_annotator(annotator: str) -> str:
    return annotator[len("stanza_"):]


STANZA_ANNOTATORS: tuple[str, ...] = tuple(stanza_source(model) for model in STANZA_MODELS)


def parse_stanza_entities(
    document: Document,
    entities: Iterable[Any],
    *,
    source: str,
) -> list[Annotation]:
    annotations: list[Annotation] = []
    for entity in entities:
        text = getattr(entity, "text", None)
        if not text:
            continue
        annotations.append(
            make_annotation(
                document=document,
                source=source,
                span_text=text,
                entity_type=getattr(entity, "type", None),
                start=getattr(entity, "start_char", None),
                end=getattr(entity, "end_char", None),
            )
        )
    return annotations


@lru_cache(maxsize=8)
def _load_stanza_pipeline(package: str, model: str) -> Any:
    try:
        import stanza
    except ImportError as exc:
        raise RuntimeError(STANZA_INSTALL_HINT) from exc

    return stanza.Pipeline(
        lang="en",
        package=None,
        processors={"tokenize": package, "ner": model},
        download_method=stanza.DownloadMethod.REUSE_RESOURCES,
        verbose=False,
    )


def annotate_with_stanza(
    document: Document,
    model: str,
    *,
    entities: Iterable[Any] | None = None,
    pipeline: Any = None,
    package: str | None = None,
    pipeline_loader: Callable[[str, str], Any] | None = None,
) -> list[Annotation]:
    source = stanza_source(model)
    if entities is not None:
        return parse_stanza_entities(document, entities, source=source)

    if pipeline is None:
        loader = pipeline_loader or _load_stanza_pipeline
        pipeline = loader(package or DEFAULT_STANZA_PACKAGE, model)

    parsed = pipeline(document.text)
    return parse_stanza_entities(document, getattr(parsed, "ents", []) or [], source=source)

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

# Each runs in its own single-model pipeline and their entities are merged under a single `source="stanza"`
DEFAULT_STANZA_MODELS: tuple[str, ...] = ("bc5cdr", "bionlp13cg", "jnlpba")
DEFAULT_STANZA_PACKAGE = "craft"

STANZA_INSTALL_HINT = (
    "The Stanza annotator requires the optional Stanza dependency. "
    "Install it with: uv sync --extra stanza"
)


def parse_stanza_entities(document: Document, entities: Iterable[Any]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for entity in entities:
        text = getattr(entity, "text", None)
        if not text:
            continue
        annotations.append(
            make_annotation(
                document=document,
                source="stanza",
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
    *,
    entities: Iterable[Any] | None = None,
    pipeline: Any = None,
    package: str | None = None,
    models: Iterable[str] | None = None,
    pipeline_loader: Callable[[str, str], Any] | None = None,
) -> list[Annotation]:
    if entities is not None:
        return parse_stanza_entities(document, entities)

    if pipeline is not None:
        parsed = pipeline(document.text)
        return parse_stanza_entities(document, getattr(parsed, "ents", []) or [])

    loader = pipeline_loader or _load_stanza_pipeline
    selected = tuple(models) if models else DEFAULT_STANZA_MODELS
    resolved_package = package or DEFAULT_STANZA_PACKAGE

    annotations: list[Annotation] = []
    seen: set[str] = set()
    for model in selected:
        parsed = loader(resolved_package, model)(document.text)
        for annotation in parse_stanza_entities(document, getattr(parsed, "ents", []) or []):
            # Models overlap (e.g. PTEN as gene from both bionlp13cg and jnlpba),
            # which collapse to the same annotation_id; keep one.
            if annotation.annotation_id in seen:
                continue
            seen.add(annotation.annotation_id)
            annotations.append(annotation)
    return annotations

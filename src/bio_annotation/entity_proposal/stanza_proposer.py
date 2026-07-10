from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

STANZA_MODELS: tuple[str, ...] = ("bc5cdr", "bionlp13cg", "jnlpba", "i2b2")
DEFAULT_STANZA_PACKAGE = "craft"

# Clinical Stanza models are tokenized with the MIMIC package rather than the
# CRAFT biomedical tokenizer. Models absent here fall back to
# DEFAULT_STANZA_PACKAGE; an explicit config package still overrides both.
STANZA_MODEL_PACKAGES: dict[str, str] = {
    "i2b2": "mimic",
}


def default_package_for_model(model: str) -> str:
    return STANZA_MODEL_PACKAGES.get(model, DEFAULT_STANZA_PACKAGE)

STANZA_INSTALL_HINT = (
    "The Stanza annotators require the optional Stanza dependency. "
    "Install it with: uv sync --extra stanza"
)


def stanza_source(model: str) -> str:
    return f"stanza_{model}"


def stanza_model_for_annotator(annotator: str) -> str:
    return annotator[len("stanza_"):]


STANZA_ANNOTATORS: tuple[str, ...] = tuple(stanza_source(model) for model in STANZA_MODELS)

# Clinical Stanza models (i2b2, radiology) often tag a noun phrase together with
# its leading determiner on out-of-domain text (e.g. "a stop codon", "This
# protein"). Strip the determiner and keep character offsets aligned. Ordered so
# longer determiners match before shorter ones.
_LEADING_DETERMINERS = ("these", "those", "this", "the", "an", "a")
_DETERMINER_WORDS = frozenset(_LEADING_DETERMINERS)


def _strip_leading_determiner(
    text: str, start: int | None, end: int | None
) -> tuple[str, int | None, int | None]:
    lowered = text.lower()
    for determiner in _LEADING_DETERMINERS:
        if lowered.startswith(determiner + " "):
            removed = len(text) - len(text[len(determiner):].lstrip())
            trimmed = text[removed:]
            if isinstance(start, int):
                return trimmed, start + removed, end
            return trimmed, start, end
    return text, start, end


def _is_noise_span(text: str) -> bool:
    """True for out-of-domain junk: a bare determiner or lone punctuation like "-"."""
    core = text.strip("-/ \t")
    if len(core) < 2 or not any(ch.isalnum() for ch in core):
        return True
    return text.strip().lower() in _DETERMINER_WORDS


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
        start = getattr(entity, "start_char", None)
        end = getattr(entity, "end_char", None)
        text, start, end = _strip_leading_determiner(text, start, end)
        if not text or _is_noise_span(text):
            continue
        annotations.append(
            make_annotation(
                document=document,
                source=source,
                span_text=text,
                entity_type=getattr(entity, "type", None),
                start=start,
                end=end,
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
        pipeline = loader(package or default_package_for_model(model), model)

    parsed = pipeline(document.text)
    return parse_stanza_entities(document, getattr(parsed, "ents", []) or [], source=source)

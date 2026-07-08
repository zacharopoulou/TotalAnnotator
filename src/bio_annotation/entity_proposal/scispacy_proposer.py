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
    "scispacy_umls": "en_core_sci_lg",
}
SCISPACY_UMLS_ANNOTATOR = "scispacy_umls"
SCISPACY_UMLS_LINKER = "scispacy_linker"


@lru_cache(maxsize=4)
def _load_scispacy_model(model: str, *, linker_name: str | None = None) -> Any:
    try:
        import scispacy  # noqa: F401
        import scispacy.linking  # noqa: F401
        import spacy
    except ImportError as exc:
        raise RuntimeError(SCISPACY_INSTALL_HINT) from exc

    try:
        nlp = spacy.load(model)
    except OSError as exc:
        raise RuntimeError(
            f"scispaCy model '{model}' is not installed. {SCISPACY_INSTALL_HINT}"
        ) from exc
    if linker_name and SCISPACY_UMLS_LINKER not in nlp.pipe_names:
        nlp.add_pipe(
            SCISPACY_UMLS_LINKER,
            config={"resolve_abbreviations": True, "linker_name": linker_name},
        )
    return nlp


def _entity_kb_ents(entity: Any) -> list[tuple[str, float]]:
    extension = getattr(entity, "_", None)
    candidates = getattr(extension, "kb_ents", None) if extension is not None else None
    return list(candidates or [])


def _linker_canonical_name(linker: Any, cui: str) -> str | None:
    kb = getattr(linker, "kb", None)
    entity_by_cui = getattr(kb, "cui_to_entity", {}) if kb is not None else {}
    linked = entity_by_cui.get(cui) if hasattr(entity_by_cui, "get") else None
    canonical_name = getattr(linked, "canonical_name", None)
    return str(canonical_name).strip() if canonical_name else None


def parse_scispacy_response(
    document: Document,
    payload: Iterable[Any] | None,
    *,
    source: str,
    linker: Any = None,
) -> list[Annotation]:
    if not payload:
        return []

    annotations: list[Annotation] = []
    for entity in payload:
        span_text = getattr(entity, "text", None)
        label = getattr(entity, "label_", None)
        start = getattr(entity, "start_char", None)
        end = getattr(entity, "end_char", None)
        canonical_id = None
        canonical_name = None
        confidence = None
        if source == SCISPACY_UMLS_ANNOTATOR:
            candidates = _entity_kb_ents(entity)
            if candidates:
                canonical_id, confidence = candidates[0]
                canonical_name = _linker_canonical_name(linker, str(canonical_id))
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
                canonical_id=canonical_id,
                canonical_name=canonical_name,
                confidence=confidence,
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
    linker_name: str | None = None,
) -> list[Annotation]:
    payload = response
    if payload is None and request_fn is not None:
        payload = request_fn(document)
    if payload is None:
        if nlp is None:
            loader = model_loader or _load_scispacy_model
            if source == SCISPACY_UMLS_ANNOTATOR:
                nlp = loader(model, linker_name=linker_name or "umls")
            else:
                nlp = loader(model)
        parsed = nlp(document.text)
        payload = getattr(parsed, "ents", None)
    linker = None
    if source == SCISPACY_UMLS_ANNOTATOR and nlp is not None:
        try:
            linker = nlp.get_pipe(SCISPACY_UMLS_LINKER)
        except (KeyError, AttributeError):
            linker = None
    return parse_scispacy_response(document, payload, source=source, linker=linker)


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


def annotate_with_scispacy_umls(
    document: Document,
    **kwargs: Any,
) -> list[Annotation]:
    model = kwargs.pop("model", SCISPACY_MODEL_BY_ANNOTATOR[SCISPACY_UMLS_ANNOTATOR])
    return annotate_with_scispacy(
        document,
        source=SCISPACY_UMLS_ANNOTATOR,
        model=model,
        linker_name=kwargs.pop("linker_name", "umls"),
        **kwargs,
    )

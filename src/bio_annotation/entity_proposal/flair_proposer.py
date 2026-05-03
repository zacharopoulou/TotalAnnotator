from __future__ import annotations

import math
from typing import Any, Callable, Iterable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation


def _is_out_tag(value: Any) -> bool:
    if value is None:
        return True
    upper = str(value).strip().upper()
    return upper in {"", "O", "OUT", "-"}


def _extract_flair_label(span: Any) -> tuple[Any, Any]:
    """Resolve type/score for a Flair Span (HunFlair2 layers are not always ``ner``)."""

    if hasattr(span, "get_labels"):
        for lbl in span.get_labels() or []:
            val = getattr(lbl, "value", None)
            if not _is_out_tag(val):
                return val, getattr(lbl, "score", None)
    if hasattr(span, "get_label"):
        label = span.get_label()
        val = getattr(label, "value", None)
        if not _is_out_tag(val):
            return val, getattr(label, "score", None)

    labels = getattr(span, "labels", None)
    if labels:
        first = labels[0]
        return getattr(first, "value", None), getattr(first, "score", None)

    return getattr(span, "tag", None), getattr(span, "score", None)


def parse_flair_spans(document: Document, spans: Iterable[Any]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for span in spans:
        label, score = _extract_flair_label(span)
        if _is_out_tag(label):
            continue
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


def parse_flair_labels(document: Document, labels: Iterable[Any]) -> list[Annotation]:
    """For ``Classifier``-style models (e.g. HunFlair2) that attach labels via ``sentence.get_labels()``."""

    annotations: list[Annotation] = []
    for label in labels:
        if _is_out_tag(getattr(label, "value", None)):
            continue
        span = getattr(label, "data_point", None)
        if span is None:
            continue
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
                entity_type=getattr(label, "value", None),
                start=getattr(span, "start_position", None),
                end=getattr(span, "end_position", None),
                confidence=getattr(label, "score", None),
            )
        )
    return annotations


def parse_flair_to_dict_annotations(document: Document, sentence: Any) -> list[Annotation]:
    """Flair ≥0.14 stores structured NER under ``sentence.to_dict()['annotations']['spans']``."""

    if not hasattr(sentence, "to_dict"):
        return []
    data = sentence.to_dict()
    out: list[Annotation] = []

    ann = data.get("annotations") if isinstance(data.get("annotations"), dict) else {}
    spans = ann.get("spans") if isinstance(ann.get("spans"), dict) else {}
    for span_info in spans.values():
        if not isinstance(span_info, dict):
            continue
        text = str(span_info.get("text") or "").strip()
        if not text:
            continue
        start = span_info.get("start_char")
        end = span_info.get("end_char")
        lbls = span_info.get("labels") or []
        etype: Any = None
        conf: Any = None
        if lbls and isinstance(lbls[0], dict):
            etype = lbls[0].get("value")
            conf = lbls[0].get("score")
        # Offsets are relative to this Sentence; single-chunk text matches document slice.
        base = getattr(sentence, "start_position", 0) or 0
        try:
            s_i = int(start) + base if start is not None else None
            e_i = int(end) + base if end is not None else None
        except (TypeError, ValueError):
            s_i = e_i = None
        out.append(
            make_annotation(
                document=document,
                source="flair",
                span_text=text,
                entity_type=etype,
                start=s_i,
                end=e_i,
                confidence=conf,
            )
        )

    # Older docs / helpers used a flat ``entities`` list.
    for ent in data.get("entities") or []:
        if not isinstance(ent, dict):
            continue
        text = str(ent.get("text") or "").strip()
        if not text:
            continue
        start = ent.get("start_pos", ent.get("start_position"))
        end = ent.get("end_pos", ent.get("end_position"))
        lbls = ent.get("labels") or []
        etype = conf = None
        if lbls and isinstance(lbls[0], dict):
            etype = lbls[0].get("value")
            conf = lbls[0].get("confidence", lbls[0].get("score"))
        try:
            s_i = int(start) if start is not None else None
            e_i = int(end) if end is not None else None
        except (TypeError, ValueError):
            s_i = e_i = None
        out.append(
            make_annotation(
                document=document,
                source="flair",
                span_text=text,
                entity_type=etype,
                start=s_i,
                end=e_i,
                confidence=conf,
            )
        )

    return out


def _json_safe(obj: Any) -> Any:
    """Convert Flair / numpy-ish values to JSON-serializable structures."""

    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return _json_safe(obj.item())
        except Exception:
            pass
    return str(obj)


def flair_sentence_to_jsonable(sentence: Any) -> dict[str, Any]:
    """Snapshot of a Flair ``Sentence`` after ``tagger.predict`` (for ``flair_raw`` exports)."""

    if hasattr(sentence, "to_dict"):
        raw = sentence.to_dict()
        if isinstance(raw, dict):
            return _json_safe(raw)
    text = getattr(sentence, "text", None)
    if text is None and hasattr(sentence, "to_plain_string"):
        try:
            text = sentence.to_plain_string()
        except Exception:
            text = None
    return _json_safe({"text": text or "", "note": "sentence.to_dict unavailable"})


def collect_flair_annotations_from_sentence(document: Document, sentence: Any) -> list[Annotation]:
    """Turn a predicted Flair ``Sentence`` into unified annotations (single predict pass)."""

    # HunFlair2 matches TotalAnnotator-hunflair2: entities surface via sentence.get_labels().
    for labels_fn in (
        lambda: list(sentence.get_labels()),
        lambda: list(sentence.get_labels("ner")),
    ):
        parsed = parse_flair_labels(document, labels_fn())
        if parsed:
            return parsed

    for span_fn in (
        lambda: sentence.get_spans("ner"),
        sentence.get_spans,
    ):
        group = span_fn()
        if not group:
            continue
        parsed = parse_flair_spans(document, group)
        if parsed:
            return parsed

    parsed = parse_flair_to_dict_annotations(document, sentence)
    return parsed if parsed else []


def run_flair_on_document(
    document: Document,
    *,
    tagger: Any,
    sentence_factory: Callable[[str], Any] | None = None,
    include_raw: bool = False,
) -> tuple[list[Annotation], dict[str, Any] | None]:
    """Run a loaded Flair tagger once per document; optionally return a JSON-safe sentence snapshot."""

    body = (document.text or "").strip()
    if not body:
        return [], ({"skipped": "empty_document_text"} if include_raw else None)

    if sentence_factory is None:
        try:
            from flair.data import Sentence
        except ImportError:
            return [], ({"skipped": "flair_not_installed"} if include_raw else None)
        sentence = Sentence(body)
    else:
        sentence = sentence_factory(body)

    tagger.predict(sentence)
    annotations = collect_flair_annotations_from_sentence(document, sentence)
    raw = flair_sentence_to_jsonable(sentence) if include_raw else None
    return annotations, raw


def annotate_with_flair(
    document: Document,
    *,
    spans: Iterable[Any] | None = None,
    tagger: Any = None,
    sentence_factory: Callable[[str], Any] | None = None,
) -> list[Annotation]:
    predictions = spans

    if predictions is None and tagger is not None:
        ann, _ = run_flair_on_document(
            document,
            tagger=tagger,
            sentence_factory=sentence_factory,
            include_raw=False,
        )
        return ann

    if predictions is None:
        return []

    return parse_flair_spans(document, predictions)

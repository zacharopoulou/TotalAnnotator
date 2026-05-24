from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from typing import Any

_SOURCE_PRIORITY: dict[str, int] = {"pubtator3": 0, "bern2": 1, "flair": 2}


def _source_priority(source: str | None) -> int:
    """Lower means preferred. PubTator3 wins because it has canonical names."""
    return _SOURCE_PRIORITY.get(source or "", 99)


def build_canonical_text(document: dict[str, Any]) -> str:
    """Return title + newline + abstract, matching PubTator3's offset scheme."""
    title = document.get("title") or ""
    abstract = document.get("abstract") or ""
    if title and abstract:
        return f"{title}\n{abstract}"
    return title or abstract


def render_highlighted_text(
    text: str,
    annotations: list[dict[str, Any]],
    cross_annotator_lookup: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
) -> str:
    """Render text with non-overlapping mark spans for each annotation.

    Annotations are sorted by start position, and overlapping spans are
    resolved by keeping the earliest, longest one. Each surviving annotation
    becomes a <mark class="entity entity-<type>"> element. The title attribute
    contains the entity type, canonical name, canonical id, and (if
    cross_annotator_lookup is provided) the list of annotators that found the
    same surface text in this document.

    cross_annotator_lookup is keyed by casefolded span text. Values are dicts
    mapping annotator name to a list of hit records (the same shape produced
    by group_annotations_by_span).
    """
    if not annotations:
        return escape(text).replace("\n", "<br>\n")

    sorted_annotations = sorted(
        annotations,
        key=lambda a: (
            a.get("start") or 0,
            _source_priority(a.get("source")),
            -((a.get("end") or 0) - (a.get("start") or 0)),
        ),
    )

    chosen: list[dict[str, Any]] = []
    last_end = -1
    for annotation in sorted_annotations:
        start = annotation.get("start")
        end = annotation.get("end")
        if start is None or end is None or end <= start:
            continue
        if start >= last_end:
            chosen.append(annotation)
            last_end = end

    out: list[str] = []
    position = 0
    for annotation in chosen:
        start = annotation["start"]
        end = annotation["end"]
        if start > position:
            out.append(escape(text[position:start]).replace("\n", "<br>\n"))
        rendered_span = escape(text[start:end])
        entity_type = (annotation.get("entity_type") or "unknown").lower()
        source = annotation.get("source") or "unknown"
        canonical_id = annotation.get("canonical_id") or ""
        canonical_name = annotation.get("canonical_name") or ""
        keyword_key = (annotation.get("span_text") or text[start:end]).strip().casefold()
        cross_hit = cross_annotator_lookup.get(keyword_key) if cross_annotator_lookup else None

        tooltip_parts = [f"Type: {entity_type}"]
        if canonical_name:
            tooltip_parts.append(f"Name: {canonical_name}")
        if canonical_id:
            tooltip_parts.append(f"ID: {canonical_id}")
        if cross_hit:
            sources_found = sorted(cross_hit.keys())
            tooltip_parts.append("Found by: " + ", ".join(sources_found))
        else:
            tooltip_parts.append(f"Source: {source}")
        tooltip = escape(" | ".join(tooltip_parts))

        popup_payload: dict[str, Any] = {
            "keyword": text[start:end],
            "entity_type": entity_type,
            "canonical_id": canonical_id or None,
            "canonical_name": canonical_name or None,
            "primary_source": source,
            "by_source": cross_hit or {source: [annotation]},
        }
        data_attribute = escape(json.dumps(popup_payload, default=str), quote=True)

        out.append(
            f'<mark class="entity entity-{escape(entity_type)}" title="{tooltip}" '
            f'data-entity="{data_attribute}" tabindex="0" role="button">{rendered_span}</mark>'
        )
        position = end
    if position < len(text):
        out.append(escape(text[position:]).replace("\n", "<br>\n"))
    return "".join(out)


def group_annotations_by_span(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group annotations across annotators by case-insensitive span text.

    Returns rows for a comparison table. Each row has the keyword and a
    dict of annotator -> list of (entity_type, canonical_id, canonical_name).
    """
    groups: dict[str, dict[str, Any]] = {}
    for annotation in annotations:
        span_text = (annotation.get("span_text") or "").strip()
        if not span_text:
            continue
        key = span_text.casefold()
        bucket = groups.setdefault(
            key,
            {
                "keyword": span_text,
                "by_source": defaultdict(list),
                "first_offset": annotation.get("start") or 0,
            },
        )
        source = annotation.get("source") or "unknown"
        bucket["by_source"][source].append(
            {
                "entity_type": annotation.get("entity_type"),
                "canonical_id": annotation.get("canonical_id"),
                "canonical_name": annotation.get("canonical_name"),
                "start": annotation.get("start"),
                "end": annotation.get("end"),
                "confidence": annotation.get("confidence"),
            }
        )
        if (annotation.get("start") or 0) < bucket["first_offset"]:
            bucket["first_offset"] = annotation.get("start") or 0

    rows = []
    for bucket in groups.values():
        by_source = dict(bucket["by_source"])
        rows.append(
            {
                "keyword": bucket["keyword"],
                "by_source": by_source,
                "annotator_count": len(by_source),
                "first_offset": bucket["first_offset"],
            }
        )
    rows.sort(key=lambda row: (row["first_offset"], row["keyword"].casefold()))
    return rows

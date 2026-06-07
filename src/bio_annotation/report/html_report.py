from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

_TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"

# Trust ranking for picking ONE annotator when several tag the same span.
# Lower number = more trusted. The most-trusted annotator's annotation
# wins the visible highlight and supplies the popup's primary canonical
# id/name. The other annotators' results are still listed in "Found by".
# PubTator3 is best at normalisation, BERN2 second, Flair last (no IDs).
_SOURCE_PRIORITY: dict[str, int] = {"pubtator3": 0, "bern2": 1, "flair": 2}

_ANNOTATOR_LABELS: dict[str, str] = {
    "pubtator3": "PubTator3",
    "bern2": "BERN2",
    "flair": "Flair / HunFlair",
}

_ENTITY_TYPE_LABELS: dict[str, str] = {
    "gene": "Gene / protein",
    "disease": "Disease",
    "drug": "Chemical / drug",
    "species": "Species",
    "variant": "Variant / mutation",
    "cell_line": "Cell line",
    # BERN2-only categories that don't have a canonical equivalent on the
    # other annotators. Kept as their own buckets rather than merged.
    "dna": "DNA segment",
    "rna": "RNA / miRNA",
    "cell_type": "Cell type",
}


# Per-annotator placeholders that look like an ID but actually mean
# "no normalized concept found". Treat them as empty.
_NULL_CANONICAL_IDS: frozenset[str] = frozenset({"cui-less", "-", ""})


def _is_real_canonical_id(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return text not in _NULL_CANONICAL_IDS


# Mirror of the JS `databaseLink` so the comparison table can hyperlink IDs
# server-side. Keep the prefix list in sync with the script in template.html.
def _database_link(canonical_id: str | None, entity_type: str | None) -> str | None:
    if not canonical_id:
        return None
    raw = str(canonical_id).strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered.startswith("mesh:"):
        return f"https://meshb.nlm.nih.gov/record/ui?ui={raw.split(':', 1)[1]}"
    if lowered.startswith("ncbigene:") or lowered.startswith("ncbi_gene:") or lowered.startswith("ncbi-gene:"):
        return f"https://www.ncbi.nlm.nih.gov/gene/{raw.split(':', 1)[1]}"
    if (
        lowered.startswith("ncbitaxon:") or lowered.startswith("ncbitaxonomy:")
        or lowered.startswith("ncbi_taxonomy:") or lowered.startswith("ncbi-taxonomy:")
        or lowered.startswith("taxonomy:") or lowered.startswith("taxon:")
    ):
        return f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={raw.split(':', 1)[1]}"
    if lowered.startswith("dbsnp:") or lowered.startswith("rs:"):
        return f"https://www.ncbi.nlm.nih.gov/snp/{raw.split(':', 1)[1]}"
    if lowered.startswith("chebi:"):
        return f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:{raw.split(':', 1)[1]}"
    if lowered.startswith("drugbank:"):
        return f"https://go.drugbank.com/drugs/{raw.split(':', 1)[1]}"
    if lowered.startswith("cvcl:") or lowered.startswith("cellosaurus:"):
        suffix = raw.split(":", 1)[1]
        ref = suffix if suffix.startswith("CVCL_") else f"CVCL_{suffix}"
        return f"https://www.cellosaurus.org/{ref}"
    if lowered.startswith("omim:") or lowered.startswith("mim:"):
        return f"https://www.omim.org/entry/{raw.split(':', 1)[1]}"
    if entity_type == "species" and raw.isdigit():
        return f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={raw}"
    # OBO ontologies: Cell Ontology, Gene Ontology, Disease Ontology, etc.
    # Resolve via the canonical PURL which redirects to the OLS landing page.
    for obo_prefix in ("cl", "go", "doid", "uberon", "bto", "fma", "pato"):
        if lowered.startswith(obo_prefix + ":"):
            term = raw.split(":", 1)[1]
            return f"http://purl.obolibrary.org/obo/{obo_prefix.upper()}_{term}"
    return None


def write_html_report(payload: dict[str, Any], output_path: Path) -> Path:
    """Generate a standalone HTML report next to the run's other outputs.

    Returns the absolute path of the file that was written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content_html = _render_body(payload)
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("<!--CONTENT-->", content_html)
    output_path.write_text(html, encoding="utf-8")
    return output_path.resolve()


def _render_body(payload: dict[str, Any]) -> str:
    summary = payload.get("annotation_summary") or {}
    documents = list(payload.get("documents") or [])
    annotations = list(payload.get("annotations") or [])

    annotators_used = sorted(
        {a.get("source") for a in annotations if a.get("source")}
    )
    annotators_text = ", ".join(
        _ANNOTATOR_LABELS.get(name, name) for name in annotators_used
    ) or "none"
    total_annotations = summary.get("annotation_count", len(annotations))
    document_count = payload.get("document_count", len(documents))

    parts: list[str] = []
    parts.append('<section class="summary">')
    parts.append('<div class="summary-headline">')
    parts.append(
        f'<p class="lede"><span class="big-number">{total_annotations}</span> '
        f'annotation{"s" if total_annotations != 1 else ""} across '
        f'<span class="big-number">{document_count}</span> '
        f'document{"s" if document_count != 1 else ""}</p>'
    )
    parts.append(f'<p class="meta">Annotators: {escape(annotators_text)}</p>')
    parts.append("</div>")
    if annotations:
        parts.append(_render_stats_panel(
            _compute_stats(annotations),
            heading="Bioconcepts in this run",
            css_class="stats-run",
        ))
    parts.append("</section>")
    parts.append(_render_legend(annotations))

    if annotations:
        parts.append(_render_type_histogram(annotations))
    if len(documents) > 1:
        parts.append(_render_documents_overview(documents, annotations))

    for document in documents:
        parts.append(_render_document(document, annotations))

    if not documents:
        parts.append('<p class="hint">No documents in this run.</p>')

    return "\n".join(parts)


def _compute_stats(annotations: list[dict[str, Any]]) -> dict[str, list[tuple[str, int]]]:
    """Group annotations by entity type, then by case-insensitive span text.

    The count is the number of distinct text positions, not the number of
    annotation rows. Multiple annotators tagging the same span at the same
    offset count as one mention, matching PubTator3's "Bioconcepts and
    mentions" panel.
    """
    positions: dict[str, dict[str, set[tuple[Any, Any]]]] = {}
    canonical: dict[str, dict[str, str]] = {}
    for annotation in annotations:
        span_text = (annotation.get("span_text") or "").strip()
        if not span_text:
            continue
        entity_type = (annotation.get("entity_type") or "unknown").lower()
        key = span_text.casefold()
        positions.setdefault(entity_type, {}).setdefault(key, set()).add(
            (annotation.get("start"), annotation.get("end"))
        )
        canonical.setdefault(entity_type, {}).setdefault(key, span_text)

    result: dict[str, list[tuple[str, int]]] = {}
    for entity_type, by_key in positions.items():
        rows = [
            (canonical[entity_type][key], len(positions_set))
            for key, positions_set in by_key.items()
        ]
        rows.sort(key=lambda item: (-item[1], item[0].casefold()))
        result[entity_type] = rows
    return result


def _render_stats_panel(
    stats: dict[str, list[tuple[str, int]]],
    *,
    heading: str,
    css_class: str,
    limit_per_type: int = 15,
) -> str:
    if not stats:
        return ""
    type_order = [
        key for key in ("disease", "drug", "gene", "species", "variant", "cell_line")
        if key in stats
    ]
    type_order += [key for key in stats if key not in type_order]

    parts: list[str] = [f'<aside class="stats-panel {css_class}">']
    parts.append(f'<h4>{escape(heading)}</h4>')
    for entity_type in type_order:
        rows = stats[entity_type]
        if not rows:
            continue
        label = _ENTITY_TYPE_LABELS.get(entity_type, entity_type)
        total = sum(count for _, count in rows)
        parts.append(
            f'<details class="stats-group stats-group-{escape(entity_type)}">'
            f'<summary><span class="stats-type">{escape(label)}</span>'
            f'<span class="stats-type-total">{total}</span></summary>'
        )
        parts.append('<ul class="stats-list">')
        max_count = rows[0][1] if rows else 1
        for keyword, count in rows[:limit_per_type]:
            width_pct = max(6, int(round(100 * count / max_count))) if max_count else 0
            parts.append(
                f'<li>'
                f'<span class="stats-keyword">{escape(keyword)}</span>'
                f'<span class="stats-bar-track"><span class="stats-bar-fill" style="width:{width_pct}%"></span></span>'
                f'<span class="stats-count">{count}</span>'
                f'</li>'
            )
        if len(rows) > limit_per_type:
            remaining = len(rows) - limit_per_type
            parts.append(f'<li class="stats-more">+{remaining} more</li>')
        parts.append("</ul></details>")
    parts.append("</aside>")
    return "\n".join(parts)


def _render_type_histogram(annotations: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for annotation in annotations:
        entity_type = (annotation.get("entity_type") or "unknown").lower()
        counts[entity_type] = counts.get(entity_type, 0) + 1
    if not counts:
        return ""
    ordered = [
        key for key in ("disease", "drug", "gene", "species", "variant", "cell_line")
        if key in counts
    ]
    ordered += sorted(key for key in counts if key not in ordered)
    max_count = max(counts.values())

    parts = ['<section class="chart-card">',
             '<h4>Entity type distribution</h4>',
             '<ul class="type-histogram">']
    for entity_type in ordered:
        count = counts[entity_type]
        label = _ENTITY_TYPE_LABELS.get(entity_type, entity_type.replace("_", " ").title())
        width = max(4, int(round(100 * count / max_count)))
        parts.append(
            f'<li class="hist-row hist-row-{escape(entity_type)}">'
            f'<span class="hist-label">{escape(label)}</span>'
            f'<span class="hist-track"><span class="hist-fill" style="width:{width}%"></span></span>'
            f'<span class="hist-count">{count}</span>'
            f'</li>'
        )
    parts.append('</ul></section>')
    return "\n".join(parts)


def _render_documents_overview(
    documents: list[dict[str, Any]], annotations: list[dict[str, Any]]
) -> str:
    by_doc: dict[Any, dict[str, int]] = {}
    for annotation in annotations:
        document_id = annotation.get("document_id")
        entity_type = (annotation.get("entity_type") or "unknown").lower()
        by_doc.setdefault(document_id, {})[entity_type] = (
            by_doc.setdefault(document_id, {}).get(entity_type, 0) + 1
        )

    doc_totals = [
        (doc, sum(by_doc.get(doc.get("document_id"), {}).values()))
        for doc in documents
    ]
    max_total = max((total for _, total in doc_totals), default=0)
    if max_total == 0:
        return ""

    type_order = ("disease", "drug", "gene", "species", "variant", "cell_line")

    parts = ['<section class="chart-card">',
             '<h4>Annotations per document</h4>',
             '<ul class="doc-overview">']
    for document, total in doc_totals:
        doc_id = str(document.get("document_id") or "")
        pmid = document.get("pmid")
        title = (document.get("title") or doc_id or "Document")
        truncated = title if len(title) <= 70 else title[:67] + "..."
        link_text = f"PMID {pmid}" if pmid else doc_id or "Document"
        anchor = _anchor_for(doc_id)
        type_counts = by_doc.get(document.get("document_id"), {})
        ordered_types = [t for t in type_order if t in type_counts]
        ordered_types += [t for t in type_counts if t not in ordered_types]

        segments: list[str] = []
        running_total = sum(type_counts.values())
        for entity_type in ordered_types:
            seg_count = type_counts[entity_type]
            seg_width = 100 * seg_count / running_total if running_total else 0
            segments.append(
                f'<span class="doc-seg doc-seg-{escape(entity_type)}" '
                f'style="width:{seg_width:.2f}%" '
                f'title="{escape(_ENTITY_TYPE_LABELS.get(entity_type, entity_type))}: {seg_count}"></span>'
            )
        bar_width = max(8, int(round(100 * total / max_total)))
        parts.append(
            f'<li class="doc-row">'
            f'<a class="doc-link" href="#{escape(anchor, quote=True)}">{escape(link_text)}</a>'
            f'<span class="doc-title">{escape(truncated)}</span>'
            f'<span class="doc-track"><span class="doc-bar" style="width:{bar_width}%">{"".join(segments)}</span></span>'
            f'<span class="doc-count">{total}</span>'
            f'</li>'
        )
    parts.append('</ul></section>')
    return "\n".join(parts)


def _anchor_for(document_id: str) -> str:
    return "doc-" + "".join(ch if ch.isalnum() else "-" for ch in document_id).strip("-").lower()


def _render_legend(annotations: list[dict[str, Any]] | None = None) -> str:
    """Render legend chips. If annotations are passed, only show the types
    actually present in this run; otherwise show every known type."""
    if annotations is not None:
        present = {
            (a.get("entity_type") or "unknown").lower()
            for a in annotations
        }
        items = [
            f'<span class="legend-chip legend-chip-{key}">{escape(label)}</span>'
            for key, label in _ENTITY_TYPE_LABELS.items()
            if key in present
        ]
    else:
        items = [
            f'<span class="legend-chip legend-chip-{key}">{escape(label)}</span>'
            for key, label in _ENTITY_TYPE_LABELS.items()
        ]
    items.append('<span class="legend-chip legend-chip-unmatched">No canonical id</span>')
    return '<div class="legend">' + "".join(items) + "</div>"


def _render_document(document: dict[str, Any], all_annotations: list[dict[str, Any]]) -> str:
    document_id = document.get("document_id")
    document_annotations = [
        annotation for annotation in all_annotations
        if annotation.get("document_id") == document_id
    ]
    comparison_rows = group_annotations_by_span(document_annotations)
    cross_lookup = {row["keyword"].casefold(): row["by_source"] for row in comparison_rows}

    title_text = (document.get("title") or "").strip()
    abstract_text = (document.get("abstract") or "").strip()
    title_annotations, abstract_annotations = _split_annotations_by_region(
        document_annotations, len(title_text)
    )

    title_html = (
        render_highlighted_text(title_text, title_annotations, cross_lookup)
        if title_text
        else escape(str(document_id or "Document"))
    )
    pmid = document.get("pmid")
    pmid_html = (
        f' | PMID: <a href="https://pubmed.ncbi.nlm.nih.gov/{escape(str(pmid))}/" target="_blank" rel="noopener">{escape(str(pmid))}</a>'
        if pmid else ""
    )

    anchor = _anchor_for(str(document_id or ""))
    parts: list[str] = [f'<article class="document" id="{escape(anchor, quote=True)}">']
    parts.append(f"<h2>{title_html}</h2>")
    parts.append(
        f'<p class="meta">{pmid_html}'
        f"{' | ' if pmid else ''}{len(document_annotations)} annotation"
        f"{'s' if len(document_annotations) != 1 else ''} on this document</p>"
    )
    parts.append('<div class="doc-grid">')
    parts.append('<div class="doc-main">')
    parts.append("<h3>Abstract</h3>")
    parts.append('<p class="hint">Highlights show entities found by any annotator. Click a highlight for full details across annotators.</p>')
    body_html = (
        render_highlighted_text(abstract_text, abstract_annotations, cross_lookup)
        if abstract_text
        else '<span class="hint">No abstract available.</span>'
    )
    parts.append(f'<div class="annotated-text">{body_html}</div>')
    parts.append("</div>")
    parts.append(_render_stats_panel(
        _compute_stats(document_annotations),
        heading="Bioconcepts in this document",
        css_class="stats-doc",
    ))
    parts.append("</div>")

    parts.append(
        f'<details class="comparison-section">'
        f'<summary><h3>Comparison across annotators</h3>'
        f'<span class="hint">{len(comparison_rows)} unique keyword'
        f'{"s" if len(comparison_rows) != 1 else ""} found by at least one annotator</span></summary>'
    )
    parts.append('<div class="comparison-scroll">')
    parts.append(_render_comparison_table(comparison_rows))
    parts.append("</div></details>")
    parts.append("</article>")
    return "\n".join(parts)


def _split_annotations_by_region(
    annotations: list[dict[str, Any]], title_length: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition canonical-scheme annotations into title-region and abstract-region.

    Canonical text is `title + "\\n" + abstract`. Annotations with offsets
    fully inside [0, title_length) belong to the title. Annotations starting
    at or past `title_length + 1` belong to the abstract; their offsets are
    rebased so position 0 maps to the start of the abstract.
    """
    title_annotations: list[dict[str, Any]] = []
    abstract_annotations: list[dict[str, Any]] = []
    body_offset = title_length + 1
    for annotation in annotations:
        start = annotation.get("start")
        end = annotation.get("end")
        if start is None or end is None:
            continue
        if title_length and end <= title_length:
            title_annotations.append(annotation)
        elif start >= body_offset:
            abstract_annotations.append(
                {**annotation, "start": start - body_offset, "end": end - body_offset}
            )
    return title_annotations, abstract_annotations


def _render_comparison_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="hint">No annotations to compare.</p>'

    sources = ("pubtator3", "bern2", "flair")
    head_cells = "".join(
        f"<th>{escape(_ANNOTATOR_LABELS.get(source, source))}</th>" for source in sources
    )
    body_rows: list[str] = []
    for row in rows:
        cells = [f'<td><code>{escape(row["keyword"])}</code></td>']
        for source in sources:
            hits = row["by_source"].get(source) or []
            cells.append(f"<td>{_render_hits_cell(hits)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return (
        '<table class="comparison"><thead><tr>'
        f"<th>Keyword</th>{head_cells}"
        "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table>"
    )


def _render_hits_cell(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return '<span class="absent">·</span>'
    lines: list[str] = []
    for hit in hits:
        entity_type = (hit.get("entity_type") or "").lower() or "unknown"
        label = _ENTITY_TYPE_LABELS.get(entity_type, entity_type)
        canonical_id = hit.get("canonical_id") if _is_real_canonical_id(hit.get("canonical_id")) else None
        canonical_name = hit.get("canonical_name")
        mentions = hit.get("mentions")
        line = f'<div class="entity-type">{escape(str(label))}</div>'
        if canonical_id:
            link = _database_link(canonical_id, entity_type)
            code = f'<code>{escape(str(canonical_id))}</code>'
            if link:
                code = f'<a href="{escape(link, quote=True)}" target="_blank" rel="noopener">{code}</a>'
            line += f"<div>{code}</div>"
        if canonical_name:
            line += f"<div><small>{escape(str(canonical_name))}</small></div>"
        if mentions and mentions > 1:
            line += f'<div><small>{mentions} mentions</small></div>'
        lines.append(line)
    return "<br>".join(lines)


def build_canonical_text(document: dict[str, Any]) -> str:
    """Return title + newline + abstract, matching PubTator3's offset scheme."""
    title = document.get("title") or ""
    abstract = document.get("abstract") or ""
    if title and abstract:
        return f"{title}\n{abstract}"
    return title or abstract


def _source_priority(source: str | None) -> int:
    return _SOURCE_PRIORITY.get(source or "", 99)


def render_highlighted_text(
    text: str,
    annotations: list[dict[str, Any]],
    cross_annotator_lookup: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
) -> str:
    """Render the document text with non-overlapping <mark> spans.

    Overlapping annotations are resolved by keeping the earliest, longest
    one. PubTator3 wins ties because it has canonical names. Each surviving
    annotation becomes a `<mark>` carrying a JSON payload in `data-entity`
    that the popup script reads.
    """
    if not annotations:
        return escape(text).replace("\n", "<br>\n")

    # A position is "matched" if any annotation at the same (start, end)
    # carries a canonical_id. The chosen annotation may not be the one that
    # had the ID (overlap resolution can pick a higher-priority source that
    # is missing the normalization), so we check sibling annotations too.
    matched_positions: set[tuple[Any, Any]] = {
        (a.get("start"), a.get("end"))
        for a in annotations
        if _is_real_canonical_id(a.get("canonical_id"))
    }

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
        raw_canonical_id = annotation.get("canonical_id")
        canonical_id = raw_canonical_id if _is_real_canonical_id(raw_canonical_id) else ""
        canonical_name = annotation.get("canonical_name") or ""
        keyword_key = (annotation.get("span_text") or text[start:end]).strip().casefold()
        cross_hit = cross_annotator_lookup.get(keyword_key) if cross_annotator_lookup else None

        popup_payload: dict[str, Any] = {
            "keyword": text[start:end],
            "entity_type": entity_type,
            "canonical_id": canonical_id or None,
            "canonical_name": canonical_name or None,
            "primary_source": source,
            "by_source": cross_hit or {source: [_hit_record(annotation)]},
        }
        data_attribute = escape(json.dumps(popup_payload, default=str), quote=True)

        css_type = entity_type if (start, end) in matched_positions else "unmatched"
        out.append(
            f'<mark class="entity entity-{escape(css_type)}" '
            f'data-entity="{data_attribute}" tabindex="0" role="button">{rendered_span}</mark>'
        )
        position = end
    if position < len(text):
        out.append(escape(text[position:]).replace("\n", "<br>\n"))
    return "".join(out)


def group_annotations_by_span(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group annotations across annotators by case-insensitive span text.

    Each row carries the keyword and a dict of annotator -> list of hits.
    Within each source, hits with identical (entity_type, canonical_id,
    canonical_name) collapse to one row with a `mentions` count.
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
        bucket["by_source"][source].append(_hit_record(annotation))
        if (annotation.get("start") or 0) < bucket["first_offset"]:
            bucket["first_offset"] = annotation.get("start") or 0

    rows: list[dict[str, Any]] = []
    for bucket in groups.values():
        by_source = {source: _dedupe_hits(hits) for source, hits in bucket["by_source"].items()}
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


def _hit_record(annotation: dict[str, Any]) -> dict[str, Any]:
    canonical_id = annotation.get("canonical_id")
    return {
        "entity_type": annotation.get("entity_type"),
        "canonical_id": canonical_id if _is_real_canonical_id(canonical_id) else None,
        "canonical_name": annotation.get("canonical_name"),
        "start": annotation.get("start"),
        "end": annotation.get("end"),
        "confidence": annotation.get("confidence"),
    }


def _dedupe_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse hits with identical (entity_type, canonical_id, canonical_name).

    Keeps the highest confidence and tracks how many mentions collapsed.
    """
    deduped: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    for hit in hits:
        key = (hit.get("entity_type"), hit.get("canonical_id"), hit.get("canonical_name"))
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = {**hit, "mentions": 1}
            continue
        existing["mentions"] += 1
        new_conf = hit.get("confidence")
        old_conf = existing.get("confidence")
        if isinstance(new_conf, (int, float)) and (
            not isinstance(old_conf, (int, float)) or new_conf > old_conf
        ):
            existing["confidence"] = new_conf
    return list(deduped.values())

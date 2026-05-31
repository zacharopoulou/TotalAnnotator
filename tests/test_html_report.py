from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bio_annotation.report.html_report import (
    build_canonical_text,
    group_annotations_by_span,
    render_highlighted_text,
    write_html_report,
)


def sample_payload() -> dict:
    return {
        "document_count": 1,
        "annotation_summary": {"annotation_count": 3, "keyword_count": 2},
        "documents": [
            {
                "document_id": "PMID:1",
                "pmid": "1",
                "title": "PTEN regulates glioblastoma",
                "abstract": "PTEN and miR-21 in glioblastoma cells.",
            }
        ],
        "annotations": [
            {
                "document_id": "PMID:1",
                "source": "pubtator3",
                "span_text": "PTEN",
                "entity_type": "gene",
                "canonical_id": "5728",
                "canonical_name": "PTEN",
                "start": 0,
                "end": 4,
                "confidence": None,
            },
            {
                "document_id": "PMID:1",
                "source": "bern2",
                "span_text": "PTEN",
                "entity_type": "gene",
                "canonical_id": "NCBIGene:5728",
                "canonical_name": "PTEN",
                "start": 0,
                "end": 4,
                "confidence": 0.97,
            },
            {
                "document_id": "PMID:1",
                "source": "pubtator3",
                "span_text": "glioblastoma",
                "entity_type": "disease",
                "canonical_id": "MESH:D005909",
                "canonical_name": "Glioblastoma",
                "start": 15,
                "end": 27,
                "confidence": None,
            },
        ],
    }


def test_build_canonical_text_joins_with_single_newline() -> None:
    text = build_canonical_text({"title": "abc", "abstract": "def"})
    assert text == "abc\ndef"


def test_render_highlighted_text_emits_mark_with_data_attribute() -> None:
    text = "PTEN and others"
    annotation = {
        "source": "pubtator3",
        "span_text": "PTEN",
        "entity_type": "gene",
        "canonical_id": "5728",
        "canonical_name": "PTEN",
        "start": 0,
        "end": 4,
    }
    html = render_highlighted_text(text, [annotation])
    assert '<mark class="entity entity-gene"' in html
    assert "PTEN" in html
    assert 'data-entity="' in html


def test_render_highlighted_text_picks_pubtator_over_bern2_for_overlap() -> None:
    text = "PTEN and others"
    annotations = [
        {"source": "bern2", "span_text": "PTEN", "entity_type": "gene", "start": 0, "end": 4, "canonical_id": "NCBIGene:5728"},
        {"source": "pubtator3", "span_text": "PTEN", "entity_type": "gene", "start": 0, "end": 4, "canonical_id": "5728"},
    ]
    html = render_highlighted_text(text, annotations)
    assert html.count("<mark") == 1
    match = re.search(r'data-entity="([^"]+)"', html)
    assert match is not None
    payload = json.loads(match.group(1).replace("&quot;", '"'))
    assert payload["primary_source"] == "pubtator3"


def test_group_annotations_by_span_dedupes_within_source() -> None:
    annotations = [
        {"source": "pubtator3", "span_text": "tumor", "entity_type": "disease", "canonical_id": "MESH:D009369", "canonical_name": "Neoplasms", "start": 5, "end": 10},
        {"source": "pubtator3", "span_text": "tumor", "entity_type": "disease", "canonical_id": "MESH:D009369", "canonical_name": "Neoplasms", "start": 50, "end": 55},
        {"source": "pubtator3", "span_text": "tumor", "entity_type": "disease", "canonical_id": "MESH:D009369", "canonical_name": "Neoplasms", "start": 100, "end": 105},
    ]
    rows = group_annotations_by_span(annotations)
    assert len(rows) == 1
    hits = rows[0]["by_source"]["pubtator3"]
    assert len(hits) == 1
    assert hits[0]["mentions"] == 3


def test_write_html_report_creates_self_contained_file(tmp_path: Path) -> None:
    output = tmp_path / "results.html"
    written = write_html_report(sample_payload(), output)
    assert written == output.resolve()
    html = output.read_text(encoding="utf-8")
    assert "<!--CONTENT-->" not in html
    assert "<style>" in html and "<script>" in html
    assert "regulates" in html
    assert "PTEN" in html
    assert "glioblastoma" in html
    assert "PubTator3" in html
    assert "PMID:" in html
    assert "data-entity=" in html


def test_title_is_highlighted_in_h2(tmp_path: Path) -> None:
    output = tmp_path / "results.html"
    write_html_report(sample_payload(), output)
    html = output.read_text(encoding="utf-8")
    h2_start = html.index("<h2>")
    h2_end = html.index("</h2>", h2_start)
    h2 = html[h2_start:h2_end]
    assert "<mark" in h2
    assert "PTEN" in h2


def test_compute_stats_counts_unique_positions_not_annotations() -> None:
    from bio_annotation.report.html_report import _compute_stats
    annotations = [
        {"source": "pubtator3", "span_text": "Glio", "entity_type": "disease", "start": 0, "end": 4},
        {"source": "bern2", "span_text": "Glio", "entity_type": "disease", "start": 0, "end": 4},
        {"source": "flair", "span_text": "Glio", "entity_type": "disease", "start": 0, "end": 4},
        {"source": "pubtator3", "span_text": "Glio", "entity_type": "disease", "start": 40, "end": 44},
    ]
    stats = _compute_stats(annotations)
    assert stats["disease"] == [("Glio", 2)]


def test_stats_panel_renders_per_document_and_run(tmp_path: Path) -> None:
    output = tmp_path / "results.html"
    write_html_report(sample_payload(), output)
    html = output.read_text(encoding="utf-8")
    assert "stats-run" in html
    assert "stats-doc" in html
    assert "Bioconcepts in this run" in html
    assert "Bioconcepts in this document" in html
    assert "PTEN" in html and "glioblastoma" in html


def test_write_html_report_handles_empty_documents(tmp_path: Path) -> None:
    output = tmp_path / "empty.html"
    write_html_report({"documents": [], "annotations": []}, output)
    html = output.read_text(encoding="utf-8")
    assert "No documents in this run" in html

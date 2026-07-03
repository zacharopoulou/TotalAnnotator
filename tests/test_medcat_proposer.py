from __future__ import annotations

from bio_annotation.entity_proposal.medcat_proposer import (
    _extract_records,
    _normalize_medcat_process_url,
    parse_medcat_response,
)
from bio_annotation.schemas.document import Document


def test_normalize_medcat_process_url_appends_api_process() -> None:
    assert _normalize_medcat_process_url("http://127.0.0.1:5555") == "http://127.0.0.1:5555/api/process"
    assert _normalize_medcat_process_url("http://127.0.0.1:5555/") == "http://127.0.0.1:5555/api/process"
    assert (
        _normalize_medcat_process_url("http://127.0.0.1:5555/api/process")
        == "http://127.0.0.1:5555/api/process"
    )


def test_extract_records_medcat_annotations_entities_wrapper() -> None:
    payload = {
        "result": {
            "annotations": {
                "entities": {
                    "0": {
                        "cui": "C001",
                        "source_value": "glioblastoma",
                        "start": 10,
                        "end": 22,
                        "pretty_name": "Glioblastoma",
                    }
                },
                "tokens": [],
            },
            "success": True,
        }
    }
    records = _extract_records(payload)
    assert len(records) == 1
    assert records[0]["source_value"] == "glioblastoma"


def test_parse_medcat_response_nested_entities() -> None:
    doc = Document(
        document_id="PMID:1",
        pmid="1",
        title="T",
        abstract="x" * 30,
        source="pubmed",
    )
    payload = {
        "result": {
            "annotations": {
                "entities": {
                    "0": {
                        "cui": "C0023418",
                        "type_ids": ["T191"],
                        "types": ["Neoplastic Process"],
                        "source_value": "glioma",
                        "start": 5,
                        "end": 11,
                    }
                },
                "tokens": [],
            }
        }
    }
    anns = parse_medcat_response(doc, payload)
    assert len(anns) == 1
    assert anns[0].span_text == "glioma"
    assert anns[0].canonical_id == "C0023418"


def test_parse_medcat_response_min_acc_filters_weak_spans() -> None:
    doc = Document(
        document_id="PMID:1",
        pmid="1",
        title="Test",
        abstract="alpha beta gamma",
        source="pubmed",
    )
    payload = {
        "result": {
            "annotations": {
                "entities": {
                    "0": {
                        "cui": "C1",
                        "source_value": "alpha",
                        "acc": 0.2,
                        "start": 0,
                        "end": 5,
                    },
                    "1": {
                        "cui": "C2",
                        "source_value": "beta",
                        "acc": 0.85,
                        "start": 6,
                        "end": 10,
                    },
                },
                "tokens": [],
            }
        }
    }
    anns = parse_medcat_response(doc, payload, min_acc=0.5)
    assert len(anns) == 1
    assert anns[0].span_text == "beta"

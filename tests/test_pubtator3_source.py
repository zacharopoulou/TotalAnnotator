"""Unit tests for ``PubTator3Source``.

All tests inject a fake HTTP opener into ``PubTator3Client`` so the suite
runs entirely offline. The shapes of fake payloads mirror real
PubTator3 BioC-JSON responses.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from bio_annotation.clients.pubtator3 import PubTator3Client
from bio_annotation.sources.base import FetchInput, UnsupportedInputError
from bio_annotation.sources.pubtator3 import PubTator3Source


def _bioc_document(pmid: str) -> dict[str, Any]:
    return {
        "id": pmid,
        "passages": [
            {
                "infons": {"section_type": "TITLE", "type": "title"},
                "offset": 0,
                "text": f"Sample title about PTEN ({pmid})",
                "annotations": [
                    {
                        "id": "T1",
                        "text": "PTEN",
                        "infons": {"type": "Gene", "identifier": "5728"},
                        "locations": [{"offset": 19, "length": 4}],
                    }
                ],
            },
            {
                "infons": {"section_type": "ABSTRACT", "type": "abstract"},
                "offset": 64,
                "text": "Glioblastoma is a malignant brain tumor.",
                "annotations": [
                    {
                        "id": "T2",
                        "text": "Glioblastoma",
                        "infons": {"type": "Disease", "identifier": "MESH:D005909"},
                        "locations": [{"offset": 64, "length": 12}],
                    }
                ],
            },
        ],
    }


def _source_with_payload(payload: dict[str, Any]) -> PubTator3Source:
    body = json.dumps(payload).encode("utf-8")

    def fake_open(http_request, timeout):
        return body

    client = PubTator3Client(opener=fake_open)
    return PubTator3Source(client=client)


def test_pubtator3_source_fetches_single_pmid_with_title_and_abstract() -> None:
    payload = {"documents": [_bioc_document("12345")]}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("12345"))

    assert len(docs) == 1
    doc = docs[0]
    assert doc.pmid == "12345"
    assert doc.document_id == "PMID:12345"
    assert doc.title == "Sample title about PTEN (12345)"
    assert doc.abstract == "Glioblastoma is a malignant brain tumor."
    assert doc.source == "pubtator3"
    assert doc.full_text is None


def test_pubtator3_source_stashes_raw_payload_for_annotator_reuse() -> None:
    payload = {"documents": [_bioc_document("777")]}
    source = _source_with_payload(payload)

    doc = source.fetch(FetchInput.from_pmid("777"))[0]

    stashed = doc.metadata.get("pubtator3_payload")
    assert isinstance(stashed, dict)
    assert isinstance(stashed.get("documents"), list)
    assert stashed["documents"][0]["id"] == "777"
    assert stashed["documents"][0]["passages"][0]["annotations"][0]["text"] == "PTEN"


def test_pubtator3_source_handles_multiple_pmids_in_one_response() -> None:
    payload = {"documents": [_bioc_document("111"), _bioc_document("222")]}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid_list(["111", "222"]))

    assert len(docs) == 2
    assert {doc.pmid for doc in docs} == {"111", "222"}


def test_pubtator3_source_supports_pubtator3_top_level_key() -> None:
    payload = {"PubTator3": [_bioc_document("333")]}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("333"))

    assert len(docs) == 1
    assert docs[0].pmid == "333"


def test_pubtator3_source_rejects_query_input() -> None:
    source = PubTator3Source()

    with pytest.raises(UnsupportedInputError):
        source.fetch(FetchInput.from_query("brain tumor"))


def test_pubtator3_source_rejects_raw_text_input() -> None:
    source = PubTator3Source()

    with pytest.raises(UnsupportedInputError):
        source.fetch(FetchInput.from_text("PTEN regulates apoptosis."))


def test_pubtator3_source_falls_back_when_section_types_missing() -> None:
    payload = {
        "documents": [
            {
                "id": "999",
                "passages": [
                    {"text": "First passage as title", "infons": {}},
                    {"text": "Second passage as abstract", "infons": {}},
                ],
            }
        ]
    }
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("999"))

    assert len(docs) == 1
    assert docs[0].title == "First passage as title"
    assert docs[0].abstract == "Second passage as abstract"


def test_pubtator3_source_skips_documents_without_pmid() -> None:
    payload = {"documents": [{"passages": [{"text": "orphan paper"}]}]}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("12345"))

    assert docs == []


def test_pubtator3_source_returns_empty_list_for_empty_payload() -> None:
    payload = {"documents": []}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("12345"))

    assert docs == []


def test_pubtator3_source_extracts_pmcid_from_infons_when_present() -> None:
    raw = _bioc_document("555")
    raw["infons"] = {"article-id_pmc": "PMC9876"}
    payload = {"documents": [raw]}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("555"))

    assert docs[0].metadata.get("pmcid") == "PMC9876"

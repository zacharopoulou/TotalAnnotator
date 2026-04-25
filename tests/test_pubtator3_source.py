"""Unit tests for ``PubTator3Source``.

All tests inject a fake HTTP opener into ``PubTator3Client`` so the suite
runs entirely offline. The shapes of fake payloads mirror real PubTator3
BioC-JSON and search-endpoint responses.
"""

from __future__ import annotations

import json
from typing import Any
from urllib import parse

import pytest

from bio_annotation.clients.pubtator3 import PubTator3Client
from bio_annotation.sources.base import FetchInput, UnsupportedInputError
from bio_annotation.sources.pubtator3 import PubTator3Source


def _bioc_document(
    pmid: str,
    *,
    pmcid: str | None = None,
    body_passages: list[str] | None = None,
) -> dict[str, Any]:
    passages: list[dict[str, Any]] = [
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
    ]
    for body_text in body_passages or []:
        passages.append(
            {
                "infons": {"section_type": "INTRO", "type": "paragraph"},
                "text": body_text,
                "annotations": [],
            }
        )

    raw: dict[str, Any] = {"id": pmid, "passages": passages}
    if pmcid:
        raw["infons"] = {"article-id_pmc": pmcid}
    return raw


def _source_with_payload(payload: dict[str, Any], **kwargs: Any) -> PubTator3Source:
    body = json.dumps(payload).encode("utf-8")

    def fake_open(http_request, timeout):
        return body

    client = PubTator3Client(opener=fake_open)
    return PubTator3Source(client=client, **kwargs)


def _source_with_router(
    routes: dict[str, bytes],
    *,
    record: list[str] | None = None,
    **kwargs: Any,
) -> PubTator3Source:
    """Return a source whose client routes by URL substring."""

    def fake_open(http_request, timeout):
        url = http_request.full_url
        if record is not None:
            record.append(url)
        for needle, body in routes.items():
            if needle in url:
                return body
        raise AssertionError(f"Unexpected URL in test: {url}")

    client = PubTator3Client(opener=fake_open)
    return PubTator3Source(client=client, **kwargs)


def test_fetches_single_pmid_with_title_and_abstract() -> None:
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


def test_stashes_raw_payload_for_annotator_reuse() -> None:
    payload = {"documents": [_bioc_document("777")]}
    source = _source_with_payload(payload)

    doc = source.fetch(FetchInput.from_pmid("777"))[0]

    stashed = doc.metadata.get("pubtator3_payload")
    assert isinstance(stashed, dict)
    assert isinstance(stashed.get("documents"), list)
    assert stashed["documents"][0]["id"] == "777"
    assert stashed["documents"][0]["passages"][0]["annotations"][0]["text"] == "PTEN"


def test_handles_multiple_pmids_in_one_response() -> None:
    payload = {"documents": [_bioc_document("111"), _bioc_document("222")]}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid_list(["111", "222"]))

    assert len(docs) == 2
    assert {doc.pmid for doc in docs} == {"111", "222"}


def test_supports_pubtator3_top_level_key() -> None:
    payload = {"PubTator3": [_bioc_document("333")]}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("333"))

    assert len(docs) == 1
    assert docs[0].pmid == "333"


def test_falls_back_when_section_types_missing() -> None:
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


def test_skips_documents_without_pmid() -> None:
    payload = {"documents": [{"passages": [{"text": "orphan paper"}]}]}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("12345"))

    assert docs == []


def test_returns_empty_list_for_empty_payload() -> None:
    payload = {"documents": []}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("12345"))

    assert docs == []


def test_extracts_pmcid_from_infons_when_present() -> None:
    raw = _bioc_document("555", pmcid="PMC9876")
    payload = {"documents": [raw]}
    source = _source_with_payload(payload)

    docs = source.fetch(FetchInput.from_pmid("555"))

    assert docs[0].metadata.get("pmcid") == "PMC9876"


def test_fetches_by_pmcid_uses_pmc_export_endpoint() -> None:
    record: list[str] = []
    body = json.dumps({"documents": [_bioc_document("12345", pmcid="PMC9999")]}).encode()
    source = _source_with_router({"pmc_export": body}, record=record)

    docs = source.fetch(FetchInput.from_pmcid("PMC9999"))

    assert len(docs) == 1
    assert docs[0].pmid == "12345"
    assert docs[0].metadata.get("pmcid") == "PMC9999"
    assert any("pmc_export" in url for url in record)
    assert any("pmcids=PMC9999" in url for url in record)


def test_fetches_by_pmcid_normalizes_bare_digits() -> None:
    record: list[str] = []
    body = json.dumps({"documents": [_bioc_document("1", pmcid="PMC42")]}).encode()
    source = _source_with_router({"pmc_export": body}, record=record)

    source.fetch(FetchInput.from_pmcid("42"))

    assert any("pmcids=PMC42" in url for url in record)


def test_fetches_by_pmcid_list_in_one_request() -> None:
    record: list[str] = []
    body = json.dumps(
        {
            "documents": [
                _bioc_document("1", pmcid="PMC42"),
                _bioc_document("2", pmcid="PMC43"),
            ]
        }
    ).encode()
    source = _source_with_router({"pmc_export": body}, record=record)

    docs = source.fetch(FetchInput.from_pmcid_list(["PMC42", "PMC43"]))

    assert len(docs) == 2
    assert any("pmcids=PMC42%2CPMC43" in url for url in record)


def test_full_text_flag_passes_full_true_and_populates_full_text_field() -> None:
    record: list[str] = []
    body = json.dumps(
        {
            "documents": [
                _bioc_document(
                    "12345",
                    body_passages=["Methods section text.", "Results section text."],
                )
            ]
        }
    ).encode()
    source = _source_with_router({"export": body}, record=record, full_text=True)

    docs = source.fetch(FetchInput.from_pmid("12345"))

    assert any("full=true" in url for url in record)
    assert docs[0].full_text is not None
    assert "Methods section text." in docs[0].full_text
    assert "Results section text." in docs[0].full_text


def test_query_chains_search_into_publication_export_and_keeps_score() -> None:
    record: list[str] = []
    search_body = json.dumps(
        {
            "results": [
                {"pmid": 111, "title": "Hit one", "score": 100.5},
                {"pmid": 222, "title": "Hit two", "score": 80.0},
            ],
            "current": 1,
            "count": 2,
        }
    ).encode()
    export_body = json.dumps(
        {"documents": [_bioc_document("111"), _bioc_document("222")]}
    ).encode()
    source = _source_with_router(
        {"/search/": search_body, "publications/export": export_body},
        record=record,
    )

    docs = source.fetch(FetchInput.from_query("glioblastoma microRNA"))

    assert [doc.pmid for doc in docs] == ["111", "222"]
    assert docs[0].metadata["pubtator3_search_score"] == 100.5
    assert docs[1].metadata["pubtator3_search_score"] == 80.0
    assert any("/search/" in url and "text=glioblastoma" in url for url in record)
    assert any("publications/export" in url for url in record)


def test_query_returns_empty_when_search_yields_no_hits() -> None:
    search_body = json.dumps({"results": [], "count": 0}).encode()
    source = _source_with_router({"/search/": search_body})

    docs = source.fetch(FetchInput.from_query("nonexistent_xyz"))

    assert docs == []


def test_raw_text_submits_then_retrieves_and_caches_payload(monkeypatch) -> None:
    record: list[tuple[str, str]] = []

    def fake_open(http_request, timeout):
        record.append((http_request.get_method(), http_request.full_url))
        if http_request.full_url.endswith("request.cgi"):
            return b'{"id":"sess-1234"}'
        return (
            b'{"text":"PTEN regulates apoptosis.",'
            b'"denotations":[{"id":"T1","span":{"begin":0,"end":4},"obj":"Gene"}]}'
        )

    monkeypatch.setattr("bio_annotation.clients.pubtator3.time.sleep", lambda _: None)
    client = PubTator3Client(opener=fake_open)
    source = PubTator3Source(client=client)

    docs = source.fetch(
        FetchInput.from_text("PTEN regulates apoptosis.", text_id="RAW:42")
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.document_id == "RAW:42"
    assert doc.pmid is None
    assert doc.abstract == "PTEN regulates apoptosis."
    assert doc.source == "pubtator3"
    assert doc.metadata["pubtator3_input_kind"] == "raw_text"
    assert doc.metadata["pubtator3_payload"] is not None
    assert any(url.endswith("request.cgi") for _, url in record)
    assert any("retrieve.cgi" in url for _, url in record)


def test_raw_text_returns_empty_for_blank_input() -> None:
    source = PubTator3Source()
    with pytest.raises(ValueError):
        FetchInput.from_text("   ")


def test_supports_all_six_input_kinds() -> None:
    source = PubTator3Source()
    assert source.supported_inputs == frozenset(
        {"pmid", "pmid_list", "pmcid", "pmcid_list", "query", "raw_text"}
    )


def test_rejects_unsupported_kind_through_check_supports(monkeypatch) -> None:
    """A source with an artificially narrowed supported set still rejects."""
    source = PubTator3Source(supported_inputs=frozenset({"pmid"}))

    with pytest.raises(UnsupportedInputError):
        source.fetch(FetchInput.from_query("anything"))


def test_query_url_includes_proper_encoding() -> None:
    record: list[str] = []
    search_body = json.dumps({"results": [], "count": 0}).encode()
    source = _source_with_router({"/search/": search_body}, record=record)

    source.fetch(FetchInput.from_query("@CHEMICAL_remdesivir"))

    parsed = parse.urlparse(record[0])
    assert parse.parse_qs(parsed.query)["text"] == ["@CHEMICAL_remdesivir"]

from __future__ import annotations

from typing import Any

import pytest

from bio_annotation.clients.europe_pmc import EuropePmcClient
from bio_annotation.sources import EuropePmcSource, FetchInput
from bio_annotation.sources.base import UnsupportedInputError


def _result(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "36403686",
        "source": "MED",
        "pmid": "36403686",
        "pmcid": "",
        "doi": "10.1016/j.ejphar.2022.175388",
        "title": "MicroRNA-based therapy for glioblastoma.",
        "abstractText": "Glioblastoma (GBM) is the most common primary brain tumor.",
        "pubYear": "2023",
        "isOpenAccess": "N",
        "inEPMC": "N",
        "citedByCount": 16,
        "license": "cc by-nc-nd",
        "fullTextUrlList": {
            "fullTextUrl": [
                {
                    "url": "https://doi.org/10.1016/j.ejphar.2022.175388",
                    "site": "DOI",
                    "availability": "Subscription required",
                    "documentStyle": "doi",
                }
            ]
        },
    }
    base.update(overrides)
    return base


def _make_client(payload: dict[str, Any]) -> EuropePmcClient:
    """Return a client whose opener always returns the same JSON payload."""
    import json

    def fake_open(http_request, timeout: int) -> bytes:
        return json.dumps(payload).encode("utf-8")

    return EuropePmcClient(opener=fake_open)


def test_fetch_single_pmid_populates_core_fields() -> None:
    payload = {"resultList": {"result": [_result()]}}
    source = EuropePmcSource(client=_make_client(payload))

    docs = source.fetch(FetchInput.from_pmid("36403686"))

    assert len(docs) == 1
    doc = docs[0]
    assert doc.document_id == "PMID:36403686"
    assert doc.pmid == "36403686"
    assert doc.title.startswith("MicroRNA-based")
    assert "Glioblastoma" in doc.abstract
    assert doc.year == "2023"
    assert doc.source == "europe_pmc"


def test_fetch_stashes_full_result_and_convenience_fields_in_metadata() -> None:
    payload = {"resultList": {"result": [_result()]}}
    source = EuropePmcSource(client=_make_client(payload))

    doc = source.fetch(FetchInput.from_pmid("36403686"))[0]

    assert doc.metadata["epmc_meta"]["doi"] == "10.1016/j.ejphar.2022.175388"
    assert doc.metadata["doi"] == "10.1016/j.ejphar.2022.175388"
    assert doc.metadata["citation_count"] == 16
    assert doc.metadata["is_open_access"] is False
    assert doc.metadata["in_epmc"] is False
    assert doc.metadata["license"] == "cc by-nc-nd"
    assert doc.metadata["full_text_urls"] == [
        {
            "url": "https://doi.org/10.1016/j.ejphar.2022.175388",
            "site": "DOI",
            "availability": "Subscription required",
            "document_style": "doi",
        }
    ]


def test_fetch_translates_yes_open_access_flag() -> None:
    payload = {
        "resultList": {
            "result": [_result(isOpenAccess="Y", inEPMC="Y", pmcid="PMC9876543")]
        }
    }
    source = EuropePmcSource(client=_make_client(payload))

    doc = source.fetch(FetchInput.from_pmid("36403686"))[0]

    assert doc.metadata["is_open_access"] is True
    assert doc.metadata["in_epmc"] is True
    assert doc.metadata["pmcid"] == "PMC9876543"


def test_fetch_pmid_list_returns_documents_in_payload_order() -> None:
    payload = {
        "resultList": {
            "result": [
                _result(pmid="1", title="A"),
                _result(pmid="2", title="B"),
                _result(pmid="3", title="C"),
            ]
        }
    }
    source = EuropePmcSource(client=_make_client(payload))

    docs = source.fetch(FetchInput.from_pmid_list(["1", "2", "3"]))

    assert [d.pmid for d in docs] == ["1", "2", "3"]
    assert [d.title for d in docs] == ["A", "B", "C"]


def test_fetch_pmcid_uses_pmcid_query_path() -> None:
    captured: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        captured.append(http_request.full_url)
        import json

        return json.dumps(
            {
                "resultList": {
                    "result": [
                        _result(pmid="", pmcid="PMC9876543", source="PMC", id="9876543")
                    ]
                }
            }
        ).encode("utf-8")

    source = EuropePmcSource(client=EuropePmcClient(opener=fake_open))
    docs = source.fetch(FetchInput.from_pmcid("PMC9876543"))

    assert "PMCID%3APMC9876543" in captured[0]
    assert docs[0].document_id == "PMC9876543"
    assert docs[0].metadata["pmcid"] == "PMC9876543"


def test_fetch_query_passes_through_user_text() -> None:
    captured: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        captured.append(http_request.full_url)
        import json

        return json.dumps(
            {"resultList": {"result": [_result(pmid="9", title="Hit")]}}
        ).encode("utf-8")

    source = EuropePmcSource(client=EuropePmcClient(opener=fake_open))
    docs = source.fetch(FetchInput.from_query("microRNA AND glioblastoma"))

    from urllib import parse

    qs = parse.parse_qs(parse.urlparse(captured[0]).query)
    assert qs["query"] == ["microRNA AND glioblastoma"]
    assert docs[0].title == "Hit"


def test_fetch_paginates_when_max_search_pages_is_high() -> None:
    pages = [
        {
            "nextCursorMark": "page2",
            "resultList": {"result": [_result(pmid="1", title="A")]},
        },
        {
            "nextCursorMark": "page3",
            "resultList": {"result": [_result(pmid="2", title="B")]},
        },
        {
            "nextCursorMark": "page3",
            "resultList": {"result": [_result(pmid="3", title="C")]},
        },
    ]

    def fake_open(http_request, timeout: int) -> bytes:
        import json

        return json.dumps(pages.pop(0)).encode("utf-8")

    source = EuropePmcSource(
        client=EuropePmcClient(opener=fake_open),
        max_search_pages=3,
    )
    docs = source.fetch(FetchInput.from_query("brain tumor"))

    assert [d.pmid for d in docs] == ["1", "2", "3"]


def test_fetch_returns_empty_list_when_payload_has_no_results() -> None:
    payload = {"resultList": {"result": []}}
    source = EuropePmcSource(client=_make_client(payload))

    docs = source.fetch(FetchInput.from_query("zzz"))

    assert docs == []


def test_fetch_skips_non_dict_results_in_payload() -> None:
    payload = {"resultList": {"result": [_result(pmid="1"), "not a dict", None]}}
    source = EuropePmcSource(client=_make_client(payload))

    docs = source.fetch(FetchInput.from_query("x"))

    assert len(docs) == 1
    assert docs[0].pmid == "1"


def test_fetch_rejects_raw_text_input() -> None:
    source = EuropePmcSource(client=_make_client({"resultList": {"result": []}}))

    with pytest.raises(UnsupportedInputError):
        source.fetch(FetchInput.from_text("free text", text_id="X"))


def test_fields_filter_keeps_core_metadata_keys() -> None:
    payload = {"resultList": {"result": [_result()]}}
    source = EuropePmcSource(client=_make_client(payload))

    request = FetchInput.from_pmid("36403686", fields=frozenset({"citation_count"}))
    doc = source.fetch(request)[0]

    assert doc.metadata.get("citation_count") == 16
    assert "license" not in doc.metadata
    assert "full_text_urls" not in doc.metadata


def test_fields_none_keeps_full_metadata() -> None:
    payload = {"resultList": {"result": [_result()]}}
    source = EuropePmcSource(client=_make_client(payload))

    doc = source.fetch(FetchInput.from_pmid("36403686"))[0]

    assert "license" in doc.metadata
    assert "full_text_urls" in doc.metadata


def test_per_source_slice_overrides_global_fields_for_europe_pmc() -> None:
    """fields_per_source['europe_pmc'] takes precedence over global fields."""

    payload = {"resultList": {"result": [_result()]}}
    source = EuropePmcSource(client=_make_client(payload))

    request = FetchInput.from_pmid(
        "36403686",
        fields=frozenset({"license"}),  # global says: keep license
        fields_per_source={
            "europe_pmc": frozenset({"citation_count"}),  # but EPMC slice says: only citation_count
        },
    )
    doc = source.fetch(request)[0]

    assert doc.metadata.get("citation_count") == 16
    assert "license" not in doc.metadata  # global filter overridden by EPMC slice
    assert "full_text_urls" not in doc.metadata


def test_per_source_filter_for_other_source_does_not_affect_europe_pmc() -> None:
    """A slice for 'entrez' does not affect the EuropePMC filter resolution."""

    payload = {"resultList": {"result": [_result()]}}
    source = EuropePmcSource(client=_make_client(payload))

    request = FetchInput.from_pmid(
        "36403686",
        fields=frozenset({"license"}),
        fields_per_source={"entrez": frozenset({"mesh_terms"})},
    )
    doc = source.fetch(request)[0]

    # EuropePMC falls back to the global 'license' filter; license is kept,
    # everything else (citation_count, full_text_urls) is dropped.
    assert "license" in doc.metadata
    assert "citation_count" not in doc.metadata
    assert "full_text_urls" not in doc.metadata


def test_per_source_empty_set_for_europe_pmc_keeps_only_core_metadata() -> None:
    payload = {"resultList": {"result": [_result()]}}
    source = EuropePmcSource(client=_make_client(payload))

    request = FetchInput.from_pmid(
        "36403686",
        fields_per_source={"europe_pmc": frozenset()},
    )
    doc = source.fetch(request)[0]

    # _CORE_FIELDS in europe_pmc.py = {pmid, pmcid, title, abstract, year}.
    # Anything outside that set must be dropped from metadata.
    for dropped in ("license", "citation_count", "full_text_urls", "doi"):
        assert dropped not in doc.metadata


def test_supports_all_advertised_input_kinds() -> None:
    source = EuropePmcSource()
    expected = {"pmid", "pmid_list", "pmcid", "pmcid_list", "query"}
    assert source.supported_inputs == expected
    assert "raw_text" not in source.supported_inputs


def test_falls_back_to_epmc_id_when_pmid_and_pmcid_missing() -> None:
    payload = {
        "resultList": {
            "result": [
                _result(
                    pmid="",
                    pmcid="",
                    source="PPR",
                    id="PPR123",
                )
            ]
        }
    }
    source = EuropePmcSource(client=_make_client(payload))

    docs = source.fetch(FetchInput.from_query("preprint"))

    assert docs[0].document_id == "PPR:PPR123"
    assert docs[0].pmid is None

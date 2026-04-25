from __future__ import annotations

import json
from urllib import parse

import pytest

from bio_annotation.clients.europe_pmc import (
    EUROPE_PMC_API_BASE_URL,
    EuropePmcClient,
    MAX_PAGE_SIZE,
)


def _ok(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_search_issues_single_get_with_query_and_cursor() -> None:
    requests: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append(http_request.full_url)
        return _ok(
            {
                "hitCount": 1,
                "nextCursorMark": "abc",
                "resultList": {"result": [{"id": "1", "pmid": "1"}]},
            }
        )

    client = EuropePmcClient(opener=fake_open, page_size=25)
    payload = client.search("glioblastoma microRNA")

    assert payload["hitCount"] == 1
    assert payload["resultList"]["result"] == [{"id": "1", "pmid": "1"}]
    assert len(requests) == 1
    parsed = parse.urlparse(requests[0])
    assert parsed.path.endswith("/search")
    qs = parse.parse_qs(parsed.query)
    assert qs["query"] == ["glioblastoma microRNA"]
    assert qs["cursorMark"] == ["*"]
    assert qs["pageSize"] == ["25"]
    assert qs["format"] == ["json"]
    assert qs["resulttype"] == ["core"]


def test_search_paginates_using_next_cursor_mark() -> None:
    pages = [
        {
            "hitCount": 3,
            "nextCursorMark": "page2",
            "resultList": {"result": [{"id": "1"}, {"id": "2"}]},
        },
        {
            "hitCount": 3,
            "nextCursorMark": "page3",
            "resultList": {"result": [{"id": "3"}]},
        },
    ]
    seen_cursors: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        qs = parse.parse_qs(parse.urlparse(http_request.full_url).query)
        seen_cursors.append(qs["cursorMark"][0])
        return _ok(pages.pop(0))

    client = EuropePmcClient(opener=fake_open)
    payload = client.search("brain tumor", max_pages=2)

    assert seen_cursors == ["*", "page2"]
    assert [r["id"] for r in payload["resultList"]["result"]] == ["1", "2", "3"]


def test_search_stops_when_cursor_does_not_advance() -> None:
    calls = {"n": 0}

    def fake_open(http_request, timeout: int) -> bytes:
        calls["n"] += 1
        return _ok(
            {
                "nextCursorMark": "*",
                "resultList": {"result": [{"id": str(calls["n"])}]},
            }
        )

    client = EuropePmcClient(opener=fake_open)
    payload = client.search("x", max_pages=5)

    assert calls["n"] == 1
    assert payload["resultList"]["result"] == [{"id": "1"}]


def test_search_stops_when_page_returns_no_results() -> None:
    pages = [
        {
            "nextCursorMark": "page2",
            "resultList": {"result": [{"id": "1"}]},
        },
        {
            "nextCursorMark": "page3",
            "resultList": {"result": []},
        },
    ]

    def fake_open(http_request, timeout: int) -> bytes:
        return _ok(pages.pop(0))

    client = EuropePmcClient(opener=fake_open)
    payload = client.search("x", max_pages=5)

    assert pages == []
    assert payload["resultList"]["result"] == [{"id": "1"}]


def test_fetch_by_pmids_builds_or_query_with_src_filter() -> None:
    captured: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        captured.append(http_request.full_url)
        return _ok({"resultList": {"result": [{"pmid": "1"}, {"pmid": "2"}]}})

    client = EuropePmcClient(opener=fake_open)
    payload = client.fetch_by_pmids(["1", "2"])

    qs = parse.parse_qs(parse.urlparse(captured[0]).query)
    assert qs["query"] == ["(EXT_ID:1 OR EXT_ID:2) AND SRC:MED"]
    assert {r["pmid"] for r in payload["resultList"]["result"]} == {"1", "2"}


def test_fetch_by_pmids_with_empty_list_skips_network() -> None:
    def fake_open(http_request, timeout: int) -> bytes:  # pragma: no cover
        raise AssertionError("client should not perform a request")

    client = EuropePmcClient(opener=fake_open)
    payload = client.fetch_by_pmids([])
    assert payload == {"resultList": {"result": []}}


def test_fetch_by_pmcids_normalises_prefixes() -> None:
    captured: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        captured.append(http_request.full_url)
        return _ok({"resultList": {"result": []}})

    client = EuropePmcClient(opener=fake_open)
    client.fetch_by_pmcids(["123", "PMC456", "pmc:789"])

    qs = parse.parse_qs(parse.urlparse(captured[0]).query)
    assert qs["query"] == ["PMCID:PMC123 OR PMCID:PMC456 OR PMCID:PMC789"]


def test_fetch_full_text_xml_returns_raw_xml_string() -> None:
    captured: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        captured.append(http_request.full_url)
        return b"<article><body><p>hello</p></body></article>"

    client = EuropePmcClient(opener=fake_open)
    xml = client.fetch_full_text_xml("PMC123")

    assert xml.startswith("<article>")
    assert captured[0] == f"{EUROPE_PMC_API_BASE_URL}/PMC123/fullTextXML"


def test_search_rejects_empty_query() -> None:
    client = EuropePmcClient(opener=lambda *_a, **_k: b"{}")
    with pytest.raises(ValueError):
        client.search("")
    with pytest.raises(ValueError):
        client.search("   ")


def test_search_rejects_invalid_max_pages() -> None:
    client = EuropePmcClient(opener=lambda *_a, **_k: b"{}")
    with pytest.raises(ValueError):
        client.search("x", max_pages=0)


def test_search_rejects_invalid_page_size() -> None:
    client = EuropePmcClient(opener=lambda *_a, **_k: b"{}")
    with pytest.raises(ValueError):
        client.search("x", page_size=0)
    with pytest.raises(ValueError):
        client.search("x", page_size=MAX_PAGE_SIZE + 1)

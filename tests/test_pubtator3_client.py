from __future__ import annotations

from urllib import error, parse

from bio_annotation.clients.pubtator3 import PubTator3Client


def test_pubtator3_client_uses_get_for_small_pmid_batches() -> None:
    requests: list[tuple[str, str | None]] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append((http_request.get_method(), http_request.full_url))
        return b'{"documents":[{"id":"123"}]}'

    client = PubTator3Client(opener=fake_open, get_batch_size=100, post_batch_size=1000)
    payload = client.fetch_publications_by_pmids(["123"], format="biocjson")

    assert payload == {"documents": [{"id": "123"}]}
    assert requests == [
        (
            "GET",
            "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson?pmids=123",
        )
    ]


def test_pubtator3_client_uses_post_and_merges_large_batches() -> None:
    requests: list[tuple[str, bytes | None, str | None]] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append((http_request.get_method(), http_request.data, http_request.full_url))
        if http_request.data:
            query = parse.parse_qs(http_request.data.decode("utf-8"))
        else:
            query = parse.parse_qs(parse.urlparse(http_request.full_url).query)
        identifiers = query["pmids"][0].split(",")
        return ('{"documents":[' + ",".join(f'{{"id":"{identifier}"}}' for identifier in identifiers) + "]}").encode("utf-8")

    client = PubTator3Client(opener=fake_open, get_batch_size=2, post_batch_size=3)
    payload = client.fetch_publications_by_pmids(["1", "2", "3", "4"], format="biocjson")

    assert payload == {"documents": [{"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "4"}]}
    assert requests == [
        ("POST", b"pmids=1%2C2%2C3", "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson"),
        ("GET", None, "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson?pmids=4"),
    ]


def test_pubtator3_client_submits_and_retrieves_text_jobs() -> None:
    requests: list[tuple[str, bytes | None, str]] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append((http_request.get_method(), http_request.data, http_request.full_url))
        if http_request.full_url.endswith("request.cgi"):
            return b'{"id":"1111-2222-3333-4444"}'
        return b'{"text":"PTEN","denotations":[]}'

    client = PubTator3Client(opener=fake_open)
    session_id = client.submit_text_annotation("PTEN")
    payload = client.retrieve_text_annotation(session_id)

    assert session_id == "1111-2222-3333-4444"
    assert payload == '{"text":"PTEN","denotations":[]}'
    assert requests == [
        (
            "POST",
            b"text=PTEN&bioconcept=All",
            "https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/RESTful/request.cgi",
        ),
        (
            "GET",
            None,
            "https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/RESTful/retrieve.cgi?id=1111-2222-3333-4444",
        ),
    ]


def test_pubtator3_client_fetch_pmcids_uses_pmc_export_endpoint() -> None:
    requests: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append(http_request.full_url)
        return b'{"documents":[{"id":"PMC9999"}]}'

    client = PubTator3Client(opener=fake_open)
    payload = client.fetch_publications_by_pmcids(["PMC9999"], format="biocjson")

    assert payload == {"documents": [{"id": "PMC9999"}]}
    assert requests == [
        "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/pmc_export/biocjson?pmcids=PMC9999"
    ]


def test_pubtator3_client_export_passes_full_true_when_requested() -> None:
    requests: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append(http_request.full_url)
        return b'{"documents":[{"id":"42"}]}'

    client = PubTator3Client(opener=fake_open)
    client.fetch_publications_by_pmids(["42"], format="biocjson", full=True)

    assert requests == [
        "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson?pmids=42&full=true"
    ]


def test_pubtator3_client_export_pmcids_passes_full_true_when_requested() -> None:
    requests: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append(http_request.full_url)
        return b'{"documents":[{"id":"PMC42"}]}'

    client = PubTator3Client(opener=fake_open)
    client.fetch_publications_by_pmcids(["PMC42"], format="biocjson", full=True)

    assert requests == [
        "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/pmc_export/biocjson?pmcids=PMC42&full=true"
    ]


def test_pubtator3_client_full_text_rejects_pubtator_format() -> None:
    client = PubTator3Client()

    import pytest

    with pytest.raises(ValueError, match="full-text"):
        client.fetch_publications_by_pmids(["1"], format="pubtator", full=True)


def test_pubtator3_client_search_publications_single_page() -> None:
    requests: list[str] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append(http_request.full_url)
        return (
            b'{"results":[{"pmid":1,"title":"A"},{"pmid":2,"title":"B"}],'
            b'"page_size":10,"current":1,"count":2,"total_pages":1}'
        )

    client = PubTator3Client(opener=fake_open)
    payload = client.search_publications("microRNA AND glioblastoma")

    assert payload["results"][0]["pmid"] == 1
    assert payload["results"][1]["title"] == "B"
    assert requests == [
        "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/search/?text=microRNA+AND+glioblastoma&page=1"
    ]


def test_pubtator3_client_search_publications_merges_multiple_pages() -> None:
    requests: list[str] = []
    pages: dict[str, bytes] = {
        "1": b'{"results":[{"pmid":1},{"pmid":2}],"current":1,"count":4}',
        "2": b'{"results":[{"pmid":3},{"pmid":4}],"current":2,"count":4}',
        "3": b'{"results":[],"current":3,"count":4}',
    }

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append(http_request.full_url)
        page = parse.parse_qs(parse.urlparse(http_request.full_url).query)["page"][0]
        return pages[page]

    client = PubTator3Client(opener=fake_open)
    payload = client.search_publications("foo", max_pages=3)

    assert [hit["pmid"] for hit in payload["results"]] == [1, 2, 3, 4]
    assert len(requests) == 3


def test_pubtator3_client_search_publications_validates_args() -> None:
    import pytest

    client = PubTator3Client()
    with pytest.raises(ValueError, match="empty"):
        client.search_publications("")
    with pytest.raises(ValueError, match=">= 1"):
        client.search_publications("foo", page=0)
    with pytest.raises(ValueError, match=">= 1"):
        client.search_publications("foo", max_pages=0)


def test_pubtator3_client_annotate_text_polls_until_ready(monkeypatch) -> None:
    requests: list[tuple[str, bytes | None, str]] = []
    attempts = {"retrieve": 0}

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append((http_request.get_method(), http_request.data, http_request.full_url))
        if http_request.full_url.endswith("request.cgi"):
            return b'{"id":"1111-2222-3333-4444"}'
        attempts["retrieve"] += 1
        if attempts["retrieve"] == 1:
            raise error.HTTPError(http_request.full_url, 400, "Bad Request", hdrs=None, fp=None)
        return b'{"text":"PTEN","denotations":[]}'

    monkeypatch.setattr("bio_annotation.clients.pubtator3.time.sleep", lambda _: None)

    client = PubTator3Client(opener=fake_open)
    payload = client.annotate_text("PTEN", max_attempts=2, poll_interval=0.0)

    assert payload == '{"text":"PTEN","denotations":[]}'
    assert requests == [
        (
            "POST",
            b"text=PTEN&bioconcept=All",
            "https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/RESTful/request.cgi",
        ),
        (
            "GET",
            None,
            "https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/RESTful/retrieve.cgi?id=1111-2222-3333-4444",
        ),
        (
            "GET",
            None,
            "https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/RESTful/retrieve.cgi?id=1111-2222-3333-4444",
        ),
    ]

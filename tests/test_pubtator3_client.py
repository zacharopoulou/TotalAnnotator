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
    requests: list[tuple[str, str]] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append((http_request.get_method(), http_request.full_url))
        if http_request.get_method() == "POST":
            return b"1111-2222-3333-4444"
        return b'{"text":"PTEN","denotations":[]}'

    client = PubTator3Client(opener=fake_open)
    session_id = client.submit_text_annotation('{"text":"PTEN"}')
    payload = client.retrieve_text_annotation(session_id)

    assert session_id == "1111-2222-3333-4444"
    assert payload == '{"text":"PTEN","denotations":[]}'


def test_pubtator3_client_annotate_text_polls_until_ready(monkeypatch) -> None:
    requests: list[tuple[str, str]] = []
    attempts = {"retrieve": 0}

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append((http_request.get_method(), http_request.full_url))
        if http_request.get_method() == "POST":
            return b"1111-2222-3333-4444"
        attempts["retrieve"] += 1
        if attempts["retrieve"] == 1:
            raise error.HTTPError(http_request.full_url, 404, "Not Found", hdrs=None, fp=None)
        return b'{"text":"PTEN","denotations":[]}'

    monkeypatch.setattr("bio_annotation.clients.pubtator3.time.sleep", lambda _: None)

    client = PubTator3Client(opener=fake_open)
    payload = client.annotate_text('{"text":"PTEN"}', max_attempts=2, poll_interval=0.0)

    assert payload == '{"text":"PTEN","denotations":[]}'
    assert requests == [
        ("POST", "https://www.ncbi.nlm.nih.gov/research/pubtator-api/annotations/annotate/submit/BioConcept"),
        ("GET", "https://www.ncbi.nlm.nih.gov/research/pubtator-api/annotations/annotate/retrieve/1111-2222-3333-4444"),
        ("GET", "https://www.ncbi.nlm.nih.gov/research/pubtator-api/annotations/annotate/retrieve/1111-2222-3333-4444"),
    ]

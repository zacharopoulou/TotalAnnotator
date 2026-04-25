from __future__ import annotations

from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3
from bio_annotation.clients.pubtator3 import PubTator3Client
from bio_annotation.schemas.document import Document


def test_pubtator3_text_fallback_uses_submit_and_retrieve_for_text_only_document() -> None:
    requests: list[tuple[str, str]] = []

    def fake_open(http_request, timeout: int) -> bytes:
        requests.append((http_request.get_method(), http_request.full_url))
        if http_request.get_method() == "POST":
            return b'{"id":"1111-2222-3333-4444"}'
        return (
            b'{"text":"PTEN regulates glioblastoma.","denotations":['
            b'{"id":"T1","span":{"begin":0,"end":4},"obj":"Gene:5728","text":"PTEN"}'
            b"]}"
        )

    client = PubTator3Client(opener=fake_open)

    document = Document(
        document_id="doc1",
        pmid=None,
        title="",
        abstract="",
        full_text="PTEN regulates glioblastoma.",
        source="text_table",
    )

    annotations = annotate_with_pubtator3(
        document,
        client=client,
        mode="auto",
        poll_interval_seconds=0.0,
        max_poll_attempts=1,
    )

    assert len(annotations) == 1
    assert annotations[0].span_text == "PTEN"
    assert annotations[0].canonical_id == "5728"
    assert annotations[0].source == "pubtator3"
    assert requests[0][0] == "POST"
    assert requests[1][0] == "GET"
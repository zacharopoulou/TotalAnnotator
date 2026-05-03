"""Regression tests for PubTator3 fetch adapter BioC quirks."""

from __future__ import annotations

from bio_annotation.fetch.adapters.pubtator3 import _extract_pmid, _payload_to_documents


def test_extract_pmid_prefers_passage_article_id_pmid_over_top_level_id() -> None:
    """PubTator3 BioC sometimes puts PMC digits in document ``id``; PMID is in passage infons."""
    raw = {
        "id": "10932356",
        "passages": [
            {
                "infons": {
                    "article-id_pmid": "38473811",
                    "section_type": "TITLE",
                },
                "text": "Example title",
            }
        ],
    }
    assert _extract_pmid(raw) == "38473811"


def test_payload_to_documents_single_pmid_when_doc_id_is_pmc_digits() -> None:
    payload = {
        "documents": [
            {
                "id": "10932356",
                "passages": [
                    {
                        "infons": {
                            "article-id_pmid": "38473811",
                            "section_type": "TITLE",
                        },
                        "text": "T",
                    },
                    {
                        "infons": {"section_type": "ABSTRACT"},
                        "text": "A body",
                    },
                ],
            }
        ]
    }
    docs = _payload_to_documents(payload, with_full_text=False)
    assert len(docs) == 1
    assert docs[0].document_id == "PMID:38473811"
    assert docs[0].pmid == "38473811"

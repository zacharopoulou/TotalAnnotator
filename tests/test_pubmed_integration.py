from __future__ import annotations

import os

import pytest

from bio_annotation.io.readers import fetch_pubmed_record


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.environ.get("TOTALANNOTATOR_RUN_LIVE_PUBMED") != "1",
    reason="Set TOTALANNOTATOR_RUN_LIVE_PUBMED=1 to run live PubMed ingestion tests.",
)
def test_fetch_pubmed_record_live() -> None:
    record = fetch_pubmed_record("38123456")
    assert record["pmid"] == "38123456"
    assert record["title"] != ""

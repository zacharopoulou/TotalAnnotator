from __future__ import annotations

from pathlib import Path

import pytest

from bio_annotation.io.readers import fetch_pubmed_record
from bio_annotation.preprocessing.document_loader import (
    load_document_from_pmid,
    load_documents_from_pmid_file,
    load_documents_from_text_table,
)
from bio_annotation.schemas.document import Document


PUBMED_XML = """\
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>38123456</PMID>
      <Article>
        <ArticleTitle>TP53 <i>regulates</i> glioblastoma</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">TP53 is important.</AbstractText>
          <AbstractText>U87-MG cells were evaluated.</AbstractText>
        </Abstract>
        <Journal>
          <JournalIssue>
            <PubDate><Year>2024</Year></PubDate>
          </JournalIssue>
        </Journal>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">38123456</ArticleId>
        <ArticleId IdType="pmc">PMC1234567</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return PUBMED_XML.encode("utf-8")


def test_fetch_pubmed_record_parses_nested_xml_text(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _FakeResponse())

    record = fetch_pubmed_record("38123456")

    assert record["pmid"] == "38123456"
    assert record["title"] == "TP53 regulates glioblastoma"
    assert "BACKGROUND: TP53 is important." in record["abstract"]
    assert "U87-MG cells were evaluated." in record["abstract"]
    assert record["year"] == "2024"
    assert record["pmcid"] == "PMC1234567"


def test_load_document_from_pmid_builds_document() -> None:
    doc = load_document_from_pmid(
        "38123456",
        fetcher=lambda pmid: {
            "pmid": pmid,
            "pmcid": "PMC1234567",
            "title": "TP53 regulates glioblastoma",
            "abstract": "U87-MG cells were evaluated.",
            "year": "2024",
        },
        extra_metadata={"batch": "run-1"},
    )

    assert isinstance(doc, Document)
    assert doc.document_id == "PMID:38123456"
    assert doc.pmid == "38123456"
    assert doc.source == "pubmed"
    assert doc.full_text is None
    assert doc.metadata["batch"] == "run-1"
    assert doc.metadata["pubmed_record"]["pmcid"] == "PMC1234567"


def test_load_documents_from_pmid_file_deduplicates(tmp_path: Path) -> None:
    pmid_file = tmp_path / "pmids.txt"
    pmid_file.write_text("38123456\nPMID:38123456\n12345678\n", encoding="utf-8")

    calls: list[str] = []

    def fake_fetcher(pmid: str) -> dict[str, str]:
        calls.append(pmid)
        return {"pmid": pmid, "title": f"title-{pmid}", "abstract": f"abstract-{pmid}"}

    documents = load_documents_from_pmid_file(pmid_file, fetcher=fake_fetcher)

    assert [doc.document_id for doc in documents] == ["PMID:38123456", "PMID:12345678"]
    assert calls == ["38123456", "12345678"]


def test_load_documents_from_text_table_csv(tmp_path: Path) -> None:
    text_file = tmp_path / "documents.csv"
    text_file.write_text(
        "\n".join(
            [
                "document_id,title,abstract,cohort",
                "doc1,Title one,Abstract one,batch-a",
                "doc2,Title two,Abstract two,batch-b",
            ]
        ),
        encoding="utf-8",
    )

    documents = load_documents_from_text_table(
        text_file,
        fmt="csv",
        document_id_column="document_id",
        title_column="title",
        abstract_column="abstract",
    )

    assert [doc.document_id for doc in documents] == ["doc1", "doc2"]
    assert documents[0].source == "text_table"
    assert documents[0].metadata["cohort"] == "batch-a"


def test_load_documents_from_text_table_missing_column_raises(tmp_path: Path) -> None:
    text_file = tmp_path / "documents.csv"
    text_file.write_text("document_id,title\nonly_id,Only title\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required columns"):
        load_documents_from_text_table(
            text_file,
            fmt="csv",
            document_id_column="document_id",
            title_column="title",
            abstract_column="abstract",
        )

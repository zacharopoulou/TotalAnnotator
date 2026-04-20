from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

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
      <DateRevised>
        <Year>2024</Year><Month>05</Month><Day>01</Day>
      </DateRevised>
      <Article>
        <ArticleTitle>TP53 <i>regulates</i> glioblastoma</ArticleTitle>
        <Pagination><MedlinePgn>123-130</MedlinePgn></Pagination>
        <ELocationID EIdType="doi">10.1000/test-doi</ELocationID>
        <Abstract>
          <AbstractText Label="BACKGROUND" NlmCategory="BACKGROUND">TP53 is important.</AbstractText>
          <AbstractText NlmCategory="METHODS">U87-MG cells were evaluated.</AbstractText>
        </Abstract>
        <Language>eng</Language>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
        </PublicationTypeList>
        <ArticleDate DateType="Electronic">
          <Year>2024</Year><Month>01</Month><Day>05</Day>
        </ArticleDate>
        <Journal>
          <ISSN IssnType="Print">1234-5678</ISSN>
          <Title>Journal of Testing</Title>
          <ISOAbbreviation>J Test</ISOAbbreviation>
          <JournalIssue>
            <Volume>12</Volume>
            <Issue>4</Issue>
            <PubDate><Year>2024</Year></PubDate>
          </JournalIssue>
        </Journal>
        <AuthorList>
          <Author>
            <LastName>Smith</LastName>
            <ForeName>Jane</ForeName>
            <Initials>J</Initials>
            <Identifier Source="ORCID">https://orcid.org/0000-0001-2345-6789</Identifier>
            <AffiliationInfo>
              <Affiliation>Department of Biology, Test University</Affiliation>
            </AffiliationInfo>
          </Author>
        </AuthorList>
        <GrantList>
          <Grant>
            <GrantID>R01CA123456</GrantID>
            <Acronym>TEST</Acronym>
            <Agency>NIH</Agency>
            <Country>USA</Country>
          </Grant>
        </GrantList>
        <DataBankList>
          <DataBank>
            <DataBankName>GenBank</DataBankName>
            <AccessionNumberList>
              <AccessionNumber>ABC123</AccessionNumber>
              <AccessionNumber>XYZ789</AccessionNumber>
            </AccessionNumberList>
          </DataBank>
        </DataBankList>
      </Article>
      <MedlineJournalInfo>
        <Country>United States</Country>
        <NlmUniqueID>987654</NlmUniqueID>
        <MedlineTA>J Test</MedlineTA>
        <ISSNLinking>1234-5678</ISSNLinking>
      </MedlineJournalInfo>
      <ChemicalList>
        <Chemical>
          <RegistryNumber>RN123</RegistryNumber>
          <NameOfSubstance UI="D000001">Temozolomide</NameOfSubstance>
        </Chemical>
      </ChemicalList>
      <SupplMeshList>
        <SupplMeshName Type="Disease" UI="C000001">Supplemental Term</SupplMeshName>
      </SupplMeshList>
      <GeneSymbolList>
        <GeneSymbol>TP53</GeneSymbol>
      </GeneSymbolList>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName UI="D005909" MajorTopicYN="Y">Glioblastoma</DescriptorName>
          <QualifierName UI="Q0001" MajorTopicYN="N">genetics</QualifierName>
        </MeshHeading>
      </MeshHeadingList>
      <KeywordList>
        <Keyword>TP53</Keyword>
        <Keyword>glioblastoma</Keyword>
      </KeywordList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">38123456</ArticleId>
        <ArticleId IdType="pmc">PMC1234567</ArticleId>
        <ArticleId IdType="doi">10.1000/test-doi</ArticleId>
      </ArticleIdList>
      <History>
        <PubMedPubDate PubStatus="received"><Year>2023</Year><Month>12</Month><Day>01</Day></PubMedPubDate>
        <PubMedPubDate PubStatus="accepted"><Year>2024</Year><Month>01</Month><Day>15</Day></PubMedPubDate>
        <PubMedPubDate PubStatus="entrez"><Year>2024</Year><Month>02</Month><Day>01</Day></PubMedPubDate>
        <PubMedPubDate PubStatus="medline"><Year>2024</Year><Month>02</Month><Day>02</Day></PubMedPubDate>
      </History>
      <CommentsCorrectionsList>
        <CommentsCorrections RefType="CommentOn">
          <RefSource>Test Journal. 2023</RefSource>
          <PMID>123456</PMID>
        </CommentsCorrections>
      </CommentsCorrectionsList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


class _FakeResponse:
    def __init__(self, payload: str):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload.encode("utf-8")


ELINK_JSON = """\
{
  "linksets": [
    {
      "ids": ["38123456"],
      "linksetdbs": [
        {
          "linkname": "pubmed_pubmed",
          "links": [{"id": "40000001", "score": 42}]
        },
        {
          "linkname": "pubmed_pubmed_citedin",
          "links": ["40000002"]
        },
        {
          "linkname": "pubmed_pubmed_refs",
          "links": ["40000003"]
        }
      ]
    }
  ]
}
"""

EUROPE_PMC_META_JSON = """\
{
  "resultList": {
    "result": [
      {
        "pmid": "38123456",
        "pmcid": "PMC1234567",
        "source": "MED"
      }
    ]
  }
}
"""

EUROPE_PMC_REFERENCES_JSON = """\
{"referenceList": {"reference": [{"id": "REF-1"}]}}
"""

EUROPE_PMC_CITATIONS_JSON = """\
{"citationList": {"citation": [{"id": "CITE-1"}]}}
"""

SEMANTIC_SCHOLAR_PAPER_JSON = """\
{
  "paperId": "s2-paper",
  "title": "TP53 regulates glioblastoma"
}
"""

SEMANTIC_SCHOLAR_REFERENCES_JSON = """\
{"data": [{"citedPaper": {"paperId": "s2-ref"}}]}
"""

SEMANTIC_SCHOLAR_CITATIONS_JSON = """\
{"data": [{"citingPaper": {"paperId": "s2-cite"}}]}
"""

CROSSREF_JSON = """\
{
  "message": {
    "DOI": "10.1000/test-doi",
    "reference": [{"DOI": "10.1000/ref-doi"}]
  }
}
"""

UNPAYWALL_JSON = """\
{
  "is_oa": true,
  "oa_status": "gold",
  "best_oa_location": {
    "url_for_pdf": "https://example.org/test.pdf",
    "license": "cc-by"
  }
}
"""


def _fake_urlopen(request, *args, **kwargs):
    url = request.full_url if hasattr(request, "full_url") else str(request)
    parsed = urlparse(url)

    if parsed.path.endswith("/efetch.fcgi"):
        return _FakeResponse(PUBMED_XML)
    if parsed.path.endswith("/elink.fcgi"):
        return _FakeResponse(ELINK_JSON)
    if parsed.netloc == "api.crossref.org":
        return _FakeResponse(CROSSREF_JSON)
    if parsed.netloc == "www.ebi.ac.uk":
        if parsed.path.endswith("/search"):
            return _FakeResponse(EUROPE_PMC_META_JSON)
        if parsed.path.endswith("/references"):
            return _FakeResponse(EUROPE_PMC_REFERENCES_JSON)
        if parsed.path.endswith("/citations"):
            return _FakeResponse(EUROPE_PMC_CITATIONS_JSON)
    if parsed.netloc == "api.semanticscholar.org":
        if parsed.path.endswith("/references"):
            return _FakeResponse(SEMANTIC_SCHOLAR_REFERENCES_JSON)
        if parsed.path.endswith("/citations"):
            return _FakeResponse(SEMANTIC_SCHOLAR_CITATIONS_JSON)
        return _FakeResponse(SEMANTIC_SCHOLAR_PAPER_JSON)
    if parsed.netloc == "api.unpaywall.org":
        query = parse_qs(parsed.query)
        assert query["email"] == ["annotator@example.org"]
        return _FakeResponse(UNPAYWALL_JSON)

    raise AssertionError(f"Unexpected URL requested in test: {url}")


def test_fetch_pubmed_record_parses_nested_xml_text(monkeypatch) -> None:
    monkeypatch.setenv("NCBI_EMAIL", "annotator@example.org")
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    record = fetch_pubmed_record(
        "38123456",
        enrichments=[
            "elinks",
            "crossref",
            "europe_pmc",
            "semantic_scholar",
            "unpaywall",
        ],
    )

    assert record["pmid"] == "38123456"
    assert record["title"] == "TP53 regulates glioblastoma"
    assert "BACKGROUND: TP53 is important." in record["abstract"]
    assert "U87-MG cells were evaluated." in record["abstract"]
    assert record["year"] == "2024"
    assert record["pmcid"] == "PMC1234567"
    assert record["doi"] == "10.1000/test-doi"
    assert record["journal"] == "Journal of Testing"
    assert record["journal_abbrev"] == "J Test"
    assert record["volume"] == "12"
    assert record["issue"] == "4"
    assert record["pages"] == "123-130"
    assert record["language"] == ["eng"]
    assert record["publication_type"] == ["Journal Article"]
    assert record["issn"] == "1234-5678"
    assert record["issn_type"] == "Print"
    assert record["nlm_unique_id"] == "987654"
    assert record["pub_date"] == "2024-01-01"
    assert record["epub_date"] == "2024-01-05"
    assert record["received_date"] == "2023-12-01"
    assert record["accepted_date"] == "2024-01-15"
    assert record["medline_date"] == "2024-02-02"
    assert record["entrez_date"] == "2024-02-01"
    assert record["revision_date"] == "2024-05-01"
    assert record["authors"][0]["last"] == "Smith"
    assert record["authors"][0]["orcid"] == "0000-0001-2345-6789"
    assert record["affiliations"] == ["Department of Biology, Test University"]
    assert record["keywords"] == ["TP53", "glioblastoma"]
    assert record["mesh_terms"][0]["descriptor"] == "Glioblastoma"
    assert record["mesh_terms"][0]["qualifiers"][0]["name"] == "genetics"
    assert record["chemicals"][0]["name"] == "Temozolomide"
    assert record["gene_symbols"] == ["TP53"]
    assert record["supplemental_mesh"][0]["name"] == "Supplemental Term"
    assert record["grants"][0]["grant_id"] == "R01CA123456"
    assert record["grants"][0]["acronym"] == "TEST"
    assert record["citation_status"] == ""
    assert record["owner"] == ""
    assert record["version"] == ""
    assert record["comments_corrections"][0]["pmid"] == "123456"
    assert record["data_banks"][0]["name"] == "GenBank"
    assert record["elinks"]["related_pmids"][0]["pmid"] == "40000001"
    assert record["elinks"]["cited_by_pmids"] == ["40000002"]
    assert record["elinks"]["references_pmids"] == ["40000003"]
    assert record["elinks"]["crossref_meta"]["DOI"] == "10.1000/test-doi"
    assert record["elinks"]["epmc_meta"]["pmcid"] == "PMC1234567"
    assert record["elinks"]["epmc_references"][0]["id"] == "REF-1"
    assert record["elinks"]["epmc_citations"][0]["id"] == "CITE-1"
    assert record["elinks"]["s2_paper"]["paperId"] == "s2-paper"
    assert record["elinks"]["s2_references"][0]["paperId"] == "s2-ref"
    assert record["elinks"]["s2_citations"][0]["paperId"] == "s2-cite"
    assert record["elinks"]["unpaywall"]["pdf_url"] == "https://example.org/test.pdf"


def test_fetch_pubmed_record_defaults_to_no_enrichments(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    record = fetch_pubmed_record("38123456")

    assert record["elinks"] == {}


def test_load_document_from_pmid_builds_document() -> None:
    doc = load_document_from_pmid(
        "38123456",
        fetcher=lambda pmid: {
            "pmid": pmid,
            "pmcid": "PMC1234567",
            "doi": "10.1000/test-doi",
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
    assert doc.metadata["pubmed_record"]["doi"] == "10.1000/test-doi"


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

"""Offline tests for :class:`EntrezSource`.

The colleague's ``fetch_pubmed_record`` / ``search_pubmed_pmids`` helpers do
real HTTP, so we never call them here. Instead we inject lightweight stubs
through ``EntrezSource(fetch_record=..., search_pmids=...)`` and assert on
the resulting :class:`Document` objects.
"""

from __future__ import annotations

from typing import Any

import pytest

from bio_annotation.sources import EntrezSource, FetchInput, UnsupportedInputError


def _record(
    pmid: str = "12345",
    *,
    title: str = "Sample title about PTEN",
    abstract: str = "Glioblastoma is aggressive.",
    year: str | None = "2024",
    pmcid: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "year": year,
        "pmcid": pmcid,
        "doi": "10.1000/example",
        "authors": [{"last": "Doe", "first": "Jane"}],
        "mesh_terms": [{"descriptor": "Glioblastoma"}],
        "journal": "Example Journal",
        "keywords": ["GBM", "PTEN"],
    }
    if extra:
        record.update(extra)
    return record


def _source_with_records(records: dict[str, dict[str, Any]]) -> EntrezSource:
    """Build a source whose fetch_record returns canned dicts by PMID."""

    def fake_fetch(pmid: str) -> dict[str, Any]:
        return records[pmid]

    return EntrezSource(fetch_record=fake_fetch)


def _source_with_records_and_search(
    records: dict[str, dict[str, Any]],
    pmids_for_query: list[str],
) -> EntrezSource:
    def fake_fetch(pmid: str) -> dict[str, Any]:
        return records[pmid]

    def fake_search(query: str) -> list[str]:
        assert query, "query must not be empty"
        return list(pmids_for_query)

    return EntrezSource(fetch_record=fake_fetch, search_pmids=fake_search)


def test_entrez_source_fetches_single_pmid_and_maps_core_fields() -> None:
    records = {"12345": _record(pmid="12345", pmcid="PMC9999")}
    source = _source_with_records(records)

    docs = source.fetch(FetchInput.from_pmid("12345"))

    assert len(docs) == 1
    doc = docs[0]
    assert doc.document_id == "PMID:12345"
    assert doc.pmid == "12345"
    assert doc.title == "Sample title about PTEN"
    assert doc.abstract == "Glioblastoma is aggressive."
    assert doc.year == "2024"
    assert doc.source == "entrez"
    assert doc.full_text is None
    assert doc.metadata["pmcid"] == "PMC9999"


def test_entrez_source_stashes_full_pubmed_record_in_metadata() -> None:
    records = {"12345": _record(pmid="12345")}
    source = _source_with_records(records)

    [doc] = source.fetch(FetchInput.from_pmid("12345"))

    record = doc.metadata["pubmed_record"]
    assert record["pmid"] == "12345"
    assert record["doi"] == "10.1000/example"
    assert record["authors"] == [{"last": "Doe", "first": "Jane"}]
    assert record["mesh_terms"] == [{"descriptor": "Glioblastoma"}]


def test_entrez_source_fetches_pmid_list_in_order() -> None:
    records = {
        "111": _record(pmid="111", title="First paper"),
        "222": _record(pmid="222", title="Second paper"),
        "333": _record(pmid="333", title="Third paper"),
    }
    source = _source_with_records(records)

    docs = source.fetch(FetchInput.from_pmid_list(["111", "222", "333"]))

    assert [doc.pmid for doc in docs] == ["111", "222", "333"]
    assert [doc.title for doc in docs] == ["First paper", "Second paper", "Third paper"]


def test_entrez_source_query_calls_search_then_fetches_each_pmid() -> None:
    records = {
        "777": _record(pmid="777", title="Hit one"),
        "888": _record(pmid="888", title="Hit two"),
    }
    source = _source_with_records_and_search(records, pmids_for_query=["777", "888"])

    docs = source.fetch(FetchInput.from_query("glioblastoma AND microRNA"))

    assert [doc.pmid for doc in docs] == ["777", "888"]
    assert docs[0].title == "Hit one"
    assert docs[1].title == "Hit two"


def test_entrez_source_query_with_empty_search_returns_no_documents() -> None:
    source = _source_with_records_and_search({}, pmids_for_query=[])

    docs = source.fetch(FetchInput.from_query("nonexistent_term_zzz"))

    assert docs == []


def test_entrez_source_rejects_raw_text_input() -> None:
    source = _source_with_records({})

    with pytest.raises(UnsupportedInputError):
        source.fetch(FetchInput.from_text("some pasted abstract"))


def test_entrez_source_fields_filter_keeps_requested_plus_core_fields() -> None:
    records = {"12345": _record(pmid="12345")}
    source = _source_with_records(records)

    docs = source.fetch(
        FetchInput.from_pmid(
            "12345",
            fields=frozenset({"authors", "mesh_terms"}),
        )
    )

    record = docs[0].metadata["pubmed_record"]
    assert "authors" in record
    assert "mesh_terms" in record
    # Core fields are always preserved so the Document and downstream
    # consumers stay coherent even with an aggressive filter.
    for core in ("pmid", "title", "abstract", "year"):
        assert core in record
    # And explicitly unrequested fields are dropped.
    assert "journal" not in record
    assert "doi" not in record
    assert "keywords" not in record


def test_entrez_source_no_fields_filter_keeps_full_record() -> None:
    records = {"12345": _record(pmid="12345")}
    source = _source_with_records(records)

    [doc] = source.fetch(FetchInput.from_pmid("12345"))

    record = doc.metadata["pubmed_record"]
    for key in ("pmid", "title", "abstract", "year", "doi", "authors",
                "mesh_terms", "journal", "keywords", "pmcid"):
        assert key in record


def test_entrez_source_propagates_fetch_errors() -> None:
    def boom(pmid: str) -> dict[str, Any]:
        raise ValueError(f"PMID {pmid} not found in PubMed response.")

    source = EntrezSource(fetch_record=boom)

    with pytest.raises(ValueError, match="not found"):
        source.fetch(FetchInput.from_pmid("99999999"))


def test_entrez_source_skips_record_when_fetch_returns_non_dict() -> None:
    def returns_none(pmid: str) -> Any:
        return None

    source = EntrezSource(fetch_record=returns_none)

    docs = source.fetch(FetchInput.from_pmid_list(["111", "222"]))

    assert docs == []


def test_entrez_source_uses_request_pmid_when_record_missing_pmid() -> None:
    records = {"55555": {"title": "T", "abstract": "A", "year": "2020"}}
    source = _source_with_records(records)

    [doc] = source.fetch(FetchInput.from_pmid("55555"))

    assert doc.pmid == "55555"
    assert doc.document_id == "PMID:55555"


def test_entrez_source_advertises_supported_inputs_and_fields() -> None:
    source = EntrezSource()

    assert source.name == "entrez"
    assert source.supported_inputs == frozenset({"pmid", "pmid_list", "query"})
    # A few representative fields the colleague's parser actually emits.
    for field_name in ("pmid", "pmcid", "doi", "title", "abstract", "year",
                       "authors", "mesh_terms", "journal", "keywords"):
        assert field_name in source.fields_provided

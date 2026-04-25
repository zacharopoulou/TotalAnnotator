"""Unit tests for ``RawTextSource``."""

from __future__ import annotations

import pytest

from bio_annotation.sources import FetchInput, RawTextSource, UnsupportedInputError


def test_raw_text_source_wraps_text_in_document() -> None:
    source = RawTextSource()
    request = FetchInput.from_text("PTEN regulates apoptosis.", text_id="RAW:7")

    docs = source.fetch(request)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.document_id == "RAW:7"
    assert doc.pmid is None
    assert doc.title == ""
    assert doc.abstract == "PTEN regulates apoptosis."
    assert doc.full_text is None
    assert doc.source == "raw_text"
    assert doc.metadata == {}


def test_raw_text_source_uses_default_text_id_when_omitted() -> None:
    source = RawTextSource()
    request = FetchInput.from_text("hello world")

    [doc] = source.fetch(request)

    assert doc.document_id == "RAW:1"


def test_raw_text_source_strips_whitespace_around_text() -> None:
    source = RawTextSource()
    request = FetchInput.from_text("  hello  ")

    [doc] = source.fetch(request)

    assert doc.abstract == "hello"


def test_raw_text_source_rejects_pmid_input() -> None:
    source = RawTextSource()

    with pytest.raises(UnsupportedInputError):
        source.fetch(FetchInput.from_pmid("12345"))


def test_raw_text_source_rejects_query_input() -> None:
    source = RawTextSource()

    with pytest.raises(UnsupportedInputError):
        source.fetch(FetchInput.from_query("brain tumor"))


def test_raw_text_source_advertises_supported_inputs() -> None:
    source = RawTextSource()
    assert source.supported_inputs == frozenset({"raw_text"})
    assert source.fields_provided == frozenset({"abstract"})
    assert source.name == "raw_text"

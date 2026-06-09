from __future__ import annotations

import pytest

from bio_annotation.fetch.input import (
    FetchInput,
    FetchKind,
    FetchSource,
    UnsupportedInputError,
    _normalize_pmcid,
    check_supports,
    sources_for_field,
)


# A. FetchInput constructors

def test_from_pmid_strips_and_sets_kind() -> None:
    request = FetchInput.from_pmid("  36403686  ")
    assert request.kind == "pmid"
    assert request.pmids == ("36403686",)


def test_from_pmid_rejects_empty() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        FetchInput.from_pmid("   ")


def test_from_pmid_list_strips_and_drops_blanks() -> None:
    request = FetchInput.from_pmid_list(["  36403686 ", "", "12345678"])
    assert request.kind == "pmid_list"
    assert request.pmids == ("36403686", "12345678")


def test_from_pmid_list_rejects_all_empty() -> None:
    with pytest.raises(ValueError, match="at least one non-empty"):
        FetchInput.from_pmid_list(["", "  "])


def test_from_pmcid_normalizes_input() -> None:
    request = FetchInput.from_pmcid("7083241")
    assert request.kind == "pmcid"
    assert request.pmcids == ("PMC7083241",)


def test_from_pmcid_list_normalizes_each_value() -> None:
    request = FetchInput.from_pmcid_list(["pmc:7083241", "PMC1234567"])
    assert request.kind == "pmcid_list"
    assert request.pmcids == ("PMC7083241", "PMC1234567")


# B. _normalize_pmcid helper

@pytest.mark.parametrize(
    "value, expected",
    [
        ("7083241", "PMC7083241"),
        ("PMC7083241", "PMC7083241"),
        ("pmc7083241", "PMC7083241"),
        ("pmc:7083241", "PMC7083241"),
        ("PMC:7083241", "PMC7083241"),
        ("  PMC1234567  ", "PMC1234567"),
    ],
)
def test_normalize_pmcid_accepted_forms(value: str, expected: str) -> None:
    assert _normalize_pmcid(value) == expected


def test_normalize_pmcid_rejects_non_digit() -> None:
    with pytest.raises(ValueError, match="PMC<digits>"):
        _normalize_pmcid("PMCabc")


def test_normalize_pmcid_rejects_empty() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        _normalize_pmcid("   ")


# C. fields_for lookup

def test_fields_for_per_source_beats_global() -> None:
    request = FetchInput.from_pmid(
        "1",
        fields=frozenset({"title", "abstract"}),
        fields_per_source={"entrez": frozenset({"mesh_terms"})},
    )
    assert request.fields_for("entrez") == frozenset({"mesh_terms"})
    assert request.fields_for("pubtator3") == frozenset({"title", "abstract"})


def test_fields_for_returns_none_when_neither_set() -> None:
    request = FetchInput.from_pmid("1")
    assert request.fields_for("entrez") is None


# D. FetchSource protocol and check_supports

class _DummySource:
    name = "dummy"
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid"})
    fields_provided: frozenset[str] = frozenset({"pmid"})

    def fetch(self, request: FetchInput) -> list:
        return []


def test_check_supports_passes_for_supported_kind() -> None:
    check_supports(_DummySource(), FetchInput.from_pmid("1"))


def test_check_supports_raises_for_wrong_kind() -> None:
    with pytest.raises(UnsupportedInputError, match="does not support"):
        check_supports(_DummySource(), FetchInput.from_pmcid("PMC1"))


def test_dummy_source_is_a_fetch_source() -> None:
    assert isinstance(_DummySource(), FetchSource)


# E. sources_for_field catalog lookup

def test_sources_for_field_mesh_terms() -> None:
    assert sources_for_field("mesh_terms") == ["entrez", "europe_pmc"]


def test_sources_for_field_full_text() -> None:
    assert sources_for_field("full_text") == ["europe_pmc", "pubtator3"]


def test_sources_for_field_unknown_returns_empty() -> None:
    assert sources_for_field("nonexistent_field") == []


# F. Regression: raw_text was dropped from FetchKind / FetchInput

def test_fetch_input_has_no_from_text_classmethod() -> None:
    assert not hasattr(FetchInput, "from_text")

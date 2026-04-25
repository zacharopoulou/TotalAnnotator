from __future__ import annotations

import pytest

from bio_annotation.ui.inputs import (
    INPUT_MODE_LABELS,
    build_fetch_input,
    parse_pmcid_list,
    parse_pmid_list,
)


def test_parse_pmid_list_splits_on_commas_whitespace_and_newlines() -> None:
    text = "1, 2 3\n4;5\t6"
    assert parse_pmid_list(text) == ["1", "2", "3", "4", "5", "6"]


def test_parse_pmid_list_deduplicates_preserving_first_seen_order() -> None:
    assert parse_pmid_list("3 1 2 1 3 4") == ["3", "1", "2", "4"]


def test_parse_pmid_list_returns_empty_for_blank_input() -> None:
    assert parse_pmid_list("") == []
    assert parse_pmid_list("   \n\t ") == []


def test_parse_pmcid_list_keeps_prefix_for_source_to_normalise() -> None:
    text = "PMC1\npmc:2 3"
    assert parse_pmcid_list(text) == ["PMC1", "pmc:2", "3"]


def test_build_fetch_input_pmid_returns_fetch_input_with_normalised_pmid() -> None:
    request = build_fetch_input(mode="pmid", single_pmid=" 36403686 ")
    assert request.kind == "pmid"
    assert request.pmids == ("36403686",)
    assert request.fields is None


def test_build_fetch_input_pmid_passes_through_fields_filter() -> None:
    request = build_fetch_input(
        mode="pmid",
        single_pmid="123",
        fields=frozenset({"mesh_terms"}),
    )
    assert request.fields == frozenset({"mesh_terms"})


def test_build_fetch_input_passes_through_per_source_filters() -> None:
    request = build_fetch_input(
        mode="pmid",
        single_pmid="123",
        fields_per_source={
            "entrez": frozenset({"mesh_terms", "authors"}),
            "europe_pmc": frozenset({"is_open_access"}),
        },
    )
    assert request.fields is None
    assert request.fields_per_source == {
        "entrez": frozenset({"mesh_terms", "authors"}),
        "europe_pmc": frozenset({"is_open_access"}),
    }


def test_build_fetch_input_per_source_overrides_global_for_named_sources() -> None:
    request = build_fetch_input(
        mode="pmid",
        single_pmid="123",
        fields=frozenset({"journal"}),
        fields_per_source={"entrez": frozenset({"mesh_terms"})},
    )
    assert request.fields_for("entrez") == frozenset({"mesh_terms"})
    assert request.fields_for("europe_pmc") == frozenset({"journal"})
    assert request.fields_for("pubtator3") == frozenset({"journal"})


def test_build_fetch_input_per_source_empty_set_means_keep_only_core() -> None:
    request = build_fetch_input(
        mode="pmid",
        single_pmid="123",
        fields_per_source={"entrez": frozenset()},
    )
    assert request.fields_for("entrez") == frozenset()
    assert request.fields_for("europe_pmc") is None


def test_build_fetch_input_pmid_list_parses_and_deduplicates() -> None:
    request = build_fetch_input(mode="pmid_list", pmid_list_text="1,2,2,3")
    assert request.kind == "pmid_list"
    assert request.pmids == ("1", "2", "3")


def test_build_fetch_input_pmcid_normalises_to_pmc_prefix() -> None:
    request = build_fetch_input(mode="pmcid", single_pmcid="9876543")
    assert request.kind == "pmcid"
    assert request.pmcids == ("PMC9876543",)


def test_build_fetch_input_pmcid_list_normalises_each_value() -> None:
    request = build_fetch_input(
        mode="pmcid_list",
        pmcid_list_text="PMC1, pmc:2, 3",
    )
    assert request.kind == "pmcid_list"
    assert request.pmcids == ("PMC1", "PMC2", "PMC3")


def test_build_fetch_input_query_strips_whitespace() -> None:
    request = build_fetch_input(mode="query", query="  microRNA glioblastoma  ")
    assert request.kind == "query"
    assert request.query == "microRNA glioblastoma"


def test_build_fetch_input_raw_text_uses_default_text_id_when_blank() -> None:
    request = build_fetch_input(mode="raw_text", raw_text="hello world", raw_text_id="")
    assert request.kind == "raw_text"
    assert request.text == "hello world"
    assert request.text_id == "RAW:1"


def test_build_fetch_input_raw_text_uses_explicit_text_id() -> None:
    request = build_fetch_input(
        mode="raw_text",
        raw_text="hello",
        raw_text_id="DOC:42",
    )
    assert request.text_id == "DOC:42"


@pytest.mark.parametrize(
    "mode,kwargs,expected_message_fragment",
    [
        ("pmid", {"single_pmid": "  "}, "PMID"),
        ("pmid_list", {"pmid_list_text": ""}, "at least one PMID"),
        ("pmcid", {"single_pmcid": ""}, "PMCID"),
        ("pmcid_list", {"pmcid_list_text": "   "}, "at least one PMCID"),
        ("query", {"query": ""}, "query"),
        ("raw_text", {"raw_text": "\n\t"}, "text"),
    ],
)
def test_build_fetch_input_raises_value_error_for_blank_input(
    mode: str,
    kwargs: dict,
    expected_message_fragment: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message_fragment):
        build_fetch_input(mode=mode, **kwargs)  # type: ignore[arg-type]


def test_build_fetch_input_unknown_mode_raises() -> None:
    with pytest.raises(ValueError, match="Unknown input mode"):
        build_fetch_input(mode="bogus")  # type: ignore[arg-type]


def test_input_mode_labels_cover_all_supported_modes() -> None:
    expected = {"pmid", "pmid_list", "pmcid", "pmcid_list", "query", "raw_text"}
    assert set(INPUT_MODE_LABELS) == expected

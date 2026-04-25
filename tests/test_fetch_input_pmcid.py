"""Tests for the new PMCID factories on :class:`FetchInput`."""

from __future__ import annotations

import pytest

from bio_annotation.sources import FetchInput


def test_from_pmcid_accepts_canonical_prefixed_form() -> None:
    request = FetchInput.from_pmcid("PMC9876")

    assert request.kind == "pmcid"
    assert request.pmcids == ("PMC9876",)


def test_from_pmcid_normalizes_bare_digits_with_pmc_prefix() -> None:
    request = FetchInput.from_pmcid("9876")

    assert request.pmcids == ("PMC9876",)


def test_from_pmcid_strips_pmc_colon_prefix() -> None:
    request = FetchInput.from_pmcid("pmc:42")

    assert request.pmcids == ("PMC42",)


def test_from_pmcid_rejects_non_numeric_payload() -> None:
    with pytest.raises(ValueError, match="PMC<digits>"):
        FetchInput.from_pmcid("PMCabc")


def test_from_pmcid_rejects_empty_string() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        FetchInput.from_pmcid("   ")


def test_from_pmcid_list_normalizes_each_value() -> None:
    request = FetchInput.from_pmcid_list(["PMC1", "2", "pmc:3"])

    assert request.kind == "pmcid_list"
    assert request.pmcids == ("PMC1", "PMC2", "PMC3")


def test_from_pmcid_list_rejects_all_blank_input() -> None:
    with pytest.raises(ValueError, match="at least one"):
        FetchInput.from_pmcid_list(["", "   "])

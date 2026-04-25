"""Pure helpers for turning raw user input into a :class:`FetchInput`.

Streamlit widget callbacks return raw strings. These helpers normalise that
input (splitting PMID lists on commas / whitespace / newlines, stripping
PMCID prefixes, dropping empty values) and build the canonical request
object that every :class:`FetchSource` understands. Keeping this logic out
of the Streamlit module makes it trivially unit-testable without spinning
up a Streamlit runtime.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Literal

from bio_annotation.sources.base import FetchInput


InputMode = Literal[
    "pmid",
    "pmid_list",
    "pmcid",
    "pmcid_list",
    "query",
    "raw_text",
]

INPUT_MODE_LABELS: dict[InputMode, str] = {
    "pmid": "Single PMID",
    "pmid_list": "List of PMIDs",
    "pmcid": "Single PMCID",
    "pmcid_list": "List of PMCIDs",
    "query": "PubMed query",
    "raw_text": "Paste raw text",
}

_SPLIT_RE = re.compile(r"[\s,;]+")


def parse_pmid_list(text: str) -> list[str]:
    """Split a free-form text blob into a deduplicated list of PMIDs.

    Splits on commas, semicolons, and any whitespace (so newline-separated
    pastes work). Drops empty fragments and preserves first-seen order.
    Does not validate that each fragment is numeric; the source layer
    surfaces meaningful errors when an invalid PMID hits the API.
    """

    return _split_unique(text)


def parse_pmcid_list(text: str) -> list[str]:
    """Split a free-form text blob into a deduplicated list of PMCID-like values.

    Performs no normalisation of the ``PMC`` prefix; that is handled inside
    :class:`FetchInput.from_pmcid_list` so the rules stay in one place.
    """

    return _split_unique(text)


def _split_unique(text: str) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for token in _SPLIT_RE.split(text.strip()):
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return cleaned


def build_fetch_input(
    *,
    mode: InputMode,
    single_pmid: str = "",
    pmid_list_text: str = "",
    single_pmcid: str = "",
    pmcid_list_text: str = "",
    query: str = "",
    raw_text: str = "",
    raw_text_id: str = "RAW:1",
    fields: frozenset[str] | None = None,
    fields_per_source: Mapping[str, frozenset[str]] | None = None,
) -> FetchInput:
    """Build a :class:`FetchInput` from raw widget values.

    ``fields`` is a single global filter applied to every source.
    ``fields_per_source`` overrides that for specific sources, e.g.
    ``{"entrez": frozenset({"mesh_terms"}), "europe_pmc": frozenset({"is_open_access"})}``;
    a source listed in this mapping uses **its own** slice instead of
    ``fields``, which is what powers strict per-source filtering in the UI.

    Raises :class:`ValueError` if the input for the chosen mode is empty.
    The error messages are user-facing strings the Streamlit app can show
    in a ``st.error`` banner without further wrapping.
    """

    common = {"fields": fields, "fields_per_source": fields_per_source}

    if mode == "pmid":
        if not single_pmid.strip():
            raise ValueError("Enter a PMID to fetch.")
        return FetchInput.from_pmid(single_pmid, **common)

    if mode == "pmid_list":
        pmids = parse_pmid_list(pmid_list_text)
        if not pmids:
            raise ValueError(
                "Enter at least one PMID, separated by commas, spaces, or new lines."
            )
        return FetchInput.from_pmid_list(pmids, **common)

    if mode == "pmcid":
        if not single_pmcid.strip():
            raise ValueError("Enter a PMCID to fetch.")
        return FetchInput.from_pmcid(single_pmcid, **common)

    if mode == "pmcid_list":
        pmcids = parse_pmcid_list(pmcid_list_text)
        if not pmcids:
            raise ValueError(
                "Enter at least one PMCID, separated by commas, spaces, or new lines."
            )
        return FetchInput.from_pmcid_list(pmcids, **common)

    if mode == "query":
        if not query.strip():
            raise ValueError("Enter a PubMed query expression.")
        return FetchInput.from_query(query, **common)

    if mode == "raw_text":
        if not raw_text.strip():
            raise ValueError("Paste some text to annotate.")
        return FetchInput.from_text(raw_text, text_id=raw_text_id or "RAW:1")

    raise ValueError(f"Unknown input mode {mode!r}.")

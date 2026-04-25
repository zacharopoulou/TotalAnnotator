"""Pluggable fetch sources for the unified TotalAnnotator pipeline.

Each source implements the :class:`FetchSource` protocol and converts a
:class:`FetchInput` (a single PMID, a list, a PubMed query, or pasted raw
text) into ``Document`` objects that downstream annotators can consume.

The four built-in sources are:

* ``EntrezSource``      - rich PubMed metadata via NCBI E-utilities
* ``EuropePmcSource``   - citations, OA flags, JATS full text via Europe PMC
* ``PubTator3Source``   - title/abstract plus pre-computed entity annotations
* ``RawTextSource``     - wraps user-pasted text, no network call

Sources are intentionally implementation-agnostic: the orchestrator picks
which one(s) to run for a given request, and the UI renders them as
selectable options.
"""

from bio_annotation.sources.base import (
    FetchInput,
    FetchKind,
    FetchSource,
    UnsupportedInputError,
    check_supports,
)
from bio_annotation.sources.entrez import EntrezSource
from bio_annotation.sources.pubtator3 import PubTator3Source
from bio_annotation.sources.raw_text import RawTextSource

__all__ = [
    "EntrezSource",
    "FetchInput",
    "FetchKind",
    "FetchSource",
    "PubTator3Source",
    "RawTextSource",
    "UnsupportedInputError",
    "check_supports",
]

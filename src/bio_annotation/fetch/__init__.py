"""Resolve PMIDs, PMCIDs, queries, or raw text into :class:`~bio_annotation.schemas.document.Document`.

:class:`FetchOrchestrator` selects one source (first match) or merges several when
``prefer`` names multiple backends. :func:`default_fetch_orchestrator` registers
PubTator3, Entrez, Europe PMC, and raw text in that order. :class:`PubtatorFirstOrchestrator`
is a separate helper that always runs PubTator3 then selectively calls Entrez for
gaps; the default pipeline uses :func:`default_fetch_orchestrator` instead unless
you pass a custom ``orchestrator_factory``.
"""

from bio_annotation.fetch.fields import (
    ENTREZ_FIELDS,
    EUROPE_PMC_FIELDS,
    FIELD_OWNERS,
    PUBTATOR3_FIELDS,
    sources_for_field,
)
from bio_annotation.fetch.input import (
    FetchInput,
    FetchKind,
    FetchSource,
    UnsupportedInputError,
    check_supports,
)
from bio_annotation.fetch.orchestrator import (
    FetchOrchestrator,
    PubtatorFirstOrchestrator,
    SourceNotFoundError,
    default_fetch_orchestrator,
)
from bio_annotation.clients import EntrezClient, EuropePmcClient, PubTator3Client
from bio_annotation.fetch.adapters import (
    EntrezSource,
    EuropePmcSource,
    PubTator3Source,
    RawTextSource,
)
from bio_annotation.fetch.unite import unite_into

__all__ = [
    "ENTREZ_FIELDS",
    "EUROPE_PMC_FIELDS",
    "FIELD_OWNERS",
    "EntrezClient",
    "EntrezSource",
    "EuropePmcClient",
    "EuropePmcSource",
    "PubTator3Client",
    "default_fetch_orchestrator",
    "FetchInput",
    "FetchKind",
    "FetchOrchestrator",
    "FetchSource",
    "PubTator3Source",
    "RawTextSource",
    "PubtatorFirstOrchestrator",
    "PUBTATOR3_FIELDS",
    "SourceNotFoundError",
    "UnsupportedInputError",
    "check_supports",
    "sources_for_field",
    "unite_into",
]

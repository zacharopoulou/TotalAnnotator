"""Public surface of the fetch package: re-exports of inputs, sources, and the orchestrator."""

from bio_annotation.clients import EntrezClient, EuropePmcClient, PubTator3Client
from bio_annotation.fetch.entrez import EntrezSource
from bio_annotation.fetch.europe_pmc import EuropePmcSource
from bio_annotation.fetch.input import (
    ENTREZ_FIELDS,
    EUROPE_PMC_FIELDS,
    FIELD_OWNERS,
    PUBTATOR3_FIELDS,
    FetchInput,
    FetchKind,
    FetchSource,
    UnsupportedInputError,
    check_supports,
    sources_for_field,
)
from bio_annotation.fetch.orchestrator import (
    FetchOrchestrator,
    PubtatorFirstOrchestrator,
    SourceNotFoundError,
    default_fetch_orchestrator,
    unite_into,
)
from bio_annotation.fetch.pubtator3 import PubTator3Source

__all__ = [
    "ENTREZ_FIELDS",
    "EUROPE_PMC_FIELDS",
    "EntrezClient",
    "EntrezSource",
    "EuropePmcClient",
    "EuropePmcSource",
    "FetchInput",
    "FetchKind",
    "FetchOrchestrator",
    "FetchSource",
    "FIELD_OWNERS",
    "PubTator3Client",
    "PubTator3Source",
    "PubtatorFirstOrchestrator",
    "PUBTATOR3_FIELDS",
    "SourceNotFoundError",
    "UnsupportedInputError",
    "check_supports",
    "sources_for_field",
    "unite_into",
]

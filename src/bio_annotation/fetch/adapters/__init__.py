"""Adapters: external APIs → :class:`~bio_annotation.schemas.document.Document`.

Uses :mod:`bio_annotation.clients` for HTTP where needed; orchestration in
:mod:`bio_annotation.fetch.orchestrator`.
"""

from bio_annotation.fetch.adapters.entrez import EntrezSource
from bio_annotation.fetch.adapters.europe_pmc import EuropePmcSource
from bio_annotation.fetch.adapters.pubtator3 import PubTator3Source
from bio_annotation.fetch.adapters.raw_text import RawTextSource

__all__ = ["EntrezSource", "EuropePmcSource", "PubTator3Source", "RawTextSource"]

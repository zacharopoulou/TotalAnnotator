"""HTTP clients for external services (PubTator3, Europe PMC, …)."""

from __future__ import annotations

from bio_annotation.clients.entrez import EntrezClient
from bio_annotation.clients.europe_pmc import EuropePmcClient
from bio_annotation.clients.pubtator3 import PubTator3Client

__all__ = ["EntrezClient", "EuropePmcClient", "PubTator3Client"]

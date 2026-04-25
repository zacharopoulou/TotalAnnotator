"""HTTP clients for external annotator services."""

from __future__ import annotations

from bio_annotation.clients.europe_pmc import EuropePmcClient
from bio_annotation.clients.pubtator3 import PubTator3Client

__all__ = ["EuropePmcClient", "PubTator3Client"]

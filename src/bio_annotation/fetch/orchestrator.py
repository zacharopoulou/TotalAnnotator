"""Source selection, merge (unite_into), and default orchestrator wiring."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from bio_annotation.fetch.entrez import EntrezSource
from bio_annotation.fetch.europe_pmc import EuropePmcSource
from bio_annotation.fetch.input import (
    FetchInput,
    FetchKind,
    FetchSource,
    UnsupportedInputError,
)
from bio_annotation.fetch.pubtator3 import PubTator3Source
from bio_annotation.schemas.document import Document

logger = logging.getLogger(__name__)


# A. Merge helper

def unite_into(base: Document, extra: Document) -> None:
    """Merge *extra* into *base* in place; *base* wins on non-empty conflicts."""

    if not base.title.strip() and extra.title.strip():
        base.title = extra.title
    if not base.abstract.strip() and extra.abstract.strip():
        base.abstract = extra.abstract
    if not base.full_text and extra.full_text:
        base.full_text = extra.full_text
    if not base.year and extra.year:
        base.year = extra.year
    if not base.pmid and extra.pmid:
        base.pmid = extra.pmid
    for key, value in extra.metadata.items():
        if key == "origin_sources":
            continue
        base.metadata.setdefault(key, value)


# B. Orchestrators

class SourceNotFoundError(KeyError):
    """Raised when a requested source name is not registered."""


@dataclass(slots=True)
class FetchOrchestrator:
    """Select one or more registered :class:`FetchSource` implementations."""

    sources: list[FetchSource]

    def __post_init__(self) -> None:
        names = [s.name for s in self.sources]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(
                f"Duplicate source names registered: {duplicates}. "
                "Each source must have a unique 'name' attribute."
            )

    def names(self) -> list[str]:
        return [s.name for s in self.sources]

    def get(self, name: str) -> FetchSource:
        for source in self.sources:
            if source.name == name:
                return source
        raise SourceNotFoundError(
            f"No source named {name!r}. Available: {self.names()}."
        )

    def available_sources(self, request: FetchInput) -> list[str]:
        return [s.name for s in self.sources if request.kind in s.supported_inputs]

    def fetch(
        self,
        request: FetchInput,
        *,
        prefer: str | Iterable[str] | None = None,
        strict: bool = True,
    ) -> list[Document]:
        selected = self._select(request, prefer)
        if not selected:
            raise UnsupportedInputError(
                f"No registered source supports input kind {request.kind!r}. "
                f"Registered sources: {self.names()}."
            )
        if len(selected) == 1:
            return selected[0].fetch(request)
        return self._fetch_and_merge(request, selected, strict=strict)

    def _select(
        self,
        request: FetchInput,
        prefer: str | Iterable[str] | None,
    ) -> list[FetchSource]:
        if prefer is None:
            for source in self.sources:
                if request.kind in source.supported_inputs:
                    return [source]
            return []

        if isinstance(prefer, str):
            source = self.get(prefer)
            if request.kind not in source.supported_inputs:
                raise UnsupportedInputError(
                    f"Source {prefer!r} does not support input kind "
                    f"{request.kind!r}. Supported: {sorted(source.supported_inputs)}."
                )
            return [source]

        seen: set[str] = set()
        chain: list[FetchSource] = []
        for name in prefer:
            if name in seen:
                continue
            seen.add(name)
            source = self.get(name)
            if request.kind not in source.supported_inputs:
                raise UnsupportedInputError(
                    f"Source {name!r} does not support input kind "
                    f"{request.kind!r}. Supported: {sorted(source.supported_inputs)}."
                )
            chain.append(source)
        if not chain:
            raise ValueError("prefer iterable must name at least one source.")
        return chain

    def _fetch_and_merge(
        self,
        request: FetchInput,
        sources: list[FetchSource],
        *,
        strict: bool,
    ) -> list[Document]:
        merged: dict[str, Document] = {}
        order: list[str] = []
        origins: dict[str, list[str]] = {}

        for source in sources:
            try:
                results = source.fetch(request)
            except Exception as exc:
                if strict:
                    raise
                logger.warning(
                    "source %s failed during merged fetch: %s",
                    source.name,
                    exc,
                )
                continue
            for doc in results:
                if doc.document_id in merged:
                    unite_into(merged[doc.document_id], doc)
                else:
                    merged[doc.document_id] = doc
                    order.append(doc.document_id)
                origins.setdefault(doc.document_id, []).append(source.name)

        for doc_id, contributing in origins.items():
            merged[doc_id].metadata["origin_sources"] = contributing

        return [merged[doc_id] for doc_id in order]


def _blank_body(document: Document) -> bool:
    return (
        not document.title.strip()
        and not document.abstract.strip()
        and not (document.full_text or "").strip()
    )


@dataclass(slots=True)
class PubtatorFirstOrchestrator:
    """PubTator3 first; Entrez fills missing PMIDs and empty bodies. Unused by default loader."""

    pubtator: FetchSource
    entrez: FetchSource

    def fetch(self, request: FetchInput) -> list[Document]:
        pt_docs = self.pubtator.fetch(request)
        kind: FetchKind = request.kind

        if kind in {"pmcid", "pmcid_list"}:
            return pt_docs

        if kind == "query":
            if not pt_docs:
                return self.entrez.fetch(request)
            out = list(pt_docs)
            for doc in out:
                if doc.pmid and _blank_body(doc):
                    try:
                        entrez_docs = self.entrez.fetch(FetchInput.from_pmid(doc.pmid))
                        if entrez_docs:
                            unite_into(doc, entrez_docs[0])
                    except Exception as exc:
                        logger.warning("entrez fallback failed for PMID %s: %s", doc.pmid, exc)
            return out

        # pmid / pmid_list
        requested = set(request.pmids)
        by_pmid = {d.pmid: d for d in pt_docs if d.pmid}
        missing_pmids = requested - set(by_pmid.keys())

        for pmid in sorted(missing_pmids):
            try:
                extra = self.entrez.fetch(FetchInput.from_pmid(pmid))
                if extra:
                    pt_docs.append(extra[0])
                    by_pmid[pmid] = extra[0]
            except Exception as exc:
                logger.warning("entrez fallback failed for missing PMID %s: %s", pmid, exc)

        for doc in pt_docs:
            if doc.pmid and _blank_body(doc):
                try:
                    extras = self.entrez.fetch(FetchInput.from_pmid(doc.pmid))
                    if extras:
                        unite_into(doc, extras[0])
                except Exception as exc:
                    logger.warning("entrez fallback failed for PMID %s: %s", doc.pmid, exc)

        return pt_docs


# C. Default wiring

def default_fetch_orchestrator() -> FetchOrchestrator:
    """Default orchestrator with PubTator3, Entrez, Europe PMC in that order."""

    return FetchOrchestrator(
        sources=[
            PubTator3Source(),
            EntrezSource(),
            EuropePmcSource(),
        ]
    )


__all__ = [
    "FetchOrchestrator",
    "PubtatorFirstOrchestrator",
    "SourceNotFoundError",
    "default_fetch_orchestrator",
    "unite_into",
]

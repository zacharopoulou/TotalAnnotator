"""User-facing facade that selects and chains :class:`FetchSource` instances.

The orchestrator is the layer the Streamlit UI (and any future CLI) talks to.
A user picks an input (single PMID, PMID list, PMCID, PMCID list, PubMed
query, or raw text) and then either:

* lets the orchestrator auto-pick a source (the first registered source that
  supports the input kind),
* names a single source explicitly via ``prefer="europe_pmc"``, or
* names a chain of sources via ``prefer=["europe_pmc", "pubtator3"]`` in
  which case every source in the chain is queried and their results are
  merged by :attr:`Document.document_id` so each article ends up with one
  Document carrying enrichment from every contributing source.

Source registration is order-sensitive. For auto-pick the first matching
source wins; for the introspection helpers (:meth:`names`,
:meth:`available_sources`) the order is preserved as registered. The UI is
expected to control the order to reflect user preference.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import (
    FetchInput,
    FetchSource,
    UnsupportedInputError,
)


logger = logging.getLogger(__name__)


class SourceNotFoundError(KeyError):
    """Raised when a requested source name is not registered."""


@dataclass(slots=True)
class FetchOrchestrator:
    """Pick and optionally chain sources for a single :class:`FetchInput`."""

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
        """Return registered source names in the order they were registered."""
        return [s.name for s in self.sources]

    def get(self, name: str) -> FetchSource:
        """Look up a registered source by name; raise if missing."""
        for source in self.sources:
            if source.name == name:
                return source
        raise SourceNotFoundError(
            f"No source named {name!r}. Available: {self.names()}."
        )

    def available_sources(self, request: FetchInput) -> list[str]:
        """Return names of registered sources that can handle *request*."""
        return [
            s.name for s in self.sources if request.kind in s.supported_inputs
        ]

    def fetch(
        self,
        request: FetchInput,
        *,
        prefer: str | Iterable[str] | None = None,
        strict: bool = True,
    ) -> list[Document]:
        """Fetch documents using one or more registered sources.

        Args:
            request: what to fetch.
            prefer: ``None`` for auto-pick (first registered source that
                supports ``request.kind``), a single name for explicit
                single-source mode, or an iterable of names for merge mode.
            strict: in merge mode, when ``False``, per-source exceptions are
                logged and skipped instead of propagated. Has no effect in
                single-source mode.

        Returns:
            List of :class:`Document` objects, deduplicated by
            ``document_id`` when more than one source contributes.
        """

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
                    self._merge_into(merged[doc.document_id], doc)
                else:
                    merged[doc.document_id] = doc
                    order.append(doc.document_id)
                origins.setdefault(doc.document_id, []).append(source.name)

        for doc_id, contributing in origins.items():
            merged[doc_id].metadata["origin_sources"] = contributing

        return [merged[doc_id] for doc_id in order]

    @staticmethod
    def _merge_into(base: Document, extra: Document) -> None:
        """Fill blank top-level fields and union metadata, base wins on conflict."""
        if not base.title and extra.title:
            base.title = extra.title
        if not base.abstract and extra.abstract:
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


__all__ = ["FetchOrchestrator", "SourceNotFoundError"]

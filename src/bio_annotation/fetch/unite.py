"""Merge two :class:`~bio_annotation.schemas.document.Document` values that describe the same article.

:func:`unite_into` is used when the fetch layer has **already decided** two results
belong to the same ``document_id`` (for example after PubTator3 and Entrez both
returned a PMID). It **mutates** the first document: copy over only what the base
still lacks (empty title/abstract/full_text/year/pmid), and **add** metadata keys
from the second document without overwriting existing keys (so e.g. PubTator’s
``pubtator3_payload`` stays, and Entrez can add ``pubmed_record``). The
``origin_sources`` key is skipped so the orchestrator can set it from the merge plan.
"""

from __future__ import annotations

from bio_annotation.schemas.document import Document


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


__all__ = ["unite_into"]

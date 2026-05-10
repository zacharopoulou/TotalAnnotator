from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Iterable

import pytest

from bio_annotation.fetch.input import (
    FetchInput,
    FetchKind,
    UnsupportedInputError,
)
from bio_annotation.fetch.orchestrator import (
    FetchOrchestrator,
    SourceNotFoundError,
    default_fetch_orchestrator,
    unite_into,
)
from bio_annotation.schemas.document import Document


# A. Stubs

@dataclass(slots=True)
class _StubSource:
    name: str
    documents: list[Document] = field(default_factory=list)
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid", "pmid_list"})
    fields_provided: frozenset[str] = frozenset({"title", "abstract"})

    def fetch(self, request: FetchInput) -> list[Document]:
        return [copy.deepcopy(d) for d in self.documents]


def _doc(
    pmid: str,
    *,
    title: str = "",
    abstract: str = "",
    full_text: str | None = None,
    year: str | None = None,
    source: str = "stub",
    metadata: dict | None = None,
) -> Document:
    return Document(
        document_id=f"PMID:{pmid}",
        pmid=pmid,
        title=title,
        abstract=abstract,
        full_text=full_text,
        year=year,
        source=source,
        metadata=metadata if metadata is not None else {},
    )


# B. default_fetch_orchestrator

def test_default_orchestrator_registers_three_sources() -> None:
    orch = default_fetch_orchestrator()
    assert orch.names() == ["pubtator3", "entrez", "europe_pmc"]


def test_default_orchestrator_excludes_raw_text() -> None:
    orch = default_fetch_orchestrator()
    assert "raw_text" not in orch.names()


# C. FetchOrchestrator.fetch — single source

def test_single_source_fetch_returns_source_results() -> None:
    docs = [_doc("1", title="from a", source="a")]
    orch = FetchOrchestrator(sources=[_StubSource("a", documents=docs)])
    out = orch.fetch(FetchInput.from_pmid("1"), prefer="a")
    assert len(out) == 1
    assert out[0].title == "from a"


def test_single_source_fetch_no_prefer_picks_first_supporting() -> None:
    a = _StubSource("a", documents=[_doc("1", title="from a")])
    b = _StubSource("b", documents=[_doc("1", title="from b")])
    orch = FetchOrchestrator(sources=[a, b])
    out = orch.fetch(FetchInput.from_pmid("1"))
    assert out[0].title == "from a"


# D. FetchOrchestrator.fetch — multi-source merge

def test_multi_source_merges_into_single_document() -> None:
    a = _StubSource(
        "a",
        documents=[_doc("1", title="from a", source="a", metadata={"key_a": 1})],
    )
    b = _StubSource(
        "b",
        documents=[_doc("1", title="from b", abstract="b abstract", source="b", metadata={"key_b": 2})],
    )
    orch = FetchOrchestrator(sources=[a, b])
    out = orch.fetch(FetchInput.from_pmid("1"), prefer=["a", "b"])
    assert len(out) == 1
    merged = out[0]
    assert merged.title == "from a"            # first source wins
    assert merged.abstract == "b abstract"     # b filled the empty field
    assert merged.metadata["key_a"] == 1
    assert merged.metadata["key_b"] == 2
    assert merged.metadata["origin_sources"] == ["a", "b"]


def test_origin_sources_records_only_contributors() -> None:
    a = _StubSource("a", documents=[_doc("1")])
    b = _StubSource("b", documents=[])  # no docs returned
    orch = FetchOrchestrator(sources=[a, b])
    out = orch.fetch(FetchInput.from_pmid("1"), prefer=["a", "b"])
    assert out[0].metadata["origin_sources"] == ["a"]


# E. Errors

def test_duplicate_source_names_raises() -> None:
    with pytest.raises(ValueError, match="Duplicate source names"):
        FetchOrchestrator(sources=[_StubSource("a"), _StubSource("a")])


def test_unknown_prefer_name_raises_source_not_found() -> None:
    orch = FetchOrchestrator(sources=[_StubSource("a")])
    with pytest.raises(SourceNotFoundError):
        orch.fetch(FetchInput.from_pmid("1"), prefer="nonexistent")


def test_wrong_kind_for_source_raises_unsupported() -> None:
    a = _StubSource("a", supported_inputs=frozenset({"pmid"}))
    orch = FetchOrchestrator(sources=[a])
    with pytest.raises(UnsupportedInputError):
        orch.fetch(FetchInput.from_query("foo"), prefer="a")


def test_no_source_supports_kind_raises() -> None:
    a = _StubSource("a", supported_inputs=frozenset({"pmid"}))
    orch = FetchOrchestrator(sources=[a])
    with pytest.raises(UnsupportedInputError, match="No registered source"):
        orch.fetch(FetchInput.from_query("foo"))


# F. unite_into

def test_unite_into_base_wins_on_non_empty_title() -> None:
    base = _doc("1", title="base title", source="a")
    extra = _doc("1", title="extra title", source="b")
    unite_into(base, extra)
    assert base.title == "base title"


def test_unite_into_fills_empty_fields_from_extra() -> None:
    base = _doc("1", title="", abstract="", year=None, source="a")
    extra = _doc("1", title="extra title", abstract="extra abstract", year="2024", source="b")
    unite_into(base, extra)
    assert base.title == "extra title"
    assert base.abstract == "extra abstract"
    assert base.year == "2024"


def test_unite_into_metadata_uses_setdefault() -> None:
    base = _doc("1", source="a", metadata={"shared_key": "from_base"})
    extra = _doc("1", source="b", metadata={"shared_key": "from_extra", "new_key": "added"})
    unite_into(base, extra)
    assert base.metadata["shared_key"] == "from_base"  # base wins
    assert base.metadata["new_key"] == "added"          # new key added


def test_unite_into_skips_origin_sources_metadata() -> None:
    base = _doc("1", source="a", metadata={})
    extra = _doc("1", source="b", metadata={"origin_sources": ["b"]})
    unite_into(base, extra)
    assert "origin_sources" not in base.metadata

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from bio_annotation.orchestrator import (
    FetchOrchestrator,
    SourceNotFoundError,
)
from bio_annotation.schemas.document import Document
from bio_annotation.sources.base import (
    FetchInput,
    FetchKind,
    UnsupportedInputError,
)


@dataclass(slots=True)
class FakeSource:
    """Minimal FetchSource implementation for offline orchestrator tests."""

    name: str
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid", "pmid_list"})
    fields_provided: frozenset[str] = frozenset({"title", "abstract"})
    documents: list[Document] = field(default_factory=list)
    raise_on_fetch: Exception | None = None
    calls: list[FetchInput] = field(default_factory=list)

    def fetch(self, request: FetchInput) -> list[Document]:
        self.calls.append(request)
        if self.raise_on_fetch is not None:
            raise self.raise_on_fetch
        return [
            Document(
                document_id=d.document_id,
                pmid=d.pmid,
                title=d.title,
                abstract=d.abstract,
                full_text=d.full_text,
                year=d.year,
                source=d.source,
                metadata=dict(d.metadata),
            )
            for d in self.documents
        ]


def _doc(doc_id: str, **overrides: Any) -> Document:
    base: dict[str, Any] = {
        "document_id": doc_id,
        "pmid": doc_id.removeprefix("PMID:") if doc_id.startswith("PMID:") else None,
        "title": "",
        "abstract": "",
        "year": None,
        "source": "fake",
        "metadata": {},
    }
    base.update(overrides)
    return Document(**base)


def test_auto_pick_uses_first_source_that_supports_request() -> None:
    a = FakeSource("a", supported_inputs=frozenset({"query"}), documents=[_doc("PMID:1")])
    b = FakeSource("b", supported_inputs=frozenset({"pmid"}), documents=[_doc("PMID:1", title="from-b")])
    orch = FetchOrchestrator(sources=[a, b])

    docs = orch.fetch(FetchInput.from_pmid("1"))

    assert len(docs) == 1
    assert docs[0].title == "from-b"
    assert a.calls == []
    assert len(b.calls) == 1


def test_auto_pick_falls_back_when_first_does_not_support_kind() -> None:
    a = FakeSource("a", supported_inputs=frozenset({"raw_text"}))
    b = FakeSource("b", supported_inputs=frozenset({"query"}), documents=[_doc("PMID:9")])
    orch = FetchOrchestrator(sources=[a, b])

    docs = orch.fetch(FetchInput.from_query("microRNA"))

    assert [d.document_id for d in docs] == ["PMID:9"]
    assert a.calls == []


def test_explicit_prefer_picks_named_source() -> None:
    a = FakeSource("a", documents=[_doc("PMID:1", title="A")])
    b = FakeSource("b", documents=[_doc("PMID:1", title="B")])
    orch = FetchOrchestrator(sources=[a, b])

    docs = orch.fetch(FetchInput.from_pmid("1"), prefer="b")

    assert docs[0].title == "B"
    assert a.calls == []


def test_explicit_prefer_unknown_name_raises() -> None:
    orch = FetchOrchestrator(sources=[FakeSource("a")])
    with pytest.raises(SourceNotFoundError):
        orch.fetch(FetchInput.from_pmid("1"), prefer="nope")


def test_explicit_prefer_unsupported_kind_raises() -> None:
    a = FakeSource("a", supported_inputs=frozenset({"query"}))
    orch = FetchOrchestrator(sources=[a])
    with pytest.raises(UnsupportedInputError):
        orch.fetch(FetchInput.from_pmid("1"), prefer="a")


def test_no_supporting_source_raises_unsupported_input() -> None:
    a = FakeSource("a", supported_inputs=frozenset({"raw_text"}))
    orch = FetchOrchestrator(sources=[a])
    with pytest.raises(UnsupportedInputError):
        orch.fetch(FetchInput.from_pmid("1"))


def test_merge_unions_metadata_from_multiple_sources() -> None:
    a = FakeSource(
        "a",
        documents=[_doc("PMID:1", title="A title", metadata={"epmc_meta": {"x": 1}})],
    )
    b = FakeSource(
        "b",
        documents=[_doc("PMID:1", metadata={"pubtator3_payload": {"y": 2}})],
    )
    orch = FetchOrchestrator(sources=[a, b])

    docs = orch.fetch(FetchInput.from_pmid("1"), prefer=["a", "b"])

    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "A title"
    assert doc.metadata["epmc_meta"] == {"x": 1}
    assert doc.metadata["pubtator3_payload"] == {"y": 2}


def test_merge_keeps_first_source_top_level_when_both_populated() -> None:
    a = FakeSource("a", documents=[_doc("PMID:1", title="A title", abstract="from-a")])
    b = FakeSource("b", documents=[_doc("PMID:1", title="B title", abstract="from-b")])
    orch = FetchOrchestrator(sources=[a, b])

    doc = orch.fetch(FetchInput.from_pmid("1"), prefer=["a", "b"])[0]

    assert doc.title == "A title"
    assert doc.abstract == "from-a"


def test_merge_fills_blank_top_level_from_later_sources() -> None:
    a = FakeSource("a", documents=[_doc("PMID:1", title="A title")])
    b = FakeSource("b", documents=[_doc("PMID:1", abstract="from-b", year="2024")])
    orch = FetchOrchestrator(sources=[a, b])

    doc = orch.fetch(FetchInput.from_pmid("1"), prefer=["a", "b"])[0]

    assert doc.title == "A title"
    assert doc.abstract == "from-b"
    assert doc.year == "2024"


def test_merge_records_origin_sources_in_metadata() -> None:
    a = FakeSource("a", documents=[_doc("PMID:1", title="A")])
    b = FakeSource("b", documents=[_doc("PMID:1", title="B")])
    orch = FetchOrchestrator(sources=[a, b])

    doc = orch.fetch(FetchInput.from_pmid("1"), prefer=["a", "b"])[0]

    assert doc.metadata["origin_sources"] == ["a", "b"]


def test_merge_strict_false_swallows_source_errors() -> None:
    a = FakeSource(
        "a",
        documents=[_doc("PMID:1", title="A")],
    )
    b = FakeSource("b", raise_on_fetch=RuntimeError("boom"))
    orch = FetchOrchestrator(sources=[a, b])

    docs = orch.fetch(
        FetchInput.from_pmid("1"),
        prefer=["a", "b"],
        strict=False,
    )

    assert [d.title for d in docs] == ["A"]
    assert docs[0].metadata["origin_sources"] == ["a"]


def test_merge_strict_true_propagates_source_errors() -> None:
    a = FakeSource("a", documents=[_doc("PMID:1", title="A")])
    b = FakeSource("b", raise_on_fetch=RuntimeError("boom"))
    orch = FetchOrchestrator(sources=[a, b])

    with pytest.raises(RuntimeError, match="boom"):
        orch.fetch(FetchInput.from_pmid("1"), prefer=["a", "b"])


def test_merge_deduplicates_repeated_source_names_in_prefer() -> None:
    a = FakeSource("a", documents=[_doc("PMID:1", title="A")])
    orch = FetchOrchestrator(sources=[a])

    orch.fetch(FetchInput.from_pmid("1"), prefer=["a", "a", "a"])

    assert len(a.calls) == 1


def test_merge_preserves_first_seen_document_order() -> None:
    a = FakeSource(
        "a",
        supported_inputs=frozenset({"pmid_list"}),
        documents=[_doc("PMID:1"), _doc("PMID:2")],
    )
    b = FakeSource(
        "b",
        supported_inputs=frozenset({"pmid_list"}),
        documents=[_doc("PMID:3"), _doc("PMID:1"), _doc("PMID:4")],
    )
    orch = FetchOrchestrator(sources=[a, b])

    docs = orch.fetch(
        FetchInput.from_pmid_list(["1", "2", "3", "4"]),
        prefer=["a", "b"],
    )

    assert [d.document_id for d in docs] == ["PMID:1", "PMID:2", "PMID:3", "PMID:4"]


def test_available_sources_filters_by_request_kind() -> None:
    a = FakeSource("a", supported_inputs=frozenset({"pmid"}))
    b = FakeSource("b", supported_inputs=frozenset({"raw_text"}))
    c = FakeSource("c", supported_inputs=frozenset({"pmid", "query"}))
    orch = FetchOrchestrator(sources=[a, b, c])

    assert orch.available_sources(FetchInput.from_pmid("1")) == ["a", "c"]
    assert orch.available_sources(FetchInput.from_query("x")) == ["c"]
    assert orch.available_sources(FetchInput.from_text("hi")) == ["b"]


def test_get_returns_source_by_name() -> None:
    a = FakeSource("a")
    b = FakeSource("b")
    orch = FetchOrchestrator(sources=[a, b])

    assert orch.get("a") is a
    assert orch.get("b") is b


def test_get_unknown_name_raises_source_not_found() -> None:
    orch = FetchOrchestrator(sources=[FakeSource("a")])
    with pytest.raises(SourceNotFoundError):
        orch.get("missing")


def test_names_preserves_registration_order() -> None:
    sources = [FakeSource("z"), FakeSource("m"), FakeSource("a")]
    orch = FetchOrchestrator(sources=sources)
    assert orch.names() == ["z", "m", "a"]


def test_duplicate_source_names_raise_at_construction() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        FetchOrchestrator(sources=[FakeSource("a"), FakeSource("a")])

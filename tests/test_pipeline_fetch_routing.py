"""Tests for the [input.source] / [input.fields_per_source] config block.

Covers two layers:

1. ``load_pipeline_config`` correctly parses the new optional keys
   (``input.source``, ``input.fields``, ``input.fields_per_source``) and
   leaves legacy configs unchanged.
2. ``load_documents_from_config`` routes through ``FetchOrchestrator`` when
   ``fetch_sources`` is set, builds a ``FetchInput`` honouring the per-source
   filters, and falls back to the legacy single-source loader otherwise.

The orchestrator is replaced with a ``FakeOrchestrator`` so no HTTP runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from bio_annotation.pipeline_config import (
    PipelineConfig,
    SUPPORTED_FETCH_SOURCES,
    load_pipeline_config,
)
from bio_annotation.preprocessing.document_loader import load_documents_from_config
from bio_annotation.schemas.document import Document


# ---------------------------------------------------------------------------
# Fakes / helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeOrchestrator:
    """Records every call so tests can assert on routing behaviour."""

    documents: list[Document] = field(default_factory=list)
    captured_request: Any = None
    captured_prefer: Any = None

    def fetch(self, request: Any, *, prefer: Any = None) -> list[Document]:
        self.captured_request = request
        self.captured_prefer = prefer
        return list(self.documents)


def _write_config(tmp_path: Path, body: str) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.write_text(body, encoding="utf-8")
    return config_path


def _stub_doc(pmid: str, title: str = "Stub") -> Document:
    return Document(
        document_id=f"PMID:{pmid}",
        pmid=pmid,
        title=title,
        abstract="",
        source="fake",
    )


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


def test_legacy_config_has_empty_fetch_sources_and_no_field_filters(tmp_path: Path) -> None:
    """A pre-existing config with no [input.source] keeps backward compatibility."""

    config_path = _write_config(
        tmp_path,
        """
        [input]
        mode = "pmids"
        pmids = ["12345"]

        [annotators]
        enabled = []
        """,
    )

    config = load_pipeline_config(config_path)

    assert config.fetch_sources == []
    assert config.fetch_fields is None
    assert config.fetch_fields_per_source is None


def test_input_source_string_becomes_single_element_list(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        [input]
        mode = "pmids"
        pmids = ["12345"]
        source = "europe_pmc"

        [annotators]
        enabled = []
        """,
    )

    config = load_pipeline_config(config_path)

    assert config.fetch_sources == ["europe_pmc"]


def test_input_source_list_preserves_order_for_chain_dispatch(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        [input]
        mode = "pmids"
        pmids = ["12345"]
        source = ["entrez", "europe_pmc", "pubtator3"]

        [annotators]
        enabled = []
        """,
    )

    config = load_pipeline_config(config_path)

    assert config.fetch_sources == ["entrez", "europe_pmc", "pubtator3"]


def test_input_source_rejects_unsupported_value(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        [input]
        mode = "pmids"
        pmids = ["12345"]
        source = "made_up_source"

        [annotators]
        enabled = []
        """,
    )

    with pytest.raises(ValueError, match="input.source contains unsupported"):
        load_pipeline_config(config_path)


def test_input_fields_parsed_as_optional_list(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        [input]
        mode = "pmids"
        pmids = ["12345"]
        source = "entrez"
        fields = ["mesh_terms", "authors"]

        [annotators]
        enabled = []
        """,
    )

    config = load_pipeline_config(config_path)

    assert config.fetch_fields == ["mesh_terms", "authors"]


def test_input_fields_per_source_parsed_as_dict(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        [input]
        mode = "pmids"
        pmids = ["12345"]
        source = ["entrez", "europe_pmc"]

        [input.fields_per_source]
        entrez = ["mesh_terms"]
        europe_pmc = ["is_open_access", "citation_count"]

        [annotators]
        enabled = []
        """,
    )

    config = load_pipeline_config(config_path)

    assert config.fetch_fields_per_source == {
        "entrez": ["mesh_terms"],
        "europe_pmc": ["is_open_access", "citation_count"],
    }


def test_input_fields_per_source_rejects_unknown_source(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        [input]
        mode = "pmids"
        pmids = ["12345"]
        source = "entrez"

        [input.fields_per_source]
        bogus = ["x"]

        [annotators]
        enabled = []
        """,
    )

    with pytest.raises(ValueError, match="input.fields_per_source.bogus"):
        load_pipeline_config(config_path)


def test_supported_fetch_sources_includes_all_four_sources() -> None:
    assert set(SUPPORTED_FETCH_SOURCES) == {
        "entrez",
        "europe_pmc",
        "pubtator3",
        "raw_text",
    }


# ---------------------------------------------------------------------------
# Loader routing
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> PipelineConfig:
    """Build a PipelineConfig with sensible defaults for routing tests."""

    base: dict[str, Any] = {
        "input_mode": "pmids",
        "pmids": ["100"],
        "pmid_file": None,
        "text_file": None,
        "text_format": "csv",
        "document_id_column": "document_id",
        "title_column": "title",
        "abstract_column": "abstract",
        "corpus_path": None,
        "enrichment_sources": [],
        "annotators": [],
        "annotator_settings": {},
        "entity_types": [],
        "output_path": None,
        "fetch_sources": [],
        "fetch_fields": None,
        "fetch_fields_per_source": None,
    }
    base.update(overrides)
    return PipelineConfig(**base)


def test_loader_uses_orchestrator_when_single_source_configured() -> None:
    fake = FakeOrchestrator(documents=[_stub_doc("100")])
    config = _make_config(fetch_sources=["europe_pmc"])

    docs = load_documents_from_config(
        config,
        orchestrator_factory=lambda: fake,
    )

    assert [d.pmid for d in docs] == ["100"]
    assert fake.captured_prefer == "europe_pmc"
    assert fake.captured_request.kind == "pmid"
    assert fake.captured_request.pmids == ("100",)


def test_loader_uses_orchestrator_with_chain_when_multiple_sources_configured() -> None:
    fake = FakeOrchestrator(
        documents=[_stub_doc("100"), _stub_doc("200")],
    )
    config = _make_config(
        pmids=["100", "200"],
        fetch_sources=["entrez", "europe_pmc"],
    )

    docs = load_documents_from_config(
        config,
        orchestrator_factory=lambda: fake,
    )

    assert len(docs) == 2
    assert fake.captured_prefer == ["entrez", "europe_pmc"]
    assert fake.captured_request.kind == "pmid_list"
    assert fake.captured_request.pmids == ("100", "200")


def test_loader_propagates_global_fields_filter_to_fetch_input() -> None:
    fake = FakeOrchestrator(documents=[_stub_doc("100")])
    config = _make_config(
        fetch_sources=["entrez"],
        fetch_fields=["mesh_terms", "authors"],
    )

    load_documents_from_config(config, orchestrator_factory=lambda: fake)

    assert fake.captured_request.fields == frozenset({"mesh_terms", "authors"})


def test_loader_propagates_per_source_fields_to_fetch_input() -> None:
    fake = FakeOrchestrator(documents=[_stub_doc("100")])
    config = _make_config(
        fetch_sources=["entrez", "europe_pmc"],
        fetch_fields_per_source={
            "entrez": ["mesh_terms"],
            "europe_pmc": ["is_open_access"],
        },
    )

    load_documents_from_config(config, orchestrator_factory=lambda: fake)

    request = fake.captured_request
    assert request.fields_per_source == {
        "entrez": frozenset({"mesh_terms"}),
        "europe_pmc": frozenset({"is_open_access"}),
    }


def test_loader_orchestrator_path_for_pmid_file(tmp_path: Path) -> None:
    """Reads PMIDs from disk, dedupes, and forwards them to the orchestrator."""

    pmid_file = tmp_path / "pmids.txt"
    pmid_file.write_text("100\n200\n200\n  300  \n", encoding="utf-8")
    fake = FakeOrchestrator(documents=[_stub_doc("100")])
    config = _make_config(
        input_mode="pmid_file",
        pmids=[],
        pmid_file=pmid_file,
        fetch_sources=["entrez"],
    )

    load_documents_from_config(config, orchestrator_factory=lambda: fake)

    assert fake.captured_request.kind == "pmid_list"
    assert fake.captured_request.pmids == ("100", "200", "300")


def test_loader_legacy_path_when_fetch_sources_empty(tmp_path: Path) -> None:
    """Without [input.source], the loader uses the legacy fetcher and never
    touches the orchestrator factory.
    """

    fake = FakeOrchestrator()  # captures nothing => assertion below

    captured: list[str] = []

    def fake_pubmed_fetcher(pmid: str) -> dict[str, Any]:
        captured.append(pmid)
        return {"pmid": pmid, "title": "T", "abstract": "A", "year": "2024"}

    config = _make_config(pmids=["100", "200"], fetch_sources=[])

    docs = load_documents_from_config(
        config,
        pmid_fetcher=fake_pubmed_fetcher,
        orchestrator_factory=lambda: fake,  # must NOT be called
    )

    assert [d.pmid for d in docs] == ["100", "200"]
    assert captured == ["100", "200"]
    assert fake.captured_request is None
    assert fake.captured_prefer is None


def test_loader_orchestrator_path_returns_empty_when_no_pmids() -> None:
    """An orchestrator with zero PMIDs to fetch returns [] without calling fetch."""

    fake = FakeOrchestrator(documents=[_stub_doc("999")])
    config = _make_config(
        input_mode="pmids",
        pmids=[],
        fetch_sources=["entrez"],
    )

    # Note: load_pipeline_config rejects empty pmids upstream, but the loader
    # itself should be defensive when called from other code paths.
    docs = load_documents_from_config(config, orchestrator_factory=lambda: fake)

    assert docs == []
    assert fake.captured_request is None

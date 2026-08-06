from __future__ import annotations

import builtins
import csv
import json
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO

import pytest

from bio_annotation.cli import main
from bio_annotation.fetch import FetchOrchestrator
from bio_annotation.fetch.input import FetchInput, FetchKind
from bio_annotation.schemas.document import Document
from bio_annotation.pipeline_runner import (
    _load_flair_tagger,
    _read_bern2_options,
    _read_flair_options,
    _read_pubtator3_options,
    _read_stanza_options,
    build_keyword_annotations,
    filter_annotations_by_type,
    run_pipeline_from_config,
    run_selected_annotators,
    run_selected_annotators_with_status,
    write_pipeline_tsv_outputs,
)
from bio_annotation.schemas.entity import Annotation
from bio_annotation.schemas.document import Document


@dataclass
class FakeLabel:
    value: str
    score: float


@dataclass
class FakeSpan:
    text: str
    start_position: int
    end_position: int
    labels: list[FakeLabel]


@dataclass(slots=True)
class _StubEntrezSource:
    name: str = "entrez"
    supported_inputs: frozenset[FetchKind] = frozenset({"pmid", "pmid_list"})
    fields_provided: frozenset[str] = frozenset()

    def fetch(self, request: FetchInput) -> list[Document]:
        return [
            Document(
                document_id=f"PMID:{pmid}",
                pmid=pmid,
                title="PTEN regulates glioblastoma",
                abstract="PTEN is important in glioblastoma.",
                source="entrez",
                year="2024",
                metadata={
                    "pubmed_record": {
                        "pmid": pmid,
                        "pmcid": "PMC1234567",
                        "title": "PTEN regulates glioblastoma",
                        "abstract": "PTEN is important in glioblastoma.",
                        "year": "2024",
                    },
                    "pmcid": "PMC1234567",
                },
            )
            for pmid in request.pmids
        ]


def _stub_orchestrator() -> FetchOrchestrator:
    return FetchOrchestrator(sources=[_StubEntrezSource()])


def test_run_pipeline_from_config_with_pmids(tmp_path) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "pmids"',
                'pmids = ["12345678"]',
                'source = "entrez"',
                "",
                "[enrichment]",
                'sources = ["elinks", "crossref"]',
                "",
                "[annotators]",
                'enabled = ["bern2", "pubtator3"]',
                "",
                "[annotators.pubtator3]",
                'runtime = "remote_api"',
                'endpoint = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"',
                'format = "biocjson"',
                "timeout = 45",
                "",
                "[filters]",
                'entity_types = ["gene", "disease"]',
                "",
                "[output]",
                'path = "outputs/test.json"',
            ]
        ),
        encoding="utf-8",
    )

    payload = run_pipeline_from_config(
        config_path,
        orchestrator_factory=_stub_orchestrator,
        bern2_request_fn=lambda document: {
            "annotations": [
                {"mention": "PTEN", "span": {"begin": 0, "end": 4}, "type": "Gene", "id": "NCBIGene:5728"}
            ]
        },
        pubtator3_request_fn=lambda document: {
            "documents": [
                {
                    "passages": [
                        {
                            "annotations": [
                                {
                                    "text": "glioblastoma",
                                    "infons": {"type": "Disease", "identifier": "D005909"},
                                    "locations": [{"offset": 19, "length": 12}],
                                }
                            ]
                        }
                    ]
                }
            ]
        },
    )

    assert payload["document_count"] == 1
    assert payload["stage"] == "corpus"
    assert payload["input"]["mode"] == "pmids"
    assert payload["pipeline"]["mode"] == "ingestion_and_annotation"
    assert payload["pipeline"]["annotators_enabled"] == ["bern2", "pubtator3"]
    assert payload["documents"][0]["metadata"]["pubmed_record"]["pmcid"] == "PMC1234567"
    assert payload["annotation_summary"]["annotation_count"] == 2
    assert payload["annotator_summary"]["configured"] == ["bern2", "pubtator3"]
    assert payload["annotator_summary"]["produced"] == ["bern2", "pubtator3"]
    assert payload["annotator_summary"]["not_produced"] == []
    assert payload["document_annotations"][0]["sources"] == ["bern2", "pubtator3"]
    assert payload["document_annotations"][0]["annotators"] == [
        {
            "name": "bern2",
            "status": "produced_annotations",
            "annotation_count": 1,
            "reason": None,
        },
        {
            "name": "pubtator3",
            "status": "produced_annotations",
            "annotation_count": 1,
            "reason": None,
        },
    ]
    assert len(payload["annotations"]) == 2
    assert payload["document_annotations"][0]["annotation_ids"] == [
        annotation["annotation_id"] for annotation in payload["annotations"]
    ]
    assert "annotations" not in payload["document_annotations"][0]


def test_run_pipeline_records_annotators_without_results(tmp_path) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "pmids"',
                'pmids = ["12345678"]',
                "",
                "[enrichment]",
                "sources = []",
                "",
                "[annotators]",
                'enabled = ["bern2", "flair"]',
                "",
                "[annotators.bern2]",
                'base_url = "http://127.0.0.1:8888"',
                "",
                "[annotators.flair]",
                'model = "hunflair2"',
                "",
                "[filters]",
                "entity_types = []",
            ]
        ),
        encoding="utf-8",
    )

    payload = run_pipeline_from_config(
        config_path,
        pmid_fetcher=lambda pmid: {
            "pmid": pmid,
            "title": "PTEN regulates glioblastoma",
            "abstract": "PTEN is important in glioblastoma.",
            "year": "2024",
        },
        bern2_request_fn=lambda document: {"annotations": []},
        flair_spans_by_document={"PMID:12345678": []},
    )

    assert payload["annotator_summary"]["configured"] == ["bern2", "flair"]
    assert payload["annotator_summary"]["produced"] == []
    assert payload["annotator_summary"]["not_produced"] == ["bern2", "flair"]
    assert payload["document_annotations"][0]["annotators"] == [
        {
            "name": "bern2",
            "status": "no_annotations",
            "annotation_count": 0,
            "reason": "No annotations returned. Verify the Bern2 service is reachable and returned entities for this document.",
        },
        {
            "name": "flair",
            "status": "no_annotations",
            "annotation_count": 0,
            "reason": "No annotations returned. The Flair model may be unavailable/not cached, or it found no entities.",
        },
    ]


def test_cli_run_config_outputs_payload(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "text_table"',
                f'text_file = "{(tmp_path / "documents.csv").as_posix()}"',
                'format = "csv"',
                'document_id_column = "document_id"',
                'title_column = "title"',
                'abstract_column = "abstract"',
                "",
                "[enrichment]",
                "sources = []",
                "",
                "[annotators]",
                'enabled = ["flair"]',
                "",
                "[filters]",
                'entity_types = ["gene"]',
                "",
                "[output]",
                'path = "outputs/test.json"',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "documents.csv").write_text(
        "document_id,title,abstract\n"
        "doc1,PTEN regulates glioblastoma,PTEN is important in glioblastoma.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "bio_annotation.cli.run_pipeline_from_config",
        lambda path: {
            "stage": "corpus",
            "document_count": 1,
            "pipeline": {
                "mode": "ingestion_and_annotation",
                "annotators_enabled": ["flair"],
            },
            "entity_types": ["gene"],
            "documents": [],
            "annotation_summary": {
                "annotators_enabled": ["flair"],
                "document_count": 1,
                "annotation_count": 0,
                "keyword_count": 0,
            },
            "document_annotations": [],
            "keywords": [],
            "annotations": [],
            "annotator_summary": {
                "configured": ["flair"],
                "produced": [],
                "not_produced": ["flair"],
                "failed": [],
                "annotators": [],
            },
            "output": {"path": "outputs/20260513-122400/test.json"},
        },
    )

    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(["run-config", "--config", str(config_path)])

    output = stream.getvalue()
    assert exit_code == 0
    assert "Pipeline completed." in output
    assert "Output written to: outputs/20260513-122400/test.json" in output
    assert "Documents: 1" in output
    assert "Annotations: 0" in output
    assert "Keywords: 0" in output
    assert "Annotators with results: none" in output
    assert "Annotators without results: flair" in output
    assert not output.lstrip().startswith("{")


def test_cli_run_config_ingestion_only(tmp_path) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "corpus"',
                f'corpus_path = "{(tmp_path / "documents.json").as_posix()}"',
                "",
                "[enrichment]",
                "sources = []",
                "",
                "[annotators]",
                "enabled = []",
                "",
                "[filters]",
                "entity_types = []",
                "",
                "[output]",
                f'path = "{(tmp_path / "outputs" / "test.json").as_posix()}"',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "documents.json").write_text(
        '{"documents":[{"document_id":"doc1","title":"PTEN regulates glioblastoma","abstract":"PTEN is important.","source":"corpus"}]}',
        encoding="utf-8",
    )

    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(["run-config", "--config", str(config_path)])

    output = stream.getvalue()
    assert exit_code == 0
    assert "Pipeline completed." in output
    written = sorted((tmp_path / "outputs").glob("*/test.json"))
    assert len(written) == 1
    assert f"Output written to: {written[0].as_posix()}" in output
    assert "Annotations: 0" in output
    assert "Annotators with results: none" in output
    assert "Annotators without results: none" in output
    assert not output.lstrip().startswith("{")


def test_read_pubtator3_options_parses_text_mode_settings() -> None:
    options = _read_pubtator3_options(
        {
            "endpoint": "https://www.ncbi.nlm.nih.gov/research/pubtator3-api",
            "timeout": 45,
            "format": "biocjson",
            "mode": "text_only",
            "bioconcept": "Gene",
            "poll_interval_seconds": 3.0,
            "poll_backoff": 2.0,
            "max_poll_interval_seconds": 12.0,
            "max_poll_attempts": 25,
        }
    )

    assert options["mode"] == "text_only"
    assert options["bioconcept"] == "Gene"
    assert options["max_poll_attempts"] == 25
    assert options["poll_interval_seconds"] == 3.0
    assert options["poll_backoff"] == 2.0
    assert options["max_poll_interval_seconds"] == 12.0


def test_read_bern2_options_prefers_endpoint_then_base_url() -> None:
    assert _read_bern2_options({"base_url": "http://bern2.local"}) == {
        "endpoint": "http://bern2.local"
    }
    assert _read_bern2_options(
        {
            "base_url": "http://bern2.local",
            "endpoint": "http://bern2.local/plain",
        }
    ) == {"endpoint": "http://bern2.local/plain"}


def test_run_selected_annotators_passes_bern2_endpoint(monkeypatch) -> None:
    document = Document(
        document_id="doc1",
        title="PTEN regulates glioblastoma",
        abstract="PTEN is important.",
        source="corpus",
    )
    calls: list[str | None] = []

    def fake_bern2(document: Document, **kwargs: object) -> list[Annotation]:
        calls.append(kwargs.get("endpoint"))
        return []

    monkeypatch.setattr("bio_annotation.pipeline_runner.annotate_with_bern2", fake_bern2)

    run_selected_annotators(
        document,
        ["bern2"],
        bern2_options={"endpoint": "http://127.0.0.1:8888"},
    )

    assert calls == ["http://127.0.0.1:8888"]


def test_read_flair_options_reads_model() -> None:
    assert _read_flair_options({"model": "hunflair2"}) == {"model": "hunflair2"}
    assert _read_flair_options({}) == {"model": None}


def test_load_flair_tagger_reports_optional_dependency(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "flair":
            raise ImportError("No module named 'flair'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="uv sync --extra flair"):
        _load_flair_tagger("hunflair2")


def test_run_pipeline_preflights_missing_flair_dependency(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "pmids"',
                'pmids = ["12345678"]',
                "",
                "[annotators]",
                'enabled = ["flair"]',
                "",
                "[filters]",
                "entity_types = []",
            ]
        ),
        encoding="utf-8",
    )
    checked_modules: list[str] = []

    def fake_find_spec(name: str) -> object | None:
        checked_modules.append(name)
        return None

    monkeypatch.setattr("bio_annotation.pipeline_runner.find_spec", fake_find_spec)

    with pytest.raises(ValueError, match="uv sync --extra flair"):
        run_pipeline_from_config(config_path)

    assert checked_modules == ["flair"]


def test_run_selected_annotators_passes_flair_model(monkeypatch) -> None:
    document = Document(
        document_id="doc1",
        title="PTEN regulates glioblastoma",
        abstract="PTEN is important.",
        source="corpus",
    )
    calls: list[str | None] = []

    def fake_flair(document: Document, **kwargs: object) -> list[Annotation]:
        calls.append(kwargs.get("model"))
        return []

    monkeypatch.setattr("bio_annotation.pipeline_runner.annotate_with_flair", fake_flair)

    run_selected_annotators(
        document,
        ["flair"],
        flair_options={"model": "hunflair2"},
    )

    assert calls == ["hunflair2"]


def test_run_selected_annotators_passes_scispacy_model(monkeypatch) -> None:
    document = Document(
        document_id="doc1",
        title="PTEN regulates glioblastoma",
        abstract="PTEN is important.",
        source="corpus",
    )
    calls: list[tuple[str, str, object]] = []

    def fake_scispacy(document: Document, **kwargs: object) -> list[Annotation]:
        calls.append((str(kwargs.get("source")), str(kwargs.get("model")), kwargs.get("linker_name")))
        return []

    monkeypatch.setattr("bio_annotation.pipeline_runner.annotate_with_scispacy", fake_scispacy)

    run_selected_annotators(
        document,
        ["scispacy_jnlpba", "scispacy_bc5cdr", "scispacy_bionlp13cg", "scispacy_scibert"],
        scispacy_options={
            "scispacy_jnlpba": {"model": "en_ner_jnlpba_md"},
            "scispacy_bc5cdr": {"model": "en_ner_bc5cdr_md"},
            "scispacy_bionlp13cg": {"model": "en_ner_bionlp13cg_md"},
            "scispacy_scibert": {"model": "en_core_sci_scibert", "linker_name": "umls"},
        },
    )

    assert calls == [
        ("scispacy_jnlpba", "en_ner_jnlpba_md", None),
        ("scispacy_bc5cdr", "en_ner_bc5cdr_md", None),
        ("scispacy_bionlp13cg", "en_ner_bionlp13cg_md", None),
        ("scispacy_scibert", "en_core_sci_scibert", "umls"),
    ]


def test_run_pipeline_preflights_missing_scispacy_dependency(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "pmids"',
                'pmids = ["12345678"]',
                "",
                "[annotators]",
                'enabled = ["scispacy_bc5cdr"]',
                "",
                "[filters]",
                "entity_types = []",
            ]
        ),
        encoding="utf-8",
    )
    checked_modules: list[str] = []

    def fake_find_spec(name: str) -> object | None:
        checked_modules.append(name)
        return None

    monkeypatch.setattr("bio_annotation.pipeline_runner.find_spec", fake_find_spec)

    with pytest.raises(ValueError, match="uv sync --extra scispacy"):
        run_pipeline_from_config(config_path)

    assert checked_modules == ["scispacy"]


def test_run_selected_annotators_records_failures(monkeypatch, caplog) -> None:
    document = Document(
        document_id="doc1",
        title="PTEN regulates glioblastoma",
        abstract="PTEN is important.",
        source="corpus",
    )

    def broken_flair(document: Document, **kwargs: object) -> list[Annotation]:
        raise RuntimeError("hunflair2 is unavailable")

    monkeypatch.setattr("bio_annotation.pipeline_runner.annotate_with_flair", broken_flair)

    with caplog.at_level("WARNING", logger="bio_annotation.pipeline_runner"):
        results, statuses = run_selected_annotators_with_status(
            document,
            ["flair"],
            flair_options={"model": "hunflair2"},
        )

    assert results == {"flair": []}
    assert statuses == [
        {
            "name": "flair",
            "status": "failed",
            "annotation_count": 0,
            "reason": "hunflair2 is unavailable",
        }
    ]
    assert "flair unavailable: hunflair2 is unavailable" in caplog.text


def test_build_keyword_annotations_groups_by_keyword_with_mentions_and_evidence() -> None:
    keywords = build_keyword_annotations(
        "doc1",
        [
            Annotation(
                annotation_id="pubtator3:1",
                source="pubtator3",
                span_text="GBM",
                start=10,
                end=13,
                entity_type="disease",
                canonical_id="MESH:D005909",
                canonical_name="Glioblastoma",
            ),
            Annotation(
                annotation_id="bern2:1",
                source="bern2",
                span_text="GBM",
                start=10,
                end=13,
                entity_type="disease",
                canonical_id="BERN:glioblastoma",
                canonical_name="Glioblastoma",
                confidence=0.94,
            ),
            Annotation(
                annotation_id="pubtator3:2",
                source="pubtator3",
                span_text="gbm",
                start=40,
                end=43,
                entity_type="disease",
                canonical_id="MESH:D005909",
                canonical_name="Glioblastoma",
            ),
            Annotation(
                annotation_id="flair:1",
                source="flair",
                span_text="tumor",
                start=55,
                end=60,
                entity_type="disease",
            ),
        ],
    )

    assert len(keywords) == 2

    gbm = keywords[0]
    assert gbm["keyword"] == "GBM"
    assert gbm["normalized_keyword"] == "gbm"
    assert gbm["variants"] == ["GBM", "gbm"]
    assert gbm["annotation_count"] == 3
    assert gbm["annotation_ids"] == ["bern2:1", "pubtator3:1", "pubtator3:2"]
    assert gbm["mention_count"] == 2
    assert gbm["annotator_count"] == 2
    assert gbm["labels"] == ["disease"]
    assert gbm["canonical_ids"] == ["BERN:glioblastoma", "MESH:D005909"]
    assert "annotators" not in gbm

    first_mention = gbm["mentions"][0]
    assert first_mention["start"] == 10
    assert first_mention["end"] == 13
    assert first_mention["annotation_count"] == 2
    assert first_mention["annotator_count"] == 2
    assert first_mention["annotation_ids"] == ["bern2:1", "pubtator3:1"]
    assert "annotators" not in first_mention


def test_pipeline_tsv_outputs_resolve_keyword_annotation_ids(tmp_path) -> None:
    annotations = [
        {
            "document_id": "doc1",
            "annotation_id": "bern2:1",
            "source": "bern2",
            "span_text": "GBM",
            "start": 10,
            "end": 13,
            "entity_type": "disease",
            "canonical_id": "BERN:glioblastoma",
            "canonical_name": "Glioblastoma",
            "confidence": 0.94,
        },
        {
            "document_id": "doc1",
            "annotation_id": "pubtator3:1",
            "source": "pubtator3",
            "span_text": "GBM",
            "start": 10,
            "end": 13,
            "entity_type": "disease",
            "canonical_id": "MESH:D005909",
            "canonical_name": "Glioblastoma",
            "confidence": None,
        },
    ]
    payload = {
        "documents": [{"document_id": "doc1", "pmid": "123", "title": "GBM study"}],
        "annotations": annotations,
        "keywords": [
            {
                "document_id": "doc1",
                "keyword": "GBM",
                "annotation_count": 2,
                "annotator_count": 2,
                "labels": ["disease"],
                "canonical_ids": ["BERN:glioblastoma", "MESH:D005909"],
                "annotation_ids": ["bern2:1", "pubtator3:1"],
                "mentions": [
                    {
                        "text": "GBM",
                        "start": 10,
                        "end": 13,
                        "annotation_count": 2,
                        "annotator_count": 2,
                        "annotation_ids": ["bern2:1", "pubtator3:1"],
                    }
                ],
            }
        ],
    }

    write_pipeline_tsv_outputs(payload, tmp_path / "results.json")

    with (tmp_path / "results.keyword_annotator_evidence.tsv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    assert [
        (row["annotation_id"], row["source"], row["label"], row["canonical_id"])
        for row in rows
    ] == [
        ("bern2:1", "bern2", "disease", "BERN:glioblastoma"),
        ("pubtator3:1", "pubtator3", "disease", "MESH:D005909"),
    ]


def test_filter_annotations_by_type_normalizes_entity_labels() -> None:
    annotations = [
        Annotation(
            annotation_id="bern2:1",
            source="bern2",
            span_text="PTEN",
            start=0,
            end=4,
            entity_type="Gene",
        ),
        Annotation(
            annotation_id="bern2:2",
            source="bern2",
            span_text="glioblastoma",
            start=15,
            end=27,
            entity_type="Disease",
        ),
    ]

    filtered = filter_annotations_by_type(annotations, ["gene"])

    assert [annotation.entity_type for annotation in filtered] == ["Gene"]


def test_read_stanza_options_omitted_package_defaults_to_none():
    # When the config omits package, it must stay None so annotate_with_stanza
    # applies the model-specific default (mimic for i2b2/radiology, craft otherwise).
    # A stray craft default here would override that per-model choice.
    assert _read_stanza_options({})["package"] is None
    assert _read_stanza_options({"package": ""})["package"] is None
    assert _read_stanza_options({"package": "  "})["package"] is None


def test_read_stanza_options_explicit_package_is_kept():
    assert _read_stanza_options({"package": "mimic"})["package"] == "mimic"
    assert _read_stanza_options({"package": " craft "})["package"] == "craft"

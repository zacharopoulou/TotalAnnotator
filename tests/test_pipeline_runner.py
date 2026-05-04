from __future__ import annotations

import json
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO

from bio_annotation.cli import main
from bio_annotation.fetch import FetchOrchestrator
from bio_annotation.fetch.input import FetchInput, FetchKind
from bio_annotation.schemas.document import Document
from bio_annotation.pipeline_runner import (
    _read_pubtator3_options,
    build_keyword_annotations,
    run_pipeline_from_config,
)
from bio_annotation.schemas.entity import Annotation


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
    assert payload["document_annotations"][0]["sources"] == ["bern2", "pubtator3"]
    assert len(payload["annotations"]) == 2


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
            "annotation_summary": {"annotators_enabled": ["flair"], "document_count": 1, "annotation_count": 0},
            "document_annotations": [],
            "annotations": [],
        },
    )

    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(["run-config", "--config", str(config_path)])

    output = json.loads(stream.getvalue())
    assert exit_code == 0
    assert output["stage"] == "corpus"
    assert output["pipeline"]["annotators_enabled"] == ["flair"]


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
                'path = "outputs/test.json"',
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

    output = json.loads(stream.getvalue())
    assert exit_code == 0
    assert output["stage"] == "corpus"
    assert output["input"]["mode"] == "corpus"
    assert output["pipeline"]["annotators_enabled"] == []
    assert output["annotation_summary"]["annotation_count"] == 0


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
    assert gbm["mention_count"] == 2
    assert gbm["annotator_count"] == 2
    assert gbm["labels"] == ["disease"]
    assert gbm["canonical_ids"] == ["BERN:glioblastoma", "MESH:D005909"]
    assert [
        (item["source"], item["annotation_count"], item["canonical_ids"])
        for item in gbm["annotators"]
    ] == [
        ("bern2", 1, ["BERN:glioblastoma"]),
        ("pubtator3", 2, ["MESH:D005909"]),
    ]
    assert "mentions" not in gbm["annotators"][0]

    first_mention = gbm["mentions"][0]
    assert first_mention["start"] == 10
    assert first_mention["end"] == 13
    assert first_mention["annotation_count"] == 2
    assert first_mention["annotator_count"] == 2
    assert [item["source"] for item in first_mention["annotators"]] == ["bern2", "pubtator3"]
    assert {item["canonical_id"] for item in first_mention["annotators"]} == {
        "BERN:glioblastoma",
        "MESH:D005909",
    }

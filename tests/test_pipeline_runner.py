from __future__ import annotations

import json
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO

from bio_annotation.cli import main
from bio_annotation.pipeline_runner import _read_pubtator3_options, run_pipeline_from_config


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


def test_run_pipeline_from_config_with_pmids(tmp_path) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "pmids"',
                'pmids = ["12345678"]',
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
        pmid_fetcher=lambda pmid: {
            "pmid": pmid,
            "pmcid": "PMC1234567",
            "title": "PTEN regulates glioblastoma",
            "abstract": "PTEN is important in glioblastoma.",
            "year": "2024",
        },
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
    assert payload["pipeline"]["annotator_settings"]["pubtator3"]["timeout"] == 45
    assert payload["documents"][0]["metadata"]["pubmed_record"]["pmcid"] == "PMC1234567"
    assert payload["annotation_summary"]["annotation_count"] == 2
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
        "bio_annotation.pipeline_runner.run_pipeline_from_config",
        lambda path: {
            "document_count": 1,
            "pipeline": {
                "mode": "ingestion_and_annotation",
                "annotators_enabled": ["flair"],
                "annotator_settings": {"flair": {}},
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

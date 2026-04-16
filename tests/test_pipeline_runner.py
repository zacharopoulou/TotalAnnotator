from __future__ import annotations

import json
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO

from bio_annotation.cli import main
from bio_annotation.pipeline_runner import run_pipeline_from_config


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
                "[annotators]",
                'enabled = ["bern2", "pubtator"]',
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
            "title": "PTEN regulates glioblastoma",
            "abstract": "PTEN is important in glioblastoma.",
            "year": "2024",
        },
        bern2_request_fn=lambda document: {
            "annotations": [
                {"mention": "PTEN", "span": {"begin": 0, "end": 4}, "type": "Gene", "id": "NCBIGene:5728"}
            ]
        },
        pubtator_request_fn=lambda document: {
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
    assert payload["documents"][0]["annotation_count"] == 2


def test_cli_run_config_outputs_payload(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "text_table"',
                f'text_file = "{tmp_path / "documents.csv"}"',
                'format = "csv"',
                'document_id_column = "document_id"',
                'title_column = "title"',
                'abstract_column = "abstract"',
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
            "annotators": ["flair"],
            "entity_types": ["gene"],
            "documents": [],
        },
    )

    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(["run-config", "--config", str(config_path)])

    output = json.loads(stream.getvalue())
    assert exit_code == 0
    assert output["stage"] == "corpus"
    assert output["annotators"] == ["flair"]


def test_cli_run_config_ingestion_only(tmp_path) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "corpus"',
                f'corpus_path = "{tmp_path / "documents.json"}"',
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
    assert output["annotators"] == []
    assert output["documents"][0]["annotation_count"] == 0

from __future__ import annotations

from bio_annotation.pipeline_runner import run_pipeline_from_config


def test_run_pipeline_from_config_without_annotators(tmp_path) -> None:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        "\n".join(
            [
                "[input]",
                'mode = "pmids"',
                'pmids = ["12345678"]',
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

    payload = run_pipeline_from_config(
        config_path,
        pmid_fetcher=lambda pmid: {
            "pmid": pmid,
            "title": "PTEN regulates glioblastoma",
            "abstract": "PTEN is important in glioblastoma.",
            "year": "2024",
        },
    )

    assert payload["document_count"] == 1
    assert payload["stage"] == "corpus"
    assert payload["input"]["mode"] == "pmids"
    assert payload["annotators"] == []
    assert payload["documents"][0]["annotation_count"] == 0
    assert payload["documents"][0]["annotations"] == []
    assert payload["documents"][0]["document"]["metadata"]["pubmed_record"]["pmid"] == "12345678"


def test_run_pipeline_from_config_writes_output_file(tmp_path) -> None:
    output_path = tmp_path / "outputs" / "pipeline.json"
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
                f'path = "{output_path}"',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "documents.json").write_text(
        '{"documents":[{"document_id":"doc1","title":"PTEN regulates glioblastoma","abstract":"PTEN is important.","source":"corpus"}]}',
        encoding="utf-8",
    )

    payload = run_pipeline_from_config(config_path)

    assert payload["document_count"] == 1
    assert output_path.exists()

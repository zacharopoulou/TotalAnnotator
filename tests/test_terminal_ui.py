from __future__ import annotations

import json
from pathlib import Path

from bio_annotation.pipeline_config import load_pipeline_config
from bio_annotation.terminal_ui import (
    TerminalUIAnswers,
    _entity_type_choices_for,
    build_terminal_ui_config_text,
    create_run_paths,
    find_unsupported_entity_types,
    parse_pmids,
    run_terminal_annotation_ui,
)


def test_parse_pmids_deduplicates_common_separators() -> None:
    assert parse_pmids("123, 456\n123 789") == ["123", "456", "789"]


def test_entity_type_choices_are_annotator_aware() -> None:
    # Without a clinical annotator, no clinical types like sign_symptom are offered.
    without_clinical = [value for value, _ in _entity_type_choices_for(["pubtator3", "bern2", "flair"])]
    assert "disease" in without_clinical
    assert "sign_symptom" not in without_clinical

    # The bio types a pubtator3 selection offers, used as the expected leading prefix
    # for a clinical selection that shares pubtator3 (but not bern2's cell/dna/rna).
    bio = [value for value, _ in _entity_type_choices_for(["pubtator3"])]

    # Selecting apollo surfaces its clinical types as selectable choices, with the
    # canonical bio types still listed first.
    with_apollo = _entity_type_choices_for(["pubtator3", "apollo"])
    values = [value for value, _ in with_apollo]
    assert values[: len(bio)] == bio
    assert "sign_symptom" in values
    assert "lab_value" in values
    labels = dict(with_apollo)
    assert labels["sign_symptom"] == "Sign symptom"


def test_find_unsupported_entity_types_reports_exact_compatibility() -> None:
    assert find_unsupported_entity_types(["bern2", "flair"], ["variant", "cell_line", "cell_type"]) == {
        "flair": ["variant", "cell_type"],
    }


def test_build_terminal_ui_config_for_plain_text(tmp_path) -> None:
    source_text = tmp_path / "doc1.txt"
    source_text.write_text("PTEN is important in glioblastoma.", encoding="utf-8")
    paths = create_run_paths(tmp_path / "out")
    answers = TerminalUIAnswers(
        input_mode="plain_text",
        pmids=[],
        pmid_file=None,
        plain_text_file=source_text,
        plain_text_document_id="doc1",
        plain_text_title="PTEN regulates glioblastoma",
        annotators=["pubtator3"],
        entity_types=["gene", "disease"],
    )

    config_path = paths.run_dir / "config.toml"
    config_path.write_text(build_terminal_ui_config_text(answers, paths), encoding="utf-8")
    paths.plain_text_path.write_text(
        "document_id\ttitle\tabstract\n"
        "doc1\tPTEN regulates glioblastoma\tPTEN is important in glioblastoma.\n",
        encoding="utf-8",
    )

    config = load_pipeline_config(config_path)

    assert config.input_mode == "text_table"
    assert config.text_file == paths.plain_text_path
    assert config.text_format == "tsv"
    assert config.annotators == ["pubtator3"]
    assert config.entity_types == ["gene", "disease"]
    assert config.annotator_settings["pubtator3"]["mode"] == "text_only"
    assert config.annotator_settings["pubtator3"]["max_poll_attempts"] == 30
    assert config.output_path == paths.results_path


def test_build_terminal_ui_config_for_pmid_file(tmp_path) -> None:
    pmid_file = tmp_path / "pmids.txt"
    pmid_file.write_text("123\n456\n", encoding="utf-8")
    paths = create_run_paths(tmp_path / "out")
    answers = TerminalUIAnswers(
        input_mode="pmid_file",
        pmids=[],
        pmid_file=pmid_file,
        annotators=["pubtator3"],
        entity_types=[],
    )

    config_path = paths.run_dir / "config.toml"
    config_path.write_text(build_terminal_ui_config_text(answers, paths), encoding="utf-8")

    config = load_pipeline_config(config_path)

    assert config.input_mode == "pmid_file"
    assert config.pmid_file == pmid_file
    assert config.annotators == ["pubtator3"]
    assert config.annotator_settings["pubtator3"]["mode"] == "auto"


def test_build_terminal_ui_config_includes_bern2_endpoint(tmp_path) -> None:
    paths = create_run_paths(tmp_path / "out")
    answers = TerminalUIAnswers(
        input_mode="pmids",
        pmids=["123"],
        pmid_file=None,
        annotators=["bern2"],
        entity_types=["gene"],
    )

    config_text = build_terminal_ui_config_text(answers, paths)

    assert "[annotators.bern2]" in config_text
    assert 'endpoint = "http://bern2.korea.ac.kr/plain"' in config_text


def test_run_terminal_annotation_ui_writes_reproducible_plain_text_run(tmp_path) -> None:
    source_text = tmp_path / "doc1.txt"
    source_text.write_text("PTEN is important in glioblastoma.\nEGFR is also relevant.\n", encoding="utf-8")
    output_dir = tmp_path / "out"
    prompts = iter(
        [
            "3",  # plain text
            "2",  # raw text file
            str(source_text),
            "1",  # pubtator3
            "1,2",  # Gene, Disease
        ]
    )
    messages: list[str] = []

    def fake_input(prompt: str) -> str:
        return next(prompts)

    def fake_output(message: str) -> None:
        messages.append(message)

    def fake_pipeline_run(config_path: Path) -> dict[str, object]:
        config = load_pipeline_config(config_path)
        assert config.input_mode == "text_table"
        assert config.annotators == ["pubtator3"]
        assert config.entity_types == ["gene", "disease"]
        assert config.text_file is not None
        assert config.text_file.read_text(encoding="utf-8") == (
            "document_id\ttitle\tabstract\n"
            "text-1\t\tPTEN is important in glioblastoma.\n"
            "text-2\t\tEGFR is also relevant.\n"
        )
        payload = {
            "document_count": 2,
            "annotation_summary": {
                "annotators_enabled": ["pubtator3"],
                "document_count": 2,
                "annotation_count": 2,
            },
            "documents": [],
            "annotations": [],
            "document_annotations": [],
        }
        config.output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    payload = run_terminal_annotation_ui(
        runs_dir=output_dir,
        input_fn=fake_input,
        output_fn=fake_output,
        pipeline_run_fn=fake_pipeline_run,
    )

    assert (output_dir / "config.toml").exists()
    assert (output_dir / "plain_text.tsv").exists()
    assert (output_dir / "results.json").exists()
    assert (output_dir / "results.keywords.tsv").exists()
    assert (output_dir / "results.keyword_annotator_evidence.tsv").exists()
    assert (output_dir / "results.annotations.tsv").exists()
    assert (output_dir / "run_manifest.json").exists()

    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["input_mode"] == "plain_text"
    assert manifest["plain_text_file"] == str(source_text)
    assert manifest["plain_text_path"].endswith("plain_text.tsv")
    assert manifest["results_path"] == str(output_dir / "results.json")
    assert manifest["tsv_paths"] == {
        "Keywords TSV": str(output_dir / "results.keywords.tsv"),
        "Keyword evidence TSV": str(output_dir / "results.keyword_annotator_evidence.tsv"),
        "Annotations TSV": str(output_dir / "results.annotations.tsv"),
    }
    assert manifest["annotators"] == ["pubtator3"]
    assert manifest["annotator_labels"] == ["PubTator3"]
    assert manifest["entity_types"] == ["gene", "disease"]
    assert manifest["entity_type_labels"] == ["Gene / protein", "Disease"]
    assert manifest["document_count"] == 2
    assert manifest["annotation_count"] == 2
    assert payload["document_count"] == 2
    assert "Run complete" in messages
    assert f"Keywords TSV: {output_dir / 'results.keywords.tsv'}" in messages
    assert f"Keyword evidence TSV: {output_dir / 'results.keyword_annotator_evidence.tsv'}" in messages
    assert f"Annotations TSV: {output_dir / 'results.annotations.tsv'}" in messages


def test_run_terminal_annotation_ui_uses_one_raw_text_line_per_document(tmp_path) -> None:
    source_text = tmp_path / "doc1.txt"
    source_text.write_text("\nPTEN is important in glioblastoma.\n\nEGFR is also relevant.\n", encoding="utf-8")
    output_dir = tmp_path / "out"
    prompts = iter(
        [
            "3",  # plain text
            "2",  # raw text file
            str(source_text),
            "1",  # pubtator3
            "",  # all entity types
        ]
    )

    def fake_input(prompt: str) -> str:
        return next(prompts)

    def fake_pipeline_run(config_path: Path) -> dict[str, object]:
        config = load_pipeline_config(config_path)
        assert config.text_file is not None
        assert config.text_file.read_text(encoding="utf-8") == (
            "document_id\ttitle\tabstract\n"
            "text-1\t\tPTEN is important in glioblastoma.\n"
            "text-2\t\tEGFR is also relevant.\n"
        )
        return {
            "document_count": 2,
            "annotation_summary": {"annotation_count": 0},
            "documents": [],
            "annotations": [],
            "document_annotations": [],
        }

    run_terminal_annotation_ui(
        runs_dir=output_dir,
        input_fn=fake_input,
        output_fn=lambda message: None,
        pipeline_run_fn=fake_pipeline_run,
    )

    assert (output_dir / "plain_text.tsv").read_text(encoding="utf-8").count("text-") == 2


def test_run_terminal_annotation_ui_uses_existing_pmid_file(tmp_path) -> None:
    output_dir = tmp_path / "out"
    pmid_file = tmp_path / "pmids.txt"
    pmid_file.write_text("123\n456\n", encoding="utf-8")
    prompts = iter(
        [
            "2",  # PMID file
            str(pmid_file),
            "1",  # pubtator3
            "",  # all entity types
        ]
    )

    def fake_input(prompt: str) -> str:
        return next(prompts)

    def fake_pipeline_run(config_path: Path) -> dict[str, object]:
        config = load_pipeline_config(config_path)
        assert config.input_mode == "pmid_file"
        assert config.pmid_file == pmid_file.resolve()
        assert config.pmid_file.read_text(encoding="utf-8") == "123\n456\n"
        return {
            "document_count": 2,
            "annotation_summary": {"annotation_count": 0},
            "documents": [],
            "annotations": [],
            "document_annotations": [],
        }

    run_terminal_annotation_ui(
        runs_dir=output_dir,
        input_fn=fake_input,
        output_fn=lambda message: None,
        pipeline_run_fn=fake_pipeline_run,
    )

    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["input_mode"] == "pmid_file"
    assert manifest["pmid_file"] == str(pmid_file.resolve())


def test_run_terminal_annotation_ui_defaults_to_all_annotators(tmp_path) -> None:
    output_dir = tmp_path / "out"
    prompts = iter(
        [
            "1",  # PMIDs
            "123",
            "",  # all annotators
            "",  # all entity types
        ]
    )
    seen_prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        seen_prompts.append(prompt)
        return next(prompts)

    def fake_pipeline_run(config_path: Path) -> dict[str, object]:
        config = load_pipeline_config(config_path)
        assert config.input_mode == "pmids"
        assert config.annotators == ["pubtator3", "bern2", "flair"]
        return {
            "document_count": 1,
            "annotation_summary": {"annotation_count": 0},
            "documents": [],
            "annotations": [],
            "document_annotations": [],
        }

    run_terminal_annotation_ui(
        runs_dir=output_dir,
        input_fn=fake_input,
        output_fn=lambda message: None,
        pipeline_run_fn=fake_pipeline_run,
    )

    assert "Choose comma-separated numbers [default: 1, 2, 3]: " in seen_prompts


def test_run_terminal_annotation_ui_warns_for_unsupported_entity_types(tmp_path) -> None:
    source_text = tmp_path / "doc1.txt"
    source_text.write_text("PTEN is important in glioblastoma.", encoding="utf-8")
    prompts = iter(
        [
            "3",  # plain text
            "2",  # raw text file
            str(source_text),
            "2,3",  # BERN2, Flair
            "5,6",  # Variant / mutation, Cell line
            "y",
        ]
    )
    messages: list[str] = []

    def fake_input(prompt: str) -> str:
        return next(prompts)

    def fake_pipeline_run(config_path: Path) -> dict[str, object]:
        config = load_pipeline_config(config_path)
        assert config.annotators == ["bern2", "flair"]
        assert config.entity_types == ["variant", "cell_line"]
        return {
            "document_count": 1,
            "annotation_summary": {"annotation_count": 0},
            "documents": [],
            "annotations": [],
            "document_annotations": [],
        }

    run_terminal_annotation_ui(
        runs_dir=tmp_path / "out",
        input_fn=fake_input,
        output_fn=messages.append,
        pipeline_run_fn=fake_pipeline_run,
    )

    assert "Entity type compatibility warning:" in messages
    assert any("Flair / HunFlair does not produce: Variant / mutation" in message for message in messages)
    assert not any("BERN2 does not produce" in message for message in messages)

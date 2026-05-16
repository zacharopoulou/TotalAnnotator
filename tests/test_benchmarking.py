from __future__ import annotations

import json

import pytest

from bio_annotation.benchmarking.config import benchmark_annotator_options
from bio_annotation.benchmarking.metrics import ScoredPrediction, evaluate_annotator
from bio_annotation.benchmarking.ncbi import case_from_bigbio_row, load_ncbi_cases
from bio_annotation.benchmarking.preflight import (
    BenchmarkPreflightError,
    preflight_benchmark_annotators,
)
from bio_annotation.benchmarking.runner import run_ncbi_review_evaluation
from bio_annotation.schemas.entity import Annotation


def _sample_ncbi_row(document_id: str = "12345678") -> dict[str, object]:
    return {
        "document_id": document_id,
        "passages": [
            {
                "type": "title",
                "text": ["PTEN disease study"],
                "offsets": [0],
            },
            {
                "type": "abstract",
                "text": ["Glioblastoma is aggressive."],
                "offsets": [100],
            },
        ],
        "entities": [
            {
                "id": "T1",
                "type": "Disease",
                "text": ["Glioblastoma"],
                "offsets": [[100, 112]],
                "normalized": [{"db_name": "MESH", "db_id": "D005909"}],
            }
        ],
    }


def _real_shape_ncbi_row() -> dict[str, object]:
    return {
        "id": "9949209",
        "document_id": "9949209",
        "passages": [
            {
                "id": "9949209_title",
                "type": "title",
                "text": ["Genetic mapping of the copper toxicosis locus."],
                "offsets": [[0, 46]],
            },
            {
                "id": "9949209_abstract",
                "type": "abstract",
                "text": ["Wilson disease causes hepatic copper accumulation."],
                "offsets": [[47, 94]],
            },
        ],
        "entities": [
            {
                "id": "9949209_OMIM:215600_0",
                "type": "Modifier",
                "text": ["copper toxicosis"],
                "offsets": [[23, 39]],
                "normalized": [{"db_name": "OMIM", "db_id": "215600"}],
            },
            {
                "id": "9949209_D006527_1",
                "type": "SpecificDisease",
                "text": ["Wilson disease"],
                "offsets": [[47, 61]],
                "normalized": [{"db_name": "MESH", "db_id": "D006527"}],
            },
            {
                "id": "9949209_D008107_2",
                "type": "DiseaseClass",
                "text": ["hepatic copper accumulation"],
                "offsets": [[69, 96]],
                "normalized": [{"db_name": "MESH", "db_id": "D008107"}],
            },
        ],
    }


def test_ncbi_loader_builds_canonical_document_and_shifts_offsets() -> None:
    case = case_from_bigbio_row(_sample_ncbi_row(), row_index=1)

    assert case.document.document_id == "12345678"
    assert case.document.title == "PTEN disease study"
    assert case.document.abstract == "Glioblastoma is aggressive."
    assert case.document.text == "PTEN disease study\n\nGlioblastoma is aggressive."
    assert case.warnings == []

    gold = case.gold_annotations[0]
    assert gold.start == 20
    assert gold.end == 32
    assert case.document.text[gold.start : gold.end] == "Glioblastoma"
    assert gold.normalized_ids == ("MESH:D005909",)


def test_ncbi_loader_accepts_real_disease_subtypes_and_pair_offsets() -> None:
    case = case_from_bigbio_row(_real_shape_ncbi_row(), row_index=1)

    assert len(case.gold_annotations) == 3
    assert [gold.raw_entity_type for gold in case.gold_annotations] == [
        "Modifier",
        "SpecificDisease",
        "DiseaseClass",
    ]
    assert [gold.entity_type for gold in case.gold_annotations] == [
        "disease",
        "disease",
        "disease",
    ]
    assert case.gold_annotations[0].start == 23
    assert case.gold_annotations[0].end == 39
    assert case.gold_annotations[1].start == 48
    assert case.gold_annotations[1].end == 62
    assert case.document.text[48:62] == "Wilson disease"
    assert case.gold_annotations[2].normalized_ids == ("MESH:D008107",)


def test_load_ncbi_cases_from_jsonl_path(tmp_path) -> None:
    path = tmp_path / "test.jsonl"
    path.write_text(json.dumps(_sample_ncbi_row()) + "\n", encoding="utf-8")

    cases = load_ncbi_cases(path)

    assert len(cases) == 1
    assert cases[0].document.document_id == "12345678"
    assert len(cases[0].gold_annotations) == 1


def test_evaluate_annotator_reports_strict_and_lenient_scores() -> None:
    case = case_from_bigbio_row(_sample_ncbi_row(), row_index=1)
    exact_prediction = ScoredPrediction(
        document_id=case.document.document_id,
        annotation=Annotation(
            annotation_id="pred-1",
            source="fake",
            span_text="Glioblastoma",
            start=20,
            end=32,
            entity_type="disease",
        ),
    )
    boundary_prediction = ScoredPrediction(
        document_id=case.document.document_id,
        annotation=Annotation(
            annotation_id="pred-2",
            source="fake",
            span_text="Glioblastoma is",
            start=20,
            end=35,
            entity_type="disease",
        ),
    )

    exact = evaluate_annotator(
        annotator="fake",
        predictions=[exact_prediction],
        gold_annotations=case.gold_annotations,
    )
    boundary = evaluate_annotator(
        annotator="fake",
        predictions=[boundary_prediction],
        gold_annotations=case.gold_annotations,
    )

    assert exact.strict.true_positive == 1
    assert exact.lenient.true_positive == 1
    assert boundary.strict.true_positive == 0
    assert boundary.strict.false_positive == 1
    assert boundary.strict.false_negative == 1
    assert boundary.lenient.true_positive == 1


def test_evaluate_annotator_matches_only_within_same_document() -> None:
    first_case = case_from_bigbio_row(_sample_ncbi_row("doc-a"), row_index=1)
    second_case = case_from_bigbio_row(_sample_ncbi_row("doc-b"), row_index=2)
    wrong_document_prediction = ScoredPrediction(
        document_id="doc-b",
        annotation=Annotation(
            annotation_id="pred-1",
            source="fake",
            span_text="Glioblastoma",
            start=20,
            end=32,
            entity_type="disease",
        ),
    )

    result = evaluate_annotator(
        annotator="fake",
        predictions=[wrong_document_prediction],
        gold_annotations=first_case.gold_annotations + second_case.gold_annotations,
    )

    assert result.strict.true_positive == 1
    assert result.strict.false_positive == 0
    assert result.strict.false_negative == 1


def test_benchmark_annotator_options_include_runtime_defaults() -> None:
    options = benchmark_annotator_options()

    assert options["bern2"]["endpoint"] == "http://bern2.korea.ac.kr/plain"
    assert options["flair"]["model"] == "hunflair2"
    assert options["pubtator3"]["mode"] == "auto"


def test_benchmark_annotator_options_allow_targeted_overrides() -> None:
    options = benchmark_annotator_options({"flair": {"model": "custom-model"}})

    assert options["flair"]["model"] == "custom-model"
    assert options["bern2"]["endpoint"] == "http://bern2.korea.ac.kr/plain"


def test_preflight_reports_remote_and_loads_flair_once() -> None:
    loaded_models: list[str] = []
    sentinel_tagger = object()

    def fake_loader(model: str) -> object:
        loaded_models.append(model)
        return sentinel_tagger

    results, resources = preflight_benchmark_annotators(
        ["bern2", "flair"],
        benchmark_annotator_options(),
        flair_tagger_loader=fake_loader,
    )

    assert loaded_models == ["hunflair2"]
    assert resources["flair_tagger"] is sentinel_tagger
    assert [result.name for result in results] == ["bern2", "flair"]
    assert results[0].status == "configured"
    assert results[1].status == "ready"


def test_preflight_fails_once_with_clear_flair_context() -> None:
    def missing_model_loader(model: str) -> object:
        raise FileNotFoundError(f"missing {model}")

    with pytest.raises(BenchmarkPreflightError) as exc_info:
        preflight_benchmark_annotators(
            ["flair"],
            benchmark_annotator_options(),
            flair_tagger_loader=missing_model_loader,
        )

    message = exc_info.value.result.message
    assert "Benchmark config is being used" in message
    assert "Flair is being called" in message
    assert "model 'hunflair2'" in message
    assert "not available through Flair's classifier loader" in message


def test_review_runner_uses_mocked_annotators_and_writes_outputs(tmp_path) -> None:
    benchmark_path = tmp_path / "test.jsonl"
    output_dir = tmp_path / "outputs"
    benchmark_path.write_text(json.dumps(_sample_ncbi_row()) + "\n", encoding="utf-8")

    def fake_bern2(document):
        assert document.document_id == "12345678"
        return {
            "annotations": [
                {
                    "mention": "Glioblastoma",
                    "span": {"begin": 20, "end": 32},
                    "type": "Disease",
                    "id": "MESH:D005909",
                }
            ]
        }

    payload = run_ncbi_review_evaluation(
        benchmark_path=benchmark_path,
        annotators=["bern2"],
        output_dir=output_dir,
        bern2_request_fn=fake_bern2,
    )

    assert payload["document_count"] == 1
    assert payload["gold_count"] == 1
    assert payload["annotator_options"]["bern2"]["endpoint"] == "http://bern2.korea.ac.kr/plain"
    assert payload["preflight"][0]["name"] == "bern2"
    assert payload["metrics"][0]["strict"]["true_positive"] == 1
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "metrics_by_annotator.tsv").exists()
    assert (output_dir / "gold.jsonl").exists()
    assert (output_dir / "predictions.jsonl").exists()
    assert (output_dir / "preflight.tsv").exists()


def test_review_runner_preloads_flair_once_for_all_documents(tmp_path) -> None:
    benchmark_path = tmp_path / "test.jsonl"
    benchmark_path.write_text(
        json.dumps(_sample_ncbi_row("doc-a")) + "\n" + json.dumps(_sample_ncbi_row("doc-b")) + "\n",
        encoding="utf-8",
    )
    loaded_models: list[str] = []

    class FakeTagger:
        def predict(self, sentence):
            return None

    def fake_loader(model: str) -> FakeTagger:
        loaded_models.append(model)
        return FakeTagger()

    payload = run_ncbi_review_evaluation(
        benchmark_path=benchmark_path,
        annotators=["flair"],
        flair_tagger_loader=fake_loader,
    )

    assert loaded_models == ["hunflair2"]
    assert payload["document_count"] == 2
    assert payload["preflight"][0]["status"] == "ready"


def test_review_runner_reports_progress(tmp_path) -> None:
    benchmark_path = tmp_path / "test.jsonl"
    benchmark_path.write_text(
        "".join(json.dumps(_sample_ncbi_row(f"doc-{index}")) + "\n" for index in range(1, 4)),
        encoding="utf-8",
    )
    progress: list[tuple[int, int, str]] = []

    def fake_bern2(document):
        return {"annotations": []}

    run_ncbi_review_evaluation(
        benchmark_path=benchmark_path,
        annotators=["bern2"],
        bern2_request_fn=fake_bern2,
        progress_callback=lambda index, total, document_id: progress.append((index, total, document_id)),
        progress_interval=2,
    )

    assert progress == [(1, 3, "doc-1"), (2, 3, "doc-2"), (3, 3, "doc-3")]

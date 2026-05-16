from __future__ import annotations

import json

from bio_annotation.benchmarking.metrics import evaluate_annotator
from bio_annotation.benchmarking.ncbi import case_from_bigbio_row, load_ncbi_cases
from bio_annotation.benchmarking.runner import run_ncbi_review_evaluation
from bio_annotation.schemas.entity import Annotation


def _sample_ncbi_row() -> dict[str, object]:
    return {
        "document_id": "12345678",
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


def test_load_ncbi_cases_from_jsonl_path(tmp_path) -> None:
    path = tmp_path / "test.jsonl"
    path.write_text(json.dumps(_sample_ncbi_row()) + "\n", encoding="utf-8")

    cases = load_ncbi_cases(path)

    assert len(cases) == 1
    assert cases[0].document.document_id == "12345678"
    assert len(cases[0].gold_annotations) == 1


def test_evaluate_annotator_reports_strict_and_lenient_scores() -> None:
    case = case_from_bigbio_row(_sample_ncbi_row(), row_index=1)
    exact_prediction = Annotation(
        annotation_id="pred-1",
        source="fake",
        span_text="Glioblastoma",
        start=20,
        end=32,
        entity_type="disease",
    )
    boundary_prediction = Annotation(
        annotation_id="pred-2",
        source="fake",
        span_text="Glioblastoma is",
        start=20,
        end=35,
        entity_type="disease",
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
    assert payload["metrics"][0]["strict"]["true_positive"] == 1
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "metrics_by_annotator.tsv").exists()
    assert (output_dir / "gold.jsonl").exists()
    assert (output_dir / "predictions.jsonl").exists()

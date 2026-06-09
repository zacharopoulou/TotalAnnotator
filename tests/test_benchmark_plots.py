from __future__ import annotations

from bio_annotation.benchmarking.runner import write_review_outputs


def test_write_review_outputs_creates_plots(tmp_path) -> None:
    payload = {
        "benchmark": "ncbi_disease",
        "split": "test",
        "entity_type": "disease",
        "document_count": 1,
        "gold_count": 1,
        "annotators": ["bern2", "pubtator3", "flair"],
        "annotator_options": {},
        "preflight": [],
        "metrics": [
            {
                "annotator": "bern2",
                "prediction_count": 1,
                "gold_count": 1,
                "strict": {
                    "true_positive": 1,
                    "false_positive": 0,
                    "false_negative": 0,
                    "precision": 1.0,
                    "recall": 1.0,
                    "f1": 1.0,
                },
                "lenient": {
                    "true_positive": 1,
                    "false_positive": 0,
                    "false_negative": 0,
                    "precision": 1.0,
                    "recall": 1.0,
                    "f1": 1.0,
                },
                "strict_normalization": {
                    "span_matches": 1,
                    "correct": 1,
                    "incorrect": 0,
                    "missing_prediction_id": 0,
                    "missing_gold_id": 0,
                    "accuracy_on_matched_spans": 1.0,
                    "prediction_id_coverage_on_matched_spans": 1.0,
                },
                "lenient_normalization": {
                    "span_matches": 1,
                    "correct": 1,
                    "incorrect": 0,
                    "missing_prediction_id": 0,
                    "missing_gold_id": 0,
                    "accuracy_on_matched_spans": 1.0,
                    "prediction_id_coverage_on_matched_spans": 1.0,
                },
            },
            {
                "annotator": "pubtator3",
                "prediction_count": 1,
                "gold_count": 1,
                "strict": {
                    "true_positive": 0,
                    "false_positive": 1,
                    "false_negative": 1,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                },
                "lenient": {
                    "true_positive": 1,
                    "false_positive": 0,
                    "false_negative": 0,
                    "precision": 1.0,
                    "recall": 1.0,
                    "f1": 1.0,
                },
                "strict_normalization": {
                    "span_matches": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "missing_prediction_id": 0,
                    "missing_gold_id": 0,
                    "accuracy_on_matched_spans": 0.0,
                    "prediction_id_coverage_on_matched_spans": 0.0,
                },
                "lenient_normalization": {
                    "span_matches": 1,
                    "correct": 0,
                    "incorrect": 1,
                    "missing_prediction_id": 0,
                    "missing_gold_id": 0,
                    "accuracy_on_matched_spans": 0.0,
                    "prediction_id_coverage_on_matched_spans": 1.0,
                },
            },
            {
                "annotator": "flair",
                "prediction_count": 0,
                "gold_count": 1,
                "strict": {
                    "true_positive": 0,
                    "false_positive": 0,
                    "false_negative": 1,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                },
                "lenient": {
                    "true_positive": 0,
                    "false_positive": 0,
                    "false_negative": 1,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                },
                "strict_normalization": {
                    "span_matches": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "missing_prediction_id": 0,
                    "missing_gold_id": 0,
                    "accuracy_on_matched_spans": 0.0,
                    "prediction_id_coverage_on_matched_spans": 0.0,
                },
                "lenient_normalization": {
                    "span_matches": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "missing_prediction_id": 0,
                    "missing_gold_id": 0,
                    "accuracy_on_matched_spans": 0.0,
                    "prediction_id_coverage_on_matched_spans": 0.0,
                },
            },
        ],
        "error_analysis": {},
        "statuses": [],
        "warnings": [],
        "gold_annotations": [
            {
                "annotation_id": "gold-1",
                "document_id": "doc-1",
                "span_text": "Glioblastoma",
                "start": 0,
                "end": 12,
                "entity_type": "disease",
                "normalized_ids": ["MESH:D005909"],
                "raw_entity_type": "SpecificDisease",
            }
        ],
        "predictions": {
            "bern2": [
                {
                    "document_id": "doc-1",
                    "span_text": "Glioblastoma",
                    "start": 0,
                    "end": 12,
                    "entity_type": "disease",
                    "canonical_id": "mesh:D005909",
                }
            ],
            "pubtator3": [
                {
                    "document_id": "doc-1",
                    "span_text": "Glioblastoma disease",
                    "start": 0,
                    "end": 20,
                    "entity_type": "disease",
                    "canonical_id": "MESH:D000000",
                }
            ],
            "flair": [],
        },
    }

    write_review_outputs(payload, tmp_path)

    plots_dir = tmp_path / "plots"
    for filename in [
        "metrics_overview.png",
        "coverage_groups.png",
        "normalization_accuracy.png",
        "annotator_combination_performance.png",
    ]:
        path = plots_dir / filename
        assert path.exists()
        assert path.stat().st_size > 0
    assert not (plots_dir / "consensus_gold_coverage.png").exists()

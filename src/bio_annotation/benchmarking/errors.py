from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from bio_annotation.benchmarking.metrics import ScoredPrediction
from bio_annotation.benchmarking.ncbi import GoldAnnotation
from bio_annotation.schemas.entity import Annotation


@dataclass(slots=True)
class ErrorAnalysis:
    false_positives: list[dict[str, Any]]
    false_negatives: list[dict[str, Any]]
    boundary_errors: list[dict[str, Any]]

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "boundary_errors": self.boundary_errors,
        }


def build_error_analysis(
    *,
    annotator: str,
    predictions: Iterable[ScoredPrediction],
    gold_annotations: Iterable[GoldAnnotation],
    entity_type: str = "disease",
) -> ErrorAnalysis:
    filtered_predictions = _filter_predictions(predictions, entity_type=entity_type)
    filtered_gold = [gold for gold in gold_annotations if gold.entity_type == entity_type]

    predictions_by_document: dict[str, list[Annotation]] = defaultdict(list)
    gold_by_document: dict[str, list[GoldAnnotation]] = defaultdict(list)
    for scored in filtered_predictions:
        predictions_by_document[scored.document_id].append(scored.annotation)
    for gold in filtered_gold:
        gold_by_document[gold.document_id].append(gold)

    false_positives: list[dict[str, Any]] = []
    false_negatives: list[dict[str, Any]] = []
    boundary_errors: list[dict[str, Any]] = []

    for document_id in sorted(set(predictions_by_document) | set(gold_by_document)):
        document_predictions = predictions_by_document.get(document_id, [])
        document_gold = gold_by_document.get(document_id, [])
        strict_matches = _strict_matches(document_predictions, document_gold)
        lenient_matches = _lenient_matches(
            document_predictions,
            document_gold,
            excluded_pairs=strict_matches,
        )

        strict_prediction_indexes = {prediction_index for prediction_index, _ in strict_matches}
        strict_gold_indexes = {gold_index for _, gold_index in strict_matches}
        boundary_prediction_indexes = {prediction_index for prediction_index, _ in lenient_matches}
        boundary_gold_indexes = {gold_index for _, gold_index in lenient_matches}

        for prediction_index, gold_index in lenient_matches:
            prediction = document_predictions[prediction_index]
            gold = document_gold[gold_index]
            boundary_errors.append(
                {
                    "annotator": annotator,
                    "document_id": document_id,
                    "prediction_text": prediction.span_text,
                    "prediction_start": prediction.start,
                    "prediction_end": prediction.end,
                    "prediction_entity_type": prediction.entity_type,
                    "prediction_canonical_id": prediction.canonical_id,
                    "gold_text": gold.span_text,
                    "gold_start": gold.start,
                    "gold_end": gold.end,
                    "gold_entity_type": gold.entity_type,
                    "gold_raw_entity_type": gold.raw_entity_type,
                    "gold_normalized_ids": ";".join(gold.normalized_ids),
                    "overlap_length": _overlap_length(prediction, gold),
                }
            )

        matched_prediction_indexes = strict_prediction_indexes | boundary_prediction_indexes
        matched_gold_indexes = strict_gold_indexes | boundary_gold_indexes

        for prediction_index, prediction in enumerate(document_predictions):
            if prediction_index in matched_prediction_indexes:
                continue
            nearest_gold = _nearest_gold(prediction, document_gold)
            false_positives.append(
                {
                    "annotator": annotator,
                    "document_id": document_id,
                    "prediction_text": prediction.span_text,
                    "prediction_start": prediction.start,
                    "prediction_end": prediction.end,
                    "prediction_entity_type": prediction.entity_type,
                    "prediction_canonical_id": prediction.canonical_id,
                    "nearest_gold_text": nearest_gold.span_text if nearest_gold else None,
                    "nearest_gold_start": nearest_gold.start if nearest_gold else None,
                    "nearest_gold_end": nearest_gold.end if nearest_gold else None,
                    "nearest_gold_raw_entity_type": nearest_gold.raw_entity_type if nearest_gold else None,
                }
            )

        for gold_index, gold in enumerate(document_gold):
            if gold_index in matched_gold_indexes:
                continue
            nearest_prediction = _nearest_prediction(gold, document_predictions)
            false_negatives.append(
                {
                    "annotator": annotator,
                    "document_id": document_id,
                    "gold_text": gold.span_text,
                    "gold_start": gold.start,
                    "gold_end": gold.end,
                    "gold_entity_type": gold.entity_type,
                    "gold_raw_entity_type": gold.raw_entity_type,
                    "gold_normalized_ids": ";".join(gold.normalized_ids),
                    "nearest_prediction_text": nearest_prediction.span_text if nearest_prediction else None,
                    "nearest_prediction_start": nearest_prediction.start if nearest_prediction else None,
                    "nearest_prediction_end": nearest_prediction.end if nearest_prediction else None,
                    "nearest_prediction_entity_type": nearest_prediction.entity_type if nearest_prediction else None,
                    "nearest_prediction_canonical_id": nearest_prediction.canonical_id if nearest_prediction else None,
                }
            )

    return ErrorAnalysis(
        false_positives=false_positives,
        false_negatives=false_negatives,
        boundary_errors=boundary_errors,
    )


def _filter_predictions(
    predictions: Iterable[ScoredPrediction],
    *,
    entity_type: str,
) -> list[ScoredPrediction]:
    normalized_type = entity_type.strip().lower()
    out: list[ScoredPrediction] = []
    for prediction in predictions:
        annotation = prediction.annotation
        if annotation.start is None or annotation.end is None:
            continue
        if annotation.entity_type.strip().lower() != normalized_type:
            continue
        out.append(prediction)
    return out


def _strict_matches(
    predictions: list[Annotation],
    gold_annotations: list[GoldAnnotation],
) -> set[tuple[int, int]]:
    matched_gold: set[int] = set()
    matches: set[tuple[int, int]] = set()
    for prediction_index, prediction in enumerate(predictions):
        for gold_index, gold in enumerate(gold_annotations):
            if gold_index in matched_gold:
                continue
            if prediction.start == gold.start and prediction.end == gold.end:
                matches.add((prediction_index, gold_index))
                matched_gold.add(gold_index)
                break
    return matches


def _lenient_matches(
    predictions: list[Annotation],
    gold_annotations: list[GoldAnnotation],
    *,
    excluded_pairs: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    matched_predictions = {prediction_index for prediction_index, _ in excluded_pairs}
    matched_gold = {gold_index for _, gold_index in excluded_pairs}
    matches: set[tuple[int, int]] = set()
    for prediction_index, prediction in enumerate(predictions):
        if prediction_index in matched_predictions:
            continue
        best_gold_index: int | None = None
        best_overlap = 0
        for gold_index, gold in enumerate(gold_annotations):
            if gold_index in matched_gold:
                continue
            overlap = _overlap_length(prediction, gold)
            if overlap > best_overlap:
                best_gold_index = gold_index
                best_overlap = overlap
        if best_gold_index is not None and best_overlap > 0:
            matches.add((prediction_index, best_gold_index))
            matched_predictions.add(prediction_index)
            matched_gold.add(best_gold_index)
    return matches


def _nearest_gold(
    prediction: Annotation,
    gold_annotations: list[GoldAnnotation],
) -> GoldAnnotation | None:
    if not gold_annotations:
        return None
    return min(gold_annotations, key=lambda gold: _span_distance(prediction.start, prediction.end, gold.start, gold.end))


def _nearest_prediction(
    gold: GoldAnnotation,
    predictions: list[Annotation],
) -> Annotation | None:
    if not predictions:
        return None
    return min(predictions, key=lambda prediction: _span_distance(prediction.start, prediction.end, gold.start, gold.end))


def _overlap_length(prediction: Annotation, gold: GoldAnnotation) -> int:
    if prediction.start is None or prediction.end is None:
        return 0
    return max(0, min(prediction.end, gold.end) - max(prediction.start, gold.start))


def _span_distance(
    left_start: int | None,
    left_end: int | None,
    right_start: int,
    right_end: int,
) -> int:
    if left_start is None or left_end is None:
        return 10**12
    if left_end < right_start:
        return right_start - left_end
    if right_end < left_start:
        return left_start - right_end
    return 0


__all__ = ["ErrorAnalysis", "build_error_analysis"]

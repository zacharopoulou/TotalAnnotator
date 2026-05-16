from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from bio_annotation.benchmarking.ncbi import GoldAnnotation
from bio_annotation.schemas.entity import Annotation


@dataclass(slots=True)
class MatchCounts:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass(slots=True)
class EvaluationResult:
    annotator: str
    strict: MatchCounts
    lenient: MatchCounts
    prediction_count: int
    gold_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotator": self.annotator,
            "prediction_count": self.prediction_count,
            "gold_count": self.gold_count,
            "strict": self.strict.to_dict(),
            "lenient": self.lenient.to_dict(),
        }


@dataclass(slots=True)
class ScoredPrediction:
    document_id: str
    annotation: Annotation


def evaluate_annotator(
    *,
    annotator: str,
    predictions: Iterable[Annotation | ScoredPrediction],
    gold_annotations: Iterable[GoldAnnotation],
    entity_type: str = "disease",
) -> EvaluationResult:
    filtered_predictions = _filter_predictions(predictions, entity_type=entity_type)
    filtered_gold = [gold for gold in gold_annotations if gold.entity_type == entity_type]
    return EvaluationResult(
        annotator=annotator,
        strict=_match_counts_by_document(filtered_predictions, filtered_gold, mode="strict"),
        lenient=_match_counts_by_document(filtered_predictions, filtered_gold, mode="lenient"),
        prediction_count=len(filtered_predictions),
        gold_count=len(filtered_gold),
    )


def _filter_predictions(
    predictions: Iterable[Annotation | ScoredPrediction],
    *,
    entity_type: str,
) -> list[ScoredPrediction]:
    normalized_type = entity_type.strip().lower()
    out: list[ScoredPrediction] = []
    for item in predictions:
        prediction = _as_scored_prediction(item)
        annotation = prediction.annotation
        if annotation.start is None or annotation.end is None:
            continue
        if annotation.entity_type.strip().lower() != normalized_type:
            continue
        out.append(prediction)
    return out


def _as_scored_prediction(item: Annotation | ScoredPrediction) -> ScoredPrediction:
    if isinstance(item, ScoredPrediction):
        return item
    document_id = _prediction_document_id(item)
    return ScoredPrediction(document_id=document_id, annotation=item)


def _prediction_document_id(annotation: Annotation) -> str:
    metadata = annotation.metadata if isinstance(annotation.metadata, dict) else {}
    for key in ("document_id", "doc_id", "source_document_id"):
        value = metadata.get(key)
        if value:
            return str(value)
    return ""


def _match_counts_by_document(
    predictions: list[ScoredPrediction],
    gold_annotations: list[GoldAnnotation],
    *,
    mode: str,
) -> MatchCounts:
    predictions_by_document: dict[str, list[Annotation]] = defaultdict(list)
    gold_by_document: dict[str, list[GoldAnnotation]] = defaultdict(list)

    for prediction in predictions:
        predictions_by_document[prediction.document_id].append(prediction.annotation)
    for gold in gold_annotations:
        gold_by_document[gold.document_id].append(gold)

    document_ids = set(predictions_by_document) | set(gold_by_document)
    total = MatchCounts()
    for document_id in document_ids:
        counts = _match_counts(
            predictions_by_document.get(document_id, []),
            gold_by_document.get(document_id, []),
            mode=mode,
        )
        total.true_positive += counts.true_positive
        total.false_positive += counts.false_positive
        total.false_negative += counts.false_negative
    return total


def _match_counts(
    predictions: list[Annotation],
    gold_annotations: list[GoldAnnotation],
    *,
    mode: str,
) -> MatchCounts:
    matched_gold: set[int] = set()
    true_positive = 0

    for prediction in predictions:
        match_index = _first_unmatched_gold_index(
            prediction,
            gold_annotations,
            matched_gold=matched_gold,
            mode=mode,
        )
        if match_index is None:
            continue
        matched_gold.add(match_index)
        true_positive += 1

    false_positive = len(predictions) - true_positive
    false_negative = len(gold_annotations) - true_positive
    return MatchCounts(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
    )


def _first_unmatched_gold_index(
    prediction: Annotation,
    gold_annotations: list[GoldAnnotation],
    *,
    matched_gold: set[int],
    mode: str,
) -> int | None:
    for index, gold in enumerate(gold_annotations):
        if index in matched_gold:
            continue
        if mode == "strict" and _strict_match(prediction, gold):
            return index
        if mode == "lenient" and _overlap_match(prediction, gold):
            return index
    return None


def _strict_match(prediction: Annotation, gold: GoldAnnotation) -> bool:
    return prediction.start == gold.start and prediction.end == gold.end


def _overlap_match(prediction: Annotation, gold: GoldAnnotation) -> bool:
    if prediction.start is None or prediction.end is None:
        return False
    return max(prediction.start, gold.start) < min(prediction.end, gold.end)


__all__ = [
    "EvaluationResult",
    "MatchCounts",
    "ScoredPrediction",
    "evaluate_annotator",
]

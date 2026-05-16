from __future__ import annotations

import ast
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
class NormalizationCounts:
    span_matches: int = 0
    correct: int = 0
    incorrect: int = 0
    missing_prediction_id: int = 0
    missing_gold_id: int = 0

    @property
    def comparable_gold_spans(self) -> int:
        return self.correct + self.incorrect + self.missing_prediction_id

    @property
    def prediction_id_spans(self) -> int:
        return self.correct + self.incorrect + self.missing_gold_id

    @property
    def accuracy_on_matched_spans(self) -> float:
        return self.correct / self.span_matches if self.span_matches else 0.0

    @property
    def accuracy_on_comparable_gold_spans(self) -> float:
        denominator = self.comparable_gold_spans
        return self.correct / denominator if denominator else 0.0

    @property
    def prediction_id_coverage_on_matched_spans(self) -> float:
        return self.prediction_id_spans / self.span_matches if self.span_matches else 0.0

    @property
    def gold_id_coverage_on_matched_spans(self) -> float:
        denominator = self.span_matches
        return self.comparable_gold_spans / denominator if denominator else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_matches": self.span_matches,
            "correct": self.correct,
            "incorrect": self.incorrect,
            "missing_prediction_id": self.missing_prediction_id,
            "missing_gold_id": self.missing_gold_id,
            "comparable_gold_spans": self.comparable_gold_spans,
            "prediction_id_spans": self.prediction_id_spans,
            "accuracy_on_matched_spans": self.accuracy_on_matched_spans,
            "accuracy_on_comparable_gold_spans": self.accuracy_on_comparable_gold_spans,
            "prediction_id_coverage_on_matched_spans": self.prediction_id_coverage_on_matched_spans,
            "gold_id_coverage_on_matched_spans": self.gold_id_coverage_on_matched_spans,
        }


@dataclass(slots=True)
class EvaluationResult:
    annotator: str
    strict: MatchCounts
    lenient: MatchCounts
    strict_normalization: NormalizationCounts
    lenient_normalization: NormalizationCounts
    prediction_count: int
    gold_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotator": self.annotator,
            "prediction_count": self.prediction_count,
            "gold_count": self.gold_count,
            "strict": self.strict.to_dict(),
            "lenient": self.lenient.to_dict(),
            "strict_normalization": self.strict_normalization.to_dict(),
            "lenient_normalization": self.lenient_normalization.to_dict(),
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
        strict_normalization=_normalization_counts_by_document(
            filtered_predictions,
            filtered_gold,
            mode="strict",
        ),
        lenient_normalization=_normalization_counts_by_document(
            filtered_predictions,
            filtered_gold,
            mode="lenient",
        ),
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
    metadata = getattr(annotation, "metadata", None)
    if isinstance(metadata, dict):
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
    total = MatchCounts()
    for predictions_for_document, gold_for_document in _iter_document_groups(
        predictions,
        gold_annotations,
    ):
        counts = _match_counts(predictions_for_document, gold_for_document, mode=mode)
        total.true_positive += counts.true_positive
        total.false_positive += counts.false_positive
        total.false_negative += counts.false_negative
    return total


def _normalization_counts_by_document(
    predictions: list[ScoredPrediction],
    gold_annotations: list[GoldAnnotation],
    *,
    mode: str,
) -> NormalizationCounts:
    total = NormalizationCounts()
    for predictions_for_document, gold_for_document in _iter_document_groups(
        predictions,
        gold_annotations,
    ):
        counts = _normalization_counts(predictions_for_document, gold_for_document, mode=mode)
        total.span_matches += counts.span_matches
        total.correct += counts.correct
        total.incorrect += counts.incorrect
        total.missing_prediction_id += counts.missing_prediction_id
        total.missing_gold_id += counts.missing_gold_id
    return total


def _iter_document_groups(
    predictions: list[ScoredPrediction],
    gold_annotations: list[GoldAnnotation],
) -> Iterable[tuple[list[Annotation], list[GoldAnnotation]]]:
    predictions_by_document: dict[str, list[Annotation]] = defaultdict(list)
    gold_by_document: dict[str, list[GoldAnnotation]] = defaultdict(list)

    for prediction in predictions:
        predictions_by_document[prediction.document_id].append(prediction.annotation)
    for gold in gold_annotations:
        gold_by_document[gold.document_id].append(gold)

    for document_id in set(predictions_by_document) | set(gold_by_document):
        yield predictions_by_document.get(document_id, []), gold_by_document.get(document_id, [])


def _match_counts(
    predictions: list[Annotation],
    gold_annotations: list[GoldAnnotation],
    *,
    mode: str,
) -> MatchCounts:
    pairs = _match_pairs(predictions, gold_annotations, mode=mode)
    true_positive = len(pairs)
    return MatchCounts(
        true_positive=true_positive,
        false_positive=len(predictions) - true_positive,
        false_negative=len(gold_annotations) - true_positive,
    )


def _normalization_counts(
    predictions: list[Annotation],
    gold_annotations: list[GoldAnnotation],
    *,
    mode: str,
) -> NormalizationCounts:
    counts = NormalizationCounts()
    for prediction_index, gold_index in _match_pairs(predictions, gold_annotations, mode=mode):
        counts.span_matches += 1
        prediction_ids = _prediction_id_aliases(predictions[prediction_index].canonical_id)
        gold_ids = _gold_id_aliases(gold_annotations[gold_index].normalized_ids)
        if not gold_ids:
            counts.missing_gold_id += 1
        elif not prediction_ids:
            counts.missing_prediction_id += 1
        elif prediction_ids & gold_ids:
            counts.correct += 1
        else:
            counts.incorrect += 1
    return counts


def _match_pairs(
    predictions: list[Annotation],
    gold_annotations: list[GoldAnnotation],
    *,
    mode: str,
) -> list[tuple[int, int]]:
    matched_gold: set[int] = set()
    pairs: list[tuple[int, int]] = []

    for prediction_index, prediction in enumerate(predictions):
        match_index = _first_unmatched_gold_index(
            prediction,
            gold_annotations,
            matched_gold=matched_gold,
            mode=mode,
        )
        if match_index is None:
            continue
        matched_gold.add(match_index)
        pairs.append((prediction_index, match_index))
    return pairs


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


def _prediction_id_aliases(value: str | None) -> set[str]:
    aliases: set[str] = set()
    for item in _iter_identifier_values(value):
        aliases.update(_identifier_aliases(item))
    return aliases


def _gold_id_aliases(values: tuple[str, ...]) -> set[str]:
    aliases: set[str] = set()
    for value in values:
        for item in _iter_identifier_values(value):
            aliases.update(_identifier_aliases(item))
    return aliases


def _iter_identifier_values(value: Any) -> Iterable[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]

    raw = str(value).strip()
    if not raw:
        return []

    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, (list, tuple, set)):
            return [str(item) for item in parsed if item]

    cleaned = raw.strip("[]")
    parts = cleaned.replace("|", ";").replace(",", ";").split(";")
    return [part.strip().strip("'\"") for part in parts if part.strip().strip("'\"")]


def _identifier_aliases(value: str | None) -> set[str]:
    raw = str(value or "").strip().strip("'\"")
    if not raw or raw == "-":
        return set()
    normalized = raw.upper().replace(" ", "")
    aliases = {normalized}
    if ":" in normalized:
        _, suffix = normalized.split(":", 1)
        if suffix:
            aliases.add(suffix)
    return aliases


__all__ = [
    "EvaluationResult",
    "MatchCounts",
    "NormalizationCounts",
    "ScoredPrediction",
    "evaluate_annotator",
]

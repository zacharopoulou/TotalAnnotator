# Standalone Benchmark Review

This package contains the benchmark-review implementation for TotalAnnotator. It is intentionally separate from the main pipeline runner.

The goal is to evaluate annotator behavior against curated benchmark data while keeping the production-style annotation pipeline stable. Benchmark review code reuses the public `Document` and `Annotation` contracts, and it reuses the existing annotator runner, but benchmark loading, gold annotation handling, annotator runtime defaults, preflight checks, scoring, error analysis, plotting, and reporting live here.

## Current benchmark

The first supported benchmark is **NCBI Disease**.

Committed data:

```text
benchmarks/data/ncbi/test.jsonl
```

Only the official test split is committed. Train and validation splits can be regenerated locally with:

```bash
uv sync --extra benchmarks
uv run python benchmarks/scripts/ncbi.py
```

The review workflow currently evaluates disease annotations from:

```text
bern2
pubtator3
flair
```

The default scored entity type is:

```text
disease
```

NCBI Disease gold labels are normalized into this single scored type. The loader currently treats these benchmark labels as disease gold annotations:

```text
Disease
SpecificDisease
DiseaseClass
Modifier
CompositeDiseaseMention
CompositeMention
```

The original benchmark label is preserved in each gold row as `raw_entity_type`.

## Benchmark-owned annotator configuration

The benchmark review workflow does **not** read `configs/pipeline.toml`.

Its annotator runtime defaults are owned by:

```text
src/bio_annotation/benchmarking/config.py
```

Current defaults:

```python
DEFAULT_BENCHMARK_ANNOTATORS = ["bern2", "pubtator3", "flair"]

DEFAULT_BENCHMARK_ANNOTATOR_OPTIONS = {
    "bern2": {
        "runtime": "remote_api",
        "base_url": "http://127.0.0.1:8888",
        "endpoint": "http://bern2.korea.ac.kr/plain",
    },
    "flair": {
        "runtime": "local_model",
        "model": "hunflair2",
    },
    "pubtator3": {
        "runtime": "remote_api",
        "endpoint": "https://www.ncbi.nlm.nih.gov/research/pubtator3-api",
        "format": "biocjson",
        "timeout": 60,
        "mode": "publication_only",
        "bioconcept": "All",
    },
}
```

These defaults are copied into each review run and passed to the existing annotator runner. They are also written into `summary.json` under `annotator_options`, so every benchmark result records the runtime settings used to produce it.

PubTator3 is intentionally configured as `publication_only` for this benchmark. NCBI Disease rows carry PubMed IDs, so PubTator3 should use the publication export API by PMID rather than raw-text annotation jobs. The PubTator3 adapter routes publication calls by available PMID/PMCID, not by `Document.source`, so benchmark documents such as `source="benchmark:ncbi_disease"` still use PMID export.

This separation is intentional: benchmark-review settings can evolve independently from the main corpus pipeline config.

## Preflight checks

Before processing benchmark documents, the runner performs preflight checks for the selected annotators.

Current checks:

- BERN2: confirms that a benchmark endpoint is configured.
- PubTator3: confirms benchmark endpoint and mode settings.
- Flair: loads the configured local model once before document iteration.

This prevents repeated per-document failures such as:

```text
flair unavailable: [Errno 2] No such file or directory: '/homes/.../.flair/models/hunflair2'
```

If Flair is selected and the configured model cannot be loaded, the command stops before scoring and reports one clear message:

```text
Benchmark preflight failed.
Benchmark config is being used. Flair is being called with model 'hunflair2', but the model is not available through Flair's classifier loader in the local environment. Original error: ...
```

When Flair preflight succeeds, the loaded tagger is reused across all benchmark documents.

## Running the benchmark review

From the repository root:

```bash
uv run totalannotator evaluate-ncbi-review
```

This loads the default NCBI Disease test split and evaluates the default annotator set.

A more explicit run:

```bash
uv run totalannotator evaluate-ncbi-review \
  --benchmark-path benchmarks/data/ncbi/test.jsonl \
  --split test \
  --annotators bern2,pubtator3,flair \
  --entity-type disease \
  --output-dir outputs/benchmark-review/ncbi_disease \
  --progress-interval 25
```

Arguments:

- `--benchmark-path`: optional path to an NCBI Disease JSONL split. If omitted, the loader uses `benchmarks/data/ncbi/<split>.jsonl`.
- `--split`: split name used when `--benchmark-path` is omitted. Default: `test`.
- `--annotators`: comma-separated annotator names. Default: `bern2,pubtator3,flair`.
- `--entity-type`: entity type to score. Default: `disease`.
- `--output-dir`: directory for review outputs. Default: `outputs/benchmark-review/ncbi_disease`.
- `--progress-interval`: print progress every N documents. Default: `25`.

## Output files

The review command writes a compact set of files for inspection:

```text
summary.json
preflight.tsv
metrics_by_annotator.tsv
false_positives.tsv
false_negatives.tsv
boundary_errors.tsv
gold.jsonl
predictions.jsonl
annotator_statuses.tsv
loader_warnings.tsv
plots/
```

### `summary.json`

Full machine-readable run payload. It includes:

- benchmark name
- split
- entity type
- document count
- gold annotation count
- annotator list
- annotator runtime options
- preflight results
- strict and lenient span metrics
- strict and lenient normalization metrics
- error analysis grouped by annotator
- per-document annotator statuses
- loader warnings
- gold annotations
- predictions grouped by annotator

### `preflight.tsv`

One row per selected annotator that passed preflight. It records:

```text
name
status
message
```

If preflight fails, the run exits before writing benchmark outputs so the failure cannot be confused with a real zero-score evaluation.

### `metrics_by_annotator.tsv`

One row per annotator. Columns include span metrics:

```text
annotator
prediction_count
gold_count
strict_tp
strict_fp
strict_fn
strict_precision
strict_recall
strict_f1
lenient_tp
lenient_fp
lenient_fn
lenient_precision
lenient_recall
lenient_f1
```

The same table also includes normalization metrics for strict and lenient span matches:

```text
strict_norm_span_matches
strict_norm_correct
strict_norm_incorrect
strict_norm_missing_prediction_id
strict_norm_missing_gold_id
strict_norm_accuracy_on_matched_spans
strict_norm_accuracy_on_comparable_gold_spans
strict_norm_prediction_id_coverage_on_matched_spans
strict_norm_gold_id_coverage_on_matched_spans
lenient_norm_span_matches
lenient_norm_correct
lenient_norm_incorrect
lenient_norm_missing_prediction_id
lenient_norm_missing_gold_id
lenient_norm_accuracy_on_matched_spans
lenient_norm_accuracy_on_comparable_gold_spans
lenient_norm_prediction_id_coverage_on_matched_spans
lenient_norm_gold_id_coverage_on_matched_spans
```

Normalization scoring compares predicted `canonical_id` values against gold normalized IDs only after a span match has been made. Identifier matching is prefix-tolerant, so IDs such as `D005909` and `MESH:D005909` are considered equivalent.

### `false_positives.tsv`

Predicted disease spans that do not exactly match or overlap a gold disease span in the same document. Each row includes the prediction span plus nearest gold span context.

### `false_negatives.tsv`

Gold disease spans that were not exactly matched or overlapped by a prediction in the same document. Each row includes the gold span plus nearest prediction context.

### `boundary_errors.tsv`

Predictions that overlap a gold disease span but have different strict boundaries. These are lenient true positives but strict errors. Each row includes both spans, raw NCBI gold type, normalized IDs, and overlap length.

### `plots/`

The benchmark run writes four PNG plots under:

```text
outputs/benchmark-review/ncbi_disease/plots/
```

Generated plots:

```text
metrics_overview.png
coverage_groups.png
normalization_accuracy.png
consensus_gold_coverage.png
```

- `metrics_overview.png`: grouped bar chart of strict and lenient span F1 per annotator.
- `coverage_groups.png`: gold annotation coverage counts, including missed-by-all, found-by-one, found-by-two, found-by-three, strictly-found-by-all, and normalization-correct-by-all.
- `normalization_accuracy.png`: normalization accuracy and ID coverage per annotator.
- `consensus_gold_coverage.png`: heatmap of each gold disease annotation against each annotator, where values distinguish missed, lenient match, strict match, and normalization-correct strict match.

### `gold.jsonl`

One gold disease annotation per line, in the canonical annotator text coordinate space.

### `predictions.jsonl`

One predicted annotation per line. Rows include the annotation fields plus `document_id` and `annotator`.

### `annotator_statuses.tsv`

Per-document status records from the annotator runner. This helps distinguish true absence of annotations from service failures, timeouts, or unavailable annotators.

### `loader_warnings.tsv`

Warnings emitted while loading benchmark rows. The most important warnings are gold span text mismatches, which indicate that text reconstruction or offset shifting should be inspected before trusting scores.

## Text and offset contract

Benchmark evaluation is only valid if gold offsets and annotator offsets refer to the same text.

The NCBI loader converts each benchmark row into the same canonical text style used by `Document.text`:

```text
title + "\n\n" + abstract
```

Gold offsets are shifted into this canonical coordinate space when the source row has separate title and abstract passages.

The source benchmark frequently stores passage offsets as `[start, end]` pairs, for example `[[149, 1528]]`. The loader uses the first value as the passage start and computes the shift from source benchmark coordinates into canonical `Document.text` coordinates.

The loader validates each gold span by checking that:

```text
canonical_text[start:end] == gold_span_text
```

If that check fails, the row is still loaded but a warning is written. Review `loader_warnings.tsv` before interpreting benchmark results.

## Metrics

The review evaluator reports span-level and normalization-level metrics.

All matching is grouped by benchmark document before scoring. A prediction from one document cannot match a gold annotation from another document, even if the offsets and span text are identical.

### Strict span matching

A prediction is correct only when all of these match:

```text
same document
same scored entity type
same start offset
same end offset
```

Strict matching is deterministic and conservative.

### Lenient span matching

A prediction is correct when the predicted span overlaps an unmatched gold span from the same document:

```text
max(pred_start, gold_start) < min(pred_end, gold_end)
```

Lenient matching helps identify boundary disagreements. For example, a prediction of `cancer` inside a gold span `breast cancer` is not strict-correct, but it is lenient-correct.

### Normalization scoring

Normalization is scored after span matching. For each strict or lenient span match, the evaluator compares the predicted disease identifier against the gold normalized disease identifiers.

The normalization counts are:

- `span_matches`: number of matched spans considered for normalization.
- `correct`: matched spans where predicted and gold IDs overlap.
- `incorrect`: matched spans where both sides have IDs but they do not overlap.
- `missing_prediction_id`: gold has an ID but the prediction does not.
- `missing_gold_id`: prediction has an ID but gold does not.

The main normalization accuracy columns are:

- `accuracy_on_matched_spans`: correct ID matches divided by all matched spans.
- `accuracy_on_comparable_gold_spans`: correct ID matches divided by matched spans where the gold has a normalized ID.
- `prediction_id_coverage_on_matched_spans`: matched spans where the prediction provides an ID.
- `gold_id_coverage_on_matched_spans`: matched spans where the gold provides an ID.

## Design boundaries

This implementation is deliberately a secondary review layer.

It does **not** replace or reorganize:

```text
pipeline_runner.py
pipeline_config.py
preprocessing/document_loader.py
```

The benchmark package only calls the existing public annotator runner:

```python
run_selected_annotators_with_status(...)
```

This keeps benchmark work useful for review without making normal `run-config` behavior depend on benchmark-specific assumptions.

## Current limitations

This is the first usable evaluation pass, not the final benchmark suite.

Current limitations:

- only NCBI Disease is supported
- live annotator reliability depends on the configured services and remote APIs

## Recommended validation

After changing this package, run:

```bash
uv run pytest tests/test_benchmarking.py tests/test_annotators.py tests/test_benchmark_plots.py
```

A successful expected result includes the standalone benchmark tests, PubTator3 routing tests, and plot generation tests.

For a real review run, inspect:

```text
outputs/benchmark-review/ncbi_disease/preflight.tsv
outputs/benchmark-review/ncbi_disease/metrics_by_annotator.tsv
outputs/benchmark-review/ncbi_disease/false_positives.tsv
outputs/benchmark-review/ncbi_disease/false_negatives.tsv
outputs/benchmark-review/ncbi_disease/boundary_errors.tsv
outputs/benchmark-review/ncbi_disease/plots/metrics_overview.png
outputs/benchmark-review/ncbi_disease/plots/coverage_groups.png
outputs/benchmark-review/ncbi_disease/plots/normalization_accuracy.png
outputs/benchmark-review/ncbi_disease/plots/consensus_gold_coverage.png
outputs/benchmark-review/ncbi_disease/loader_warnings.tsv
outputs/benchmark-review/ncbi_disease/annotator_statuses.tsv
outputs/benchmark-review/ncbi_disease/summary.json
```

The preflight, warning, status, error-analysis, and plot files should be reviewed before drawing conclusions from F1 scores. `summary.json` should be checked to confirm the benchmark-owned `annotator_options` used for the run.

## Next implementation steps

Suggested next steps:

1. Add BERN2 retry/backoff for temporary remote API failures.
2. Add a benchmark config file once more benchmarks exist.
3. Add additional disease benchmarks to reduce overfitting to NCBI Disease.

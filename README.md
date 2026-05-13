# TotalAnnotator

TotalAnnotator is a config-first biomedical literature pipeline for building corpora, running annotators, and producing comparable annotation outputs.

The current product direction is:

`PMID/query/corpus input -> canonical documents -> selected annotators -> unified annotations`

The near-term workflow target is described in [docs/workflow-spec.md](docs/workflow-spec.md). The longer-term research roadmap remains in [Workflow_longterm.md](Workflow_longterm.md).

## What You Can Run Today

TotalAnnotator currently supports:

- corpus creation from inline PMIDs, PMID files, and local text inputs
- rich PubMed metadata ingestion for PMID-based inputs
- a first live annotator integration with `pubtator3`
- a unified JSON pipeline output with top-level corpus and annotation sections

## Available Annotators

- `pubtator3`
  First live annotator integration. Runs through the official NCBI PubTator API.
- `bern2`
  Runtime scaffold kept in config for future local deployment.
- `flair`
  Runtime scaffold kept in config for future local deployment.

## Quickstart

```bash
git clone <YOUR_REPOSITORY_URL>
cd TotalAnnotator
uv sync
```

The default install stays lightweight. Install optional extras only when you
need them:

```bash
uv sync --extra flair      # local Flair annotator support
uv sync --extra benchmarks # benchmark dataset tooling and analytics
uv sync --extra all        # all optional functionality
```

Project overview:

```bash
uv run totalannotator
```

Inspect the default config:

```bash
uv run totalannotator inspect-config
```

Preview the documents that will be loaded:

```bash
uv run totalannotator load-documents
```

Run the pipeline:

```bash
uv run totalannotator run-config
```

## First Live Run

The default [configs/pipeline.toml](configs/pipeline.toml) is set up for a first live `pubtator3` run on a PMID input.

It uses:

- `input.mode = "pmids"`
- an inline PMID list
- `annotators.enabled = ["pubtator3"]`
- a `pubtator3` runtime block under `[annotators.pubtator3]`

Run it with:

```bash
uv run totalannotator run-config
```

The output is written to:

```bash
outputs/pubtator3_pipeline_output.json
```

`search-pmids` bypasses NCBI ESearch's 10,000-result cap by recursively
bisecting the publication-date range until every window fits under the limit,
then concatenating the per-window results. The command writes the full PMID
list to `--output` and prints a short summary (query, count, output path, and
the first 10 PMIDs) to stdout.

Supported options:

- `--query` (required) — PubMed query string.
- `--output` (required) — path to write the PMID file (one PMID per line).
- `--max-results` — optional upper bound on the returned PMIDs (positive int).
  Applied as a final slice after the full search completes.
- `--date-from` / `--date-to` — bound the publication-date window. Accept
  `YYYY`, `YYYY/MM`, or `YYYY/MM/DD`; partial dates expand to the start or end
  of the period depending on which bound they are.
- `--sort-by` — PubMed sort order. Only `pub_date` gives a globally correct
  ordering across the full result set (the bisection processes windows
  latest-first). `relevance` and `author` are honored per-window only.
- `--filter` — extra PubMed filter clause (e.g. `"english[lang]"`). Repeatable.

If no annotators are enabled yet, `run-config` still works as an ingestion step
and returns the loaded documents with zero annotations.

The current pipeline supports these input modes:

- `pmids`
- `pmid_file`
- `text_table`
- `corpus`

The CLI also supports upstream PMID generation with:

```bash
uv run totalannotator search-pmids --query 'glioblastoma AND microRNA' --output data/inputs/query_pmids.txt
```

## Example Configs

Inline PMID input with `pubtator3`:

```bash
uv run totalannotator run-config --config configs/examples/pmid-single.toml
```

This runs the PMIDs defined directly in the config through PubMed ingestion and `pubtator3`, and writes:

```bash
outputs/examples/pubtator3-pmid.json
```

PMID file batch with `pubtator3`:

```bash
uv run totalannotator run-config --config configs/examples/pmid-file.toml
```

This runs a batch of PMIDs from `data/inputs/example_pmids.txt` and writes:

```bash
outputs/examples/pubtator3-pmid-file.json
```

Local text table with `pubtator3`:

```bash
uv run totalannotator run-config --config configs/examples/corpus-file.toml
```

This runs the bundled local text input through `pubtator3` raw-text annotation and writes:

```bash
outputs/examples/corpus-file.json
```

Because PubTator3 raw-text jobs are asynchronous, this example can take longer
than the PMID-based runs.

## Configuration Model

The pipeline config is organized into five main sections:

- `[input]`
- `[enrichment]`
- `[annotators]`
- `[filters]`
- `[output]`

Annotator-specific runtime metadata lives under nested tables such as:

```toml
[annotators.pubtator3]
runtime = "remote_api"
endpoint = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"
format = "biocjson"
timeout = 60
text_mode = "raw_text"
raw_text_bioconcept = "All"
raw_text_max_attempts = 20
raw_text_poll_interval = 2.0
```

This metadata is parsed by the pipeline and is also visible through:

```bash
uv run totalannotator inspect-config
```

For PubMed-backed documents, `pubtator3` uses the publication export API. For
local text inputs, it can use plain-text mode through:

```toml
mode = "text_only"
bioconcept = "All"
poll_interval_seconds = 2.0
poll_backoff = 1.5
max_poll_interval_seconds = 15.0
max_poll_attempts = 30
```

## Output

The current pipeline output is corpus-first.

Top-level sections include:

- `stage`
- `input`
- `pipeline`
- `corpus_summary`
- `documents`
- `annotation_summary`
- `document_annotations`
- `annotations`

When no annotators are enabled, the pipeline still succeeds and returns a clean canonical corpus.

## Development

Run the test suite:

```bash
uv run pytest
```

The shared early-stage contracts are:

- `Document`: the canonical input each annotator receives
- `Annotation`: the unified output each annotator returns

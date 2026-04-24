# TotalAnnotator

TotalAnnotator is a biomedical and clinical literature annotation project focused on turning article text into structured entity and relation outputs.

The near-term product workflow target is documented in [docs/workflow-spec.md](docs/workflow-spec.md).

The long-term pipeline vision is documented in [Workflow_longterm.md](Workflow_longterm.md) and follows this general path:

`document -> entity proposals -> candidate merging -> normalization -> adjudication -> validation -> final JSON`

## Getting Started

This repository uses `uv` for environment and dependency management.

```bash
git clone <YOUR_REPOSITORY_URL>
cd TotalAnnotator
uv sync
```

Run the built-in project command:

```bash
uv run totalannotator
```

Run the local mocked demo:

```bash
uv run totalannotator demo
```

Inspect the example pipeline config:

```bash
uv run totalannotator inspect-config
```

Preview documents loaded from the pipeline config:

```bash
uv run totalannotator load-documents
```

Run the selected annotators from the pipeline config:

```bash
uv run totalannotator run-config
```

Search PubMed and write a PMID file:

```bash
uv run totalannotator search-pmids --query 'glioblastoma AND microRNA' --output data/inputs/query_pmids.txt
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

For PMID-based ingestion, PubMed link and external metadata enrichment is
configurable through `[enrichment]`.

Run the test suite:

```bash
uv run pytest
```

## Current Focus

The repository is in the first implementation stage:

- shared `Document` and `Annotation` schemas
- annotator adapters for BERN2, Flair, and PubTator
- a unified output format so different annotators can be compared easily

This first milestone is centered on:

`PMID/document input -> annotator outputs -> unified annotations`

The intended near-term execution flow is:

`config -> validation -> document loading -> selected annotators -> harmonized per-annotator annotations -> overlap-based agreement summaries`

## What Exists Right Now

- `src/bio_annotation/schemas/`
  Shared `Document` and `Annotation` objects used across the pipeline.
- `src/bio_annotation/io/`
  PubMed record readers for PMID-based ingestion.
- `src/bio_annotation/preprocessing/`
  Config-driven document loading from PMIDs, PMID files, and text tables.
- `src/bio_annotation/pipeline_runner.py`
  Minimal config-driven runner for loading documents and executing selected annotators.
- `src/bio_annotation/entity_proposal/`
  Annotator adapters and a `run_all_annotators()` entry point.
- `src/bio_annotation/cli.py`
  A runnable CLI with demo, config inspection, and document-loading preview commands.
- `tests/`
  Offline tests for adapter normalization and unified outputs.

## Environment Notes

- `pyproject.toml` is the source of truth for project dependencies
- `.python-version` pins the local development interpreter to Python 3.12
- `uv sync` will create and manage the local `.venv/`
- heavy annotator-specific dependencies can be added later once the live integrations are chosen
- current demo commands are intentionally offline and use mocked annotator payloads

## Near-Term Goals

- connect live annotator backends where practical
- compare annotator outputs before building merging and normalization
- define a stable workflow and config contract for users and collaborators

## Input Modes

The current config loader supports these input modes:

- `pmids`
- `pmid_file`
- `text_table`
- `corpus`

## Runnable Examples

Single PMID:

```bash
uv run totalannotator run-config --config configs/examples/pmid-single.toml
```

PMID file:

```bash
uv run totalannotator run-config --config configs/examples/pmid-file.toml
```

Plain corpus file:

```bash
uv run totalannotator run-config --config configs/examples/corpus-file.toml
```

## Current Output Shape

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

In ingestion-only mode, `documents` is the main deliverable and the annotation
sections stay empty.

## Example Config Shapes

Example single PMID config:

```toml
[input]
mode = "pmids"
pmids = ["38123456"]

[enrichment]
sources = ["elinks", "crossref", "europe_pmc", "semantic_scholar", "unpaywall", "biorxiv"]

[annotators]
enabled = []
```

Example PMID file config:

```toml
[input]
mode = "pmid_file"
pmid_file = "data/inputs/example_pmids.txt"

[annotators]
enabled = []
```

Example plain corpus config:

```toml
[input]
mode = "corpus"
corpus_path = "data/corpora/example_documents.json"

[annotators]
enabled = []
```

## Development Note

The main shared contracts for early work are:

- `Document`: what each annotator receives
- `Annotation`: what each annotator returns

Keeping these stable will make the next stages much easier to build in parallel.

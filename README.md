# TotalAnnotator

TotalAnnotator is a config-first biomedical literature pipeline for building corpora, running annotators, and preparing benchmark-style evaluation.

The near-term product workflow target is documented in [docs/workflow-spec.md](docs/workflow-spec.md).

The separate long-term research vision is kept in [Workflow_longterm.md](Workflow_longterm.md).

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

If no annotators are enabled yet, `run-config` still works as an ingestion step
and returns the loaded documents with zero annotations.

For PMID-based ingestion, external enrichment is opt-in through `[enrichment]`.

Run the test suite:

```bash
uv run pytest
```

## Current Direction

The repository is currently centered on three connected workflows:

- corpus creation from PubMed PMIDs, query-generated PMID lists, and local corpora
- annotator execution on canonical documents
- benchmark-oriented evaluation scaffolding for comparing annotators consistently

The current implemented milestone is:

`PMID/document input -> annotator outputs -> unified annotations`

The repo direction now is:

`query or corpus -> canonical documents -> selected annotators -> harmonized outputs -> evaluation`

## What Exists Right Now

- `src/bio_annotation/schemas/`
  Shared `Document` and `Annotation` objects used across the pipeline.
- `src/bio_annotation/io/`
  PubMed search and metadata readers for PMID-based ingestion.
- `src/bio_annotation/preprocessing/`
  Config-driven document loading from PMIDs, PMID files, and text tables.
- `src/bio_annotation/annotators/`
  Primary home for annotator adapters and shared annotator runner utilities.
- `src/bio_annotation/pipeline_runner.py`
  Minimal config-driven runner for loading documents and executing selected annotators.
- `src/bio_annotation/entity_proposal/`
  Compatibility layer for the older annotator package path.
- `src/bio_annotation/cli.py`
  A runnable CLI with query search, config inspection, and document-loading preview commands.
- `data/`
  Example corpora, input files, and benchmark scaffolding.
- `tests/`
  Offline tests for adapter normalization and unified outputs.

## Environment Notes

- `pyproject.toml` is the source of truth for project dependencies
- `.python-version` pins the local development interpreter to Python 3.12
- `uv sync` will create and manage the local `.venv/`
- heavy annotator-specific dependencies can be added later once the live integrations are chosen
- current demo commands are intentionally offline and use mocked annotator payloads

## Near-Term Goals

- keep corpus construction reliable and reproducible
- make annotator backends pluggable across PMIDs, local corpora, and benchmark datasets
- add evaluation workflows that make annotator comparison first-class

## Input Modes

The current config loader supports these input modes:

- `pmids`
- `pmid_file`
- `text_table`
- `corpus`

The CLI also supports upstream PMID search with `search-pmids`. Benchmark input
support is the next planned first-class mode.

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
sources = []

[annotators]
enabled = []
```

Example PMID file config:

```toml
[input]
mode = "pmid_file"
pmid_file = "data/inputs/example_pmids.txt"

[enrichment]
sources = []

[annotators]
enabled = []
```

Example plain corpus config:

```toml
[input]
mode = "corpus"
corpus_path = "data/corpora/example_documents.json"

[enrichment]
sources = []

[annotators]
enabled = []
```

## Development Note

The main shared contracts for early work are:

- `Document`: what each annotator receives
- `Annotation`: what each annotator returns

Keeping these stable will make the next stages much easier to build in parallel.

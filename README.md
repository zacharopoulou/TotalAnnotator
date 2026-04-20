# TotalAnnotator

TotalAnnotator is a config-first biomedical literature pipeline for building corpora, running annotators, and producing comparable annotation outputs.

The current product direction is:

`PMID/query/corpus input -> canonical documents -> selected annotators -> unified annotations`

The near-term workflow target is described in [docs/workflow-spec.md](docs/workflow-spec.md). The longer-term research roadmap remains in [Workflow_longterm.md](Workflow_longterm.md).

## What You Can Run Today

TotalAnnotator currently supports:

- corpus creation from PubMed PMIDs, PMID files, and local corpus files
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
- one example PMID
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

## Input Modes

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

Single PMID with `pubtator3`:

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
```

This metadata is parsed by the pipeline and is also visible through:

```bash
uv run totalannotator inspect-config
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

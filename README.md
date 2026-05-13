# TotalAnnotator

TotalAnnotator is a config-first biomedical literature pipeline for building document corpora, running biomedical annotators, and exporting comparable annotation results.

The pipeline flow is:

```text
PMID, PMID file, text table, or corpus input
-> canonical documents
-> selected annotators
-> unified JSON output
```

## What It Supports

- PubMed document loading from inline PMIDs and PMID files
- Local text-table input from CSV or TSV files
- Existing corpus JSON input
- PubMed metadata enrichment for PMID-based inputs
- PubTator3 annotation through the NCBI PubTator API
- Optional local Flair annotation
- Optional BERN2 annotation through a configured endpoint
- Unified JSON output with corpus, document, and annotation sections

## Install

Base install:

```bash
git clone <YOUR_REPOSITORY_URL>
cd TotalAnnotator
uv sync
```

Install local Flair support when you want to use the `flair` annotator:

```bash
uv sync --extra flair
```

Install every optional feature:

```bash
uv sync --extra all
```

If a config enables `flair` but Flair is not installed, TotalAnnotator stops before the run starts and prints the install command.

## Run

Inspect the configured pipeline:

```bash
uv run totalannotator inspect-config --config configs/pipeline.toml
```

Preview the documents that will be loaded:

```bash
uv run totalannotator load-documents --config configs/pipeline.toml
```

Run the default pipeline:

```bash
uv run totalannotator run-config --config configs/pipeline.toml
```

The default config runs PubMed ingestion and PubTator3 annotation for PMID `36403686`.

## Annotators

Enable annotators in `[annotators]`:

```toml
[annotators]
enabled = ["pubtator3"]
```

Available annotators:

- `pubtator3`: remote annotation through the NCBI PubTator API.
- `flair`: local Flair annotation. Requires `uv sync --extra flair`.
- `bern2`: remote BERN2 annotation through the configured endpoint.

Annotator settings live in annotator-specific tables:

```toml
[annotators.pubtator3]
runtime = "remote_api"
endpoint = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"
format = "biocjson"
timeout = 60
```

```toml
[annotators.flair]
runtime = "python_local"
model = "hunflair2"
```

```toml
[annotators.bern2]
runtime = "remote_api"
endpoint = "http://bern2.korea.ac.kr/plain"
```

## Inputs

Supported input modes:

- `pmids`: PMIDs listed directly in the config.
- `pmid_file`: one PMID per line in a local file.
- `text_table`: CSV or TSV table with document ID, title, and abstract columns.
- `corpus`: existing TotalAnnotator corpus JSON.

Example PMID input:

```toml
[input]
mode = "pmids"
pmids = ["36403686"]
```

Example text-table input:

```toml
[input]
mode = "text_table"
text_file = "data/inputs/plain_text.tsv"
format = "tsv"
document_id_column = "document_id"
title_column = "title"
abstract_column = "abstract"
```

## Outputs

The configured output path controls where the JSON file is written:

```toml
[output]
path = "outputs/pubtator3_pipeline_output.json"
```

The JSON output includes:

- `stage`
- `input`
- `pipeline`
- `corpus_summary`
- `documents`
- `annotation_summary`
- `document_annotations`
- `annotations`

When no annotators are enabled, the pipeline still succeeds and writes the loaded corpus with zero annotations.

## Example Runs

Inline PMID input with PubTator3:

```bash
uv run totalannotator run-config --config configs/examples/pmid-single.toml
```

PMID file batch with PubTator3:

```bash
uv run totalannotator run-config --config configs/examples/pmid-file.toml
```

Local text table with PubTator3 plain-text mode:

```bash
uv run totalannotator run-config --config configs/examples/corpus-file.toml
```

PubTator3 plain-text runs are asynchronous and may take longer than PMID-based publication runs.

## PMID Search

Generate a PMID file from a PubMed query:

```bash
uv run totalannotator search-pmids \
  --query 'glioblastoma AND microRNA' \
  --output data/inputs/query_pmids.txt
```

`search-pmids` writes one PMID per line and prints a short summary with the query, result count, output path, and first 10 PMIDs.

Common options:

- `--max-results`: maximum number of PMIDs to keep.
- `--date-from` / `--date-to`: publication date bounds. Accepts `YYYY`, `YYYY/MM`, or `YYYY/MM/DD`.
- `--sort-by`: PubMed sort order.
- `--filter`: extra PubMed filter clause. Repeatable.

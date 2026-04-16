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
- `src/bio_annotation/entity_proposal/`
  Annotator adapters and a `run_all_annotators()` entry point.
- `src/bio_annotation/cli.py`
  A minimal runnable CLI for fresh clones.
- `tests/`
  Offline tests for adapter normalization and unified outputs.

## Environment Notes

- `pyproject.toml` is the source of truth for project dependencies
- `.python-version` pins the local development interpreter to Python 3.12
- `uv sync` will create and manage the local `.venv/`
- heavy annotator-specific dependencies can be added later once the live integrations are chosen
- current demo commands are intentionally offline and use mocked annotator payloads

## Near-Term Goals

- implement PMID ingestion and document loading
- connect live annotator backends where practical
- compare annotator outputs before building merging and normalization
- define a stable workflow and config contract for users and collaborators

## Development Note

The main shared contracts for early work are:

- `Document`: what each annotator receives
- `Annotation`: what each annotator returns

Keeping these stable will make the next stages much easier to build in parallel.

# Configuration Guide

This directory contains runnable pipeline configurations for TotalAnnotator.

## Files

- `pipeline.toml`
  Default config, set up for a first live `pubtator3` PMID run.
- `examples/`
  Small example configs for single PMID, PMID file, and corpus inputs.

## Main Sections

Each pipeline config is organized around:

- `[input]`
- `[enrichment]`
- `[annotators]`
- `[filters]`
- `[output]`

## Annotator Tables

Annotator runtime metadata is defined under nested annotator tables.

Example:

```toml
[annotators]
enabled = ["pubtator3"]

[annotators.pubtator3]
runtime = "remote_api"
endpoint = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"
format = "biocjson"
timeout = 60
text_mode = "raw_text"
raw_text_bioconcept = "All"
```

The pipeline reads these settings and uses them at runtime for the matching annotator.

## Current Examples

- `examples/pmid-single.toml`
  Single PMID example with `pubtator3`.
- `examples/pmid-file.toml`
  PMID batch example with `pubtator3`.
- `examples/corpus-file.toml`
  Local corpus example with `pubtator3` raw-text annotation.

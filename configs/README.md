# Configuration Guide

This directory contains runnable pipeline configurations for TotalAnnotator.

## Files

- `pipeline.toml`
  Default config, set up for a first live PubTator3 PMID run.
- `examples/`
  Small runnable configs for common input modes, plus one advanced multi-source fetch example.

## Main Sections

Each pipeline config is organized around:

- `[input]`
- `[enrichment]`
- `[annotators]`
- `[filters]`
- `[output]`

## Fetch Defaults

PMID-based inputs use PubTator3 as the default fetch source when `[input].source` is omitted.

Use comments inside `examples/pmid-single.toml` and `examples/pmid-file.toml` to switch to Entrez, Europe PMC, merged fetch, field filtering, or PubTator3 full text.

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
mode = "text_only"
bioconcept = "All"
poll_interval_seconds = 2.0
```

The pipeline reads these settings and uses them at runtime for the matching annotator.

## Current Examples

- `examples/pmid-single.toml`
  Inline PMID input using the default PubTator3 fetch source.
- `examples/pmid-file.toml`
  PMID batch input using the default PubTator3 fetch source. Commented options show Entrez, Europe PMC, merged fetch, field filtering, and PubTator3 full text.
- `examples/corpus-file.toml`
  Local text-table input with PubTator3 raw-text annotation.
- `examples/fetch-merge.toml`
  Advanced multi-source fetch example. Fetches from PubTator3, Entrez, and Europe PMC, then merges results into one canonical document per PMID.

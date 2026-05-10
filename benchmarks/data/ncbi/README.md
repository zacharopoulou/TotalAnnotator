# NCBI Disease — local benchmark data

Only `test.jsonl` is committed to this repo. It is the official held-out
evaluation split, used for testing annotators.

`train.jsonl` and `validation.jsonl` are intentionally **not** shipped here
(see `.gitignore`). Anyone who needs them can regenerate the full corpus
locally:

```
uv sync --extra benchmarks
uv run python benchmarks/scripts/ncbi.py
```

That downloads all three splits from Hugging Face (`bigbio/ncbi_disease`)
into this directory.

`NCBI_ANALYTICS_SUMMART.md` was generated from a full local download and
documents the entire corpus shape (counts, entity types, normalization
coverage), even though only the test split lives here.

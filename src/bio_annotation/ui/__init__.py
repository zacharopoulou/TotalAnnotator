"""Streamlit UI for the unified TotalAnnotator fetch pipeline.

Run the app with::

    uv run streamlit run src/bio_annotation/ui/streamlit_app.py

Pure-Python helpers used by the UI live in :mod:`bio_annotation.ui.inputs`
and are unit-tested. The Streamlit module itself is intentionally a thin
wiring layer so it can be iterated on without breaking tests.
"""

from bio_annotation.ui.inputs import (
    INPUT_MODE_LABELS,
    InputMode,
    build_fetch_input,
    parse_pmcid_list,
    parse_pmid_list,
)

__all__ = [
    "INPUT_MODE_LABELS",
    "InputMode",
    "build_fetch_input",
    "parse_pmcid_list",
    "parse_pmid_list",
]

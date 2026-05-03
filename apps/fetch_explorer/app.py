"""Streamlit workbench for fetch_pmids-style pipelines (visualize + save JSON).

Run from the TotalAnnotator repository root::

    pip install -e ".[ui]"
    streamlit run apps/fetch_explorer/app.py

Loads ``<repo>/.env`` the same way as ``scripts/fetch_pmids.py`` (does not override
existing environment variables).
"""

from __future__ import annotations

import html
import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any

import streamlit as st

# -----------------------------------------------------------------------------
# Repo layout: TotalAnnotator/apps/fetch_explorer/app.py
# -----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
FETCH_PMIDS_PATH = ROOT / "scripts" / "fetch_pmids.py"


def _ensure_src_on_path() -> None:
    if SRC.is_dir():
        sys.path.insert(0, str(SRC))


def _load_fetch_pmids_module():
    _ensure_src_on_path()
    spec = importlib.util.spec_from_file_location("fetch_pmids_workbench", FETCH_PMIDS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {FETCH_PMIDS_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SOURCE_COLORS: dict[str, str] = {
    "pubtator3": "#64b5f6",
    "medcat": "#81c784",
    "bern2": "#ffb74d",
    "flair": "#ba68c8",
}


def _annotation_intervals_for_highlight(results: dict[str, Any]) -> list[tuple[int, int, dict[str, Any]]]:
    intervals: list[tuple[int, int, dict[str, Any]]] = []
    for source_name, items in results.items():
        if source_name.endswith("_raw"):
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            start = item.get("start")
            end = item.get("end")
            if start is None or end is None:
                continue
            try:
                s_i, e_i = int(start), int(end)
            except (TypeError, ValueError):
                continue
            if e_i <= s_i:
                continue
            intervals.append((s_i, e_i, item))
    intervals.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    return intervals


def render_highlighted(text: str, results: dict[str, Any]) -> str:
    """HTML <mark> overlay by annotator source (non-overlapping greedy by sort order)."""
    intervals = _annotation_intervals_for_highlight(results)
    if not intervals:
        return f"<pre style='white-space:pre-wrap'>{html.escape(text)}</pre>"
    pieces: list[str] = []
    cursor = 0
    for start, end, item in intervals:
        if start < cursor:
            continue
        if start > cursor:
            pieces.append(html.escape(text[cursor:start]))
        src = str(item.get("source") or "unknown")
        color = SOURCE_COLORS.get(src, "#cfd8dc")
        et = html.escape(str(item.get("entity_type") or ""))
        cid = html.escape(str(item.get("canonical_id") or ""))
        title = f"{html.escape(src)} · {et}" + (f" · {cid}" if cid else "")
        marked = html.escape(text[start:end])
        pieces.append(
            f"<mark title='{title}' "
            f"style='background:{color};padding:0 2px;border-radius:3px'>"
            f"{marked}</mark>"
        )
        cursor = end
    if cursor < len(text):
        pieces.append(html.escape(text[cursor:]))
    return f"<pre style='white-space:pre-wrap;font-family:inherit;font-size:0.95rem'>{''.join(pieces)}</pre>"


def _annotator_body_text(doc: dict[str, Any]) -> str:
    """Match :meth:`~bio_annotation.schemas.document.Document.get_text` for highlight offsets."""

    from bio_annotation.schemas.document import Document

    meta = doc.get("metadata")
    return Document(
        document_id=str(doc.get("document_id") or ""),
        pmid=doc.get("pmid"),
        title=str(doc.get("title") or ""),
        abstract=str(doc.get("abstract") or ""),
        full_text=doc.get("full_text"),
        source=str(doc.get("source") or "unknown"),
        year=doc.get("year"),
        metadata=meta if isinstance(meta, dict) else {},
    ).get_text()


def render_source_legend() -> None:
    chips = " ".join(
        f"<span style='background:{c};padding:2px 8px;border-radius:3px;margin-right:6px;color:#111'>"
        f"{html.escape(name)}</span>"
        for name, c in SOURCE_COLORS.items()
    )
    st.markdown(chips, unsafe_allow_html=True)


def _split_ids(blob: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in blob.replace(",", "\n").splitlines():
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _run_pipeline(
    *,
    fp: Any,
    input_kind: str,
    raw_ids: list[str],
    query_text: str,
    raw_body: str,
    raw_doc_id: str,
    sources: list[str],
    explicit_fields: list[str] | None,
    include_annotations: bool,
    strict_sources: bool,
    annotators: list[str],
    pubtator_chunk_size: int,
    pubtator_chunk_overlap: int,
    include_medcat_raw: bool,
    include_flair_raw: bool,
    medcat_endpoint_override: str,
    flair_model: str,
) -> tuple[dict[str, Any] | None, str]:
    """Returns (payload dict, error message)."""

    from bio_annotation.fetch.input import FetchInput
    from bio_annotation.fetch.orchestrator import default_fetch_orchestrator

    if pubtator_chunk_overlap >= pubtator_chunk_size:
        return None, "pubtator chunk_overlap must be smaller than chunk_size."

    try:
        resolved_sources, fps, unresolved, auto_added = fp._resolve_sources_and_fields(
            explicit_sources=sources,
            explicit_fields=explicit_fields,
            include_annotations=include_annotations,
            annotators=annotators if annotators else None,
            strict_sources=strict_sources,
        )
    except ValueError as exc:
        return None, str(exc)

    warn_extra = ""
    if unresolved:
        warn_extra += "Unknown fields: " + ", ".join(unresolved) + "\n"
    if auto_added:
        warn_extra += "Auto-added sources: " + ", ".join(auto_added) + "\n"

    try:
        if input_kind == "raw_text":
            request = FetchInput.from_text(raw_body.strip(), text_id=raw_doc_id.strip() or "RAW:1")
            prefer: str | list[str] = ["raw_text"]
        elif input_kind == "pmid":
            if len(raw_ids) != 1:
                return None, "Single PMID mode needs exactly one ID."
            err = fp._validate_id_tokens_for_input_kind("pmid", raw_ids)
            if err:
                return None, err
            request = FetchInput.from_pmid(raw_ids[0], fields_per_source=fps)
            prefer = list(resolved_sources)
        elif input_kind == "pmid_list":
            if not raw_ids:
                return None, "Provide at least one PMID."
            err = fp._validate_id_tokens_for_input_kind("pmid_list", raw_ids)
            if err:
                return None, err
            request = FetchInput.from_pmid_list(raw_ids, fields_per_source=fps)
            prefer = list(resolved_sources)
        elif input_kind == "pmcid":
            if len(raw_ids) != 1:
                return None, "Single PMCID mode needs exactly one ID."
            err = fp._validate_id_tokens_for_input_kind("pmcid", raw_ids)
            if err:
                return None, err
            request = FetchInput.from_pmcid(raw_ids[0], fields_per_source=fps)
            prefer = list(resolved_sources)
        elif input_kind == "pmcid_list":
            if not raw_ids:
                return None, "Provide at least one PMCID."
            err = fp._validate_id_tokens_for_input_kind("pmcid_list", raw_ids)
            if err:
                return None, err
            request = FetchInput.from_pmcid_list(raw_ids, fields_per_source=fps)
            prefer = list(resolved_sources)
        elif input_kind == "query":
            q = query_text.strip()
            if not q:
                return None, "Query must not be empty."
            request = FetchInput.from_query(q, fields_per_source=fps)
            prefer = list(resolved_sources)
        else:
            return None, f"Unknown input kind {input_kind!r}."
    except ValueError as exc:
        return None, str(exc)

    orch = default_fetch_orchestrator()
    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            documents = orch.fetch(request, prefer=prefer)
            fp._warn_if_full_text_missing(
                documents,
                explicit_fields=explicit_fields,
                fields_per_source=fps,
            )
    except Exception as exc:
        return None, f"Fetch failed: {exc!s}"

    stderr_text = buf.getvalue()
    payload: dict[str, Any] = {
        "input_kind": input_kind,
        "sources": resolved_sources,
        "documents": [fp._document_to_jsonable(d) for d in documents],
        "_meta": {"warnings": warn_extra + stderr_text},
    }
    if input_kind == "query":
        payload["query"] = query_text.strip()

    annotator_settings: dict[str, dict[str, Any]] = {}
    ep = medcat_endpoint_override.strip()
    if ep:
        annotator_settings["medcat"] = {"endpoint": ep}
    if "flair" in annotators:
        fm = flair_model.strip() or "hunflair2"
        annotator_settings["flair"] = {"model": fm}

    if annotators:
        try:
            payload["annotators"] = fp._run_annotators(
                annotators=annotators,
                documents=documents,
                annotator_settings=annotator_settings or None,
                pubtator_chunk_size=pubtator_chunk_size,
                pubtator_chunk_overlap=pubtator_chunk_overlap,
                include_medcat_raw=include_medcat_raw,
                include_flair_raw=include_flair_raw,
            )
        except ValueError as exc:
            return None, str(exc)

    return payload, ""


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="TotalAnnotator Fetch Explorer", layout="wide")
st.title("TotalAnnotator · Fetch explorer")
st.caption(
    "Fetch literature or paste raw text, run annotators, inspect highlights and JSON, save to disk. "
    "Install `pip install -e \".[ui]\"` from the repo root for Streamlit + Flair (HunFlair2)."
)

try:
    fp = _load_fetch_pmids_module()
except Exception as exc:
    st.error(f"Failed to load fetch_pmids.py: {exc}")
    st.stop()

fp._load_repo_dotenv()

with st.sidebar:
    st.header("Fetch")
    catalog = fp._field_catalog()
    all_fields = sorted({f for fields in catalog.values() for f in fields})

    sources = st.multiselect(
        "Sources (order preserved)",
        options=["pubtator3", "entrez", "europe_pmc", "raw_text"],
        default=["pubtator3"],
        help="Literature modes: choose backends to merge. Raw-text tab forces raw_text only.",
    )

    field_pick = st.multiselect(
        "Fields (empty = default auto)",
        options=all_fields,
        default=[],
        help="If empty, PubTator uses lightweight defaults (see fetch_pmids).",
    )
    explicit_fields: list[str] | None = field_pick if field_pick else None

    include_annotations = st.checkbox("Include PubTator annotations blob", value=False)
    strict_sources = st.checkbox("Strict sources (no auto-add)", value=False)

    st.subheader("PubTator3 chunks")
    chunk_size = st.number_input("chunk_size", min_value=256, value=6000, step=256)
    chunk_overlap = st.number_input("chunk_overlap", min_value=0, value=300, step=50)

    st.subheader("Annotators")
    annotators = st.multiselect(
        "Run after fetch",
        options=["pubtator3", "medcat", "flair"],
        default=[],
        help="PubTator3 uses the fetched document text. MedCAT needs MEDCAT_API_URL or endpoint below. Flair runs HunFlair2 locally.",
    )
    include_medcat_raw = st.checkbox("MedCAT: include medcat_raw (large)", value=False)
    medcat_ep = st.text_input(
        "MedCAT endpoint override (optional)",
        value="",
        placeholder="Leave empty to use MEDCAT_API_URL from .env",
    )
    flair_model_sidebar = st.text_input(
        "Flair model id (Classifier.load)",
        value="hunflair2",
        help="Used when Flair is selected. First run downloads model weights.",
    )
    include_flair_raw = st.checkbox("Flair: include flair_raw (Sentence snapshot, large)", value=False)

tab_lit, tab_raw = st.tabs(["Literature fetch", "Raw text"])

with tab_lit:
    mode = st.selectbox(
        "Input kind",
        options=[
            ("pmid_list", "PMID list (textarea / file)"),
            ("pmid", "Single PMID"),
            ("pmcid_list", "PMCID list"),
            ("pmcid", "Single PMCID"),
            ("query", "PubMed query"),
        ],
        format_func=lambda x: x[1],
    )
    input_kind_lit = mode[0]

    ids_blob = ""
    query_text = ""
    uploaded = st.file_uploader("Optional ID file (one ID per line)", type=["txt", "csv"])

    if input_kind_lit == "query":
        query_text = st.text_input("PubMed query", value="glioblastoma review")
    elif input_kind_lit in ("pmid_list", "pmcid_list"):
        ids_blob = st.text_area("IDs (one per line or comma-separated)", height=120)
        if uploaded is not None:
            ids_blob = uploaded.read().decode("utf-8", errors="replace")
    else:
        single = st.text_input("ID", value="36403686" if input_kind_lit == "pmid" else "PMC7083241")
        ids_blob = single

with tab_raw:
    raw_doc_id = st.text_input("Document id label", value="RAW:1")
    raw_body = st.text_area(
        "Text to annotate",
        height=240,
        placeholder="Paste abstract or note text…",
    )

render_source_legend()

run_lit = tab_lit.button("Run fetch (literature)", type="primary")
run_raw = tab_raw.button("Run fetch (raw text)", type="primary")

payload_result: dict[str, Any] | None = None
error_msg = ""

if run_lit:
    raw_ids = _split_ids(ids_blob) if input_kind_lit != "query" else []
    if input_kind_lit in ("pmid", "pmcid"):
        raw_ids = [ids_blob.strip()] if ids_blob.strip() else []
    payload_result, error_msg = _run_pipeline(
        fp=fp,
        input_kind=input_kind_lit,
        raw_ids=raw_ids,
        query_text=query_text,
        raw_body="",
        raw_doc_id="",
        sources=[s for s in sources if s != "raw_text"] or ["pubtator3"],
        explicit_fields=explicit_fields,
        include_annotations=include_annotations,
        strict_sources=strict_sources,
        annotators=list(annotators),
        pubtator_chunk_size=int(chunk_size),
        pubtator_chunk_overlap=int(chunk_overlap),
        include_medcat_raw=include_medcat_raw,
        include_flair_raw=include_flair_raw,
        medcat_endpoint_override=medcat_ep,
        flair_model=flair_model_sidebar,
    )

if run_raw:
    payload_result, error_msg = _run_pipeline(
        fp=fp,
        input_kind="raw_text",
        raw_ids=[],
        query_text="",
        raw_body=raw_body,
        raw_doc_id=raw_doc_id,
        sources=["raw_text"],
        explicit_fields=explicit_fields,
        include_annotations=include_annotations,
        strict_sources=strict_sources,
        annotators=list(annotators),
        pubtator_chunk_size=int(chunk_size),
        pubtator_chunk_overlap=int(chunk_overlap),
        include_medcat_raw=include_medcat_raw,
        include_flair_raw=include_flair_raw,
        medcat_endpoint_override=medcat_ep,
        flair_model=flair_model_sidebar,
    )

if error_msg:
    st.error(error_msg)

if payload_result is not None:
    st.session_state["last_payload"] = payload_result

payload = st.session_state.get("last_payload")

if payload:
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    w = str(meta.get("warnings") or "").strip()
    if w:
        st.warning(w)

    st.subheader("Results")
    st.download_button(
        label="Download JSON",
        data=json.dumps(payload, indent=2, ensure_ascii=False),
        file_name="fetch_result.json",
        mime="application/json",
    )

    save_name = st.text_input("Save to repo outputs/ as …", value="fetch_result.json")
    if st.button("Save to disk"):
        safe = Path(save_name).name
        out_dir = ROOT / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / safe
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        st.success(f"Wrote {path}")

    with st.expander("Full JSON", expanded=False):
        st.json(payload)

    docs = payload.get("documents") or []
    ann_rows = payload.get("annotators") or []

    for i, doc in enumerate(docs):
        did = doc.get("document_id", f"doc-{i}")
        with st.expander(f"Document · {did}", expanded=(i == 0)):
            body_for_highlight = _annotator_body_text(doc) if isinstance(doc, dict) else ""

            row = next((r for r in ann_rows if r.get("document_id") == did), None)
            results = (row or {}).get("results") or {}

            ht, hc = st.tabs(["Highlighted text", "Annotation tables"])
            with ht:
                if body_for_highlight:
                    st.markdown(render_highlighted(body_for_highlight, results), unsafe_allow_html=True)
                else:
                    st.info("No text to highlight.")

            with hc:
                for src_name, items in results.items():
                    if src_name.endswith("_raw"):
                        with st.expander(f"{src_name} (raw JSON)", expanded=False):
                            st.json(items)
                        continue
                    if isinstance(items, list) and items:
                        st.markdown(f"**{src_name}** ({len(items)})")
                        st.dataframe(items, width="stretch", hide_index=True)

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bio_annotation.entity_types import (
    ANNOTATOR_CHOICES,
    ANNOTATOR_DISPLAY_NAMES,
    ENTITY_TYPE_CHOICES,
)
from bio_annotation.pipeline_runner import (
    run_pipeline_from_config,
    write_pipeline_tsv_outputs,
)
from bio_annotation.terminal_ui import (
    TerminalUIAnswers,
    build_run_manifest,
    create_run_paths,
    parse_pmids,
    prepare_input_files,
    write_json,
    write_terminal_ui_config,
)
from bio_annotation.web_ui.backend.rendering import (
    build_canonical_text,
    group_annotations_by_span,
    render_highlighted_text,
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

app = FastAPI(title="TotalAnnotator Web UI")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

RUNS_DIR = Path("outputs/web-runs")


@app.get("/", response_class=HTMLResponse)
def get_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "form.html",
        {
            "annotators": ANNOTATOR_CHOICES,
            "entity_types": ENTITY_TYPE_CHOICES,
        },
    )


@app.post("/annotate", response_class=HTMLResponse)
async def post_annotate(
    request: Request,
    input_mode: Annotated[str, Form()] = "pmids",
    pmids: Annotated[str, Form()] = "",
    pmid_file: Annotated[UploadFile | None, Form()] = None,
    plain_text: Annotated[str, Form()] = "",
    annotators: Annotated[list[str] | None, Form()] = None,
    entity_types: Annotated[list[str] | None, Form()] = None,
) -> HTMLResponse:
    selected_annotators = annotators or [value for value, _ in ANNOTATOR_CHOICES]
    paths = create_run_paths(RUNS_DIR)
    answers = await _build_answers(
        input_mode=input_mode,
        pmids=pmids,
        pmid_file=pmid_file,
        plain_text=plain_text,
        annotators=selected_annotators,
        entity_types=entity_types or [],
        paths=paths,
    )
    prepare_input_files(answers, paths)
    write_terminal_ui_config(answers, paths.config_path, paths)
    payload = run_pipeline_from_config(paths.config_path)
    write_pipeline_tsv_outputs(payload, paths.results_path)
    write_json(paths.manifest_path, build_run_manifest(answers, paths, payload))

    all_annotations = payload.get("annotations", [])
    document_views = []
    for document in payload.get("documents", []):
        document_id = document.get("document_id")
        document_annotations = [
            annotation
            for annotation in all_annotations
            if annotation.get("document_id") == document_id
        ]
        canonical_text = build_canonical_text(document)
        comparison_rows = group_annotations_by_span(document_annotations)
        cross_annotator_lookup = {
            row["keyword"].casefold(): row["by_source"] for row in comparison_rows
        }
        document_views.append(
            {
                "document": document,
                "canonical_text_length": len(canonical_text),
                "highlighted_html": render_highlighted_text(
                    canonical_text,
                    document_annotations,
                    cross_annotator_lookup,
                ),
                "comparison_rows": comparison_rows,
                "annotation_count": len(document_annotations),
            }
        )

    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "documents": document_views,
            "total_annotations": payload.get("annotation_summary", {}).get("annotation_count", 0),
            "annotators_used": [
                ANNOTATOR_DISPLAY_NAMES.get(name, name) for name in selected_annotators
            ],
            "results_path": str(paths.results_path),
        },
    )


async def _build_answers(
    *,
    input_mode: str,
    pmids: str,
    pmid_file: UploadFile | None,
    plain_text: str,
    annotators: list[str],
    entity_types: list[str],
    paths,
) -> TerminalUIAnswers:
    if input_mode == "pmids":
        parsed = parse_pmids(pmids)
        if not parsed:
            raise HTTPException(status_code=400, detail="Enter at least one PMID.")
        return TerminalUIAnswers(
            input_mode="pmids",
            pmids=parsed,
            pmid_file=None,
            annotators=annotators,
            entity_types=entity_types,
        )
    if input_mode == "pmid_file":
        if pmid_file is None or not pmid_file.filename:
            raise HTTPException(status_code=400, detail="Choose a PMID file to upload.")
        contents = await pmid_file.read()
        paths.pmids_path.parent.mkdir(parents=True, exist_ok=True)
        paths.pmids_path.write_bytes(contents)
        return TerminalUIAnswers(
            input_mode="pmid_file",
            pmids=[],
            pmid_file=paths.pmids_path,
            annotators=annotators,
            entity_types=entity_types,
        )
    if input_mode == "plain_text":
        if not plain_text.strip():
            raise HTTPException(status_code=400, detail="Paste some text to annotate.")
        return TerminalUIAnswers(
            input_mode="plain_text",
            pmids=[],
            pmid_file=None,
            annotators=annotators,
            entity_types=entity_types,
            plain_text_source="manual_text",
            plain_text_content=plain_text,
        )
    raise HTTPException(status_code=400, detail=f"Unsupported input mode: {input_mode}")

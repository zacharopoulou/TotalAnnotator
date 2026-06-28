from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from bio_annotation.entity_proposal.aioner_proposer import (
    DEFAULT_AIONER_ENTITY,
    DEFAULT_AIONER_PROJECT,
)
from bio_annotation.entity_proposal.bern2_proposer import DEFAULT_BERN2_API_URL
from bio_annotation.entity_types import (
    ANNOTATOR_CHOICES,
    ANNOTATOR_DISPLAY_NAMES,
    ANNOTATOR_ENTITY_TYPES,
    ENTITY_TYPE_CHOICES,
    ENTITY_TYPE_DISPLAY_NAMES,
)
from bio_annotation.pipeline_config import load_pipeline_config
from bio_annotation.pipeline_runner import (
    SUPPORTED_ANNOTATORS,
    run_pipeline_from_config,
    write_pipeline_tsv_outputs,
)
from bio_annotation.terminal_text_input import (
    GENERATED_TEXT_DOCUMENT_ID,
    is_text_table_file,
    prompt_existing_file,
    prompt_multiline_text,
    text_table_format,
    write_generated_text_table,
    write_generated_text_table_from_raw_text_file,
)
from bio_annotation.terminal_theme import (
    banner_lines,
    choice_lines,
    emit,
    help_lines,
    run_plan_lines,
    run_summary_lines,
    warning_lines,
)

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
PipelineRunFn = Callable[[Path], dict[str, Any]]


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_dir: Path
    config_path: Path
    results_path: Path
    manifest_path: Path
    pmids_path: Path
    plain_text_path: Path


@dataclass(frozen=True)
class TerminalUIAnswers:
    input_mode: str
    pmids: list[str]
    pmid_file: Path | None
    annotators: list[str]
    entity_types: list[str]
    plain_text_file: Path | None = None
    plain_text_source: str | None = None
    plain_text_content: str | None = None
    plain_text_document_id: str | None = None
    plain_text_title: str | None = None
    plain_text_abstract: str | None = None


def run_terminal_annotation_ui(
    *,
    runs_dir: Path = Path("outputs"),
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    pipeline_run_fn: PipelineRunFn = run_pipeline_from_config,
) -> dict[str, Any]:
    emit(output_fn, banner_lines())
    emit(output_fn, help_lines())
    paths = create_run_paths(runs_dir)
    answers = collect_terminal_ui_answers(input_fn=input_fn, output_fn=output_fn)
    emit(
        output_fn,
        run_plan_lines(
            input_mode=_input_mode_label(answers.input_mode),
            annotators=[_annotator_label(a) for a in answers.annotators],
            entity_types=[_entity_type_label(e) for e in answers.entity_types],
        ),
    )
    prepare_input_files(answers, paths)
    write_terminal_ui_config(answers, paths.config_path, paths)
    load_pipeline_config(paths.config_path)
    if "aioner" in answers.annotators:
        _, aioner_model = aioner_config_paths()
        if not Path(aioner_model).exists():
            emit(
                output_fn,
                warning_lines(
                    "AIONER model not found",
                    [
                        f"Expected model path: {aioner_model}",
                        "Run tools/aioner/setup.sh first, or set AIONER_REPO / AIONER_MODEL.",
                        "Otherwise the AIONER step will be skipped this run.",
                    ],
                ),
            )
    output_fn("")
    output_fn("Running annotation...")
    payload = pipeline_run_fn(paths.config_path)
    write_pipeline_tsv_outputs(payload, paths.results_path)
    write_json(paths.manifest_path, build_run_manifest(answers, paths, payload))
    output_fn("")
    emit(
        output_fn,
        run_summary_lines(
            document_count=payload.get("document_count", 0),
            annotation_count=payload.get("annotation_summary", {}).get("annotation_count", 0),
            results_path=paths.results_path,
            tsv_paths=terminal_ui_tsv_paths(paths),
            config_path=paths.config_path,
            manifest_path=paths.manifest_path,
        ),
    )
    return payload


def collect_terminal_ui_answers(*, input_fn: InputFn, output_fn: OutputFn) -> TerminalUIAnswers:
    mode = _prompt_choice(
        input_fn=input_fn,
        output_fn=output_fn,
        title="What do you want to annotate?",
        choices=(
            ("pmids", "PubMed articles by PMID"),
            ("pmid_file", "PubMed articles from a PMID file"),
            ("plain_text", "Plain text"),
        ),
    )
    pmids: list[str] = []
    pmid_file: Path | None = None
    text_source = text_content = None
    text_file: Path | None = None
    if mode == "pmids":
        pmids = _prompt_pmids(input_fn=input_fn)
    elif mode == "pmid_file":
        pmid_file = _prompt_existing_pmid_file(input_fn=input_fn, output_fn=output_fn)
    else:
        text_source = _prompt_choice(
            input_fn=input_fn,
            output_fn=output_fn,
            title="How do you want to provide plain text?",
            choices=(
                ("table_file", "CSV/TSV table file with document_id, title, abstract columns"),
                ("text_file", "Raw text file with one text per line"),
                ("manual_text", "Enter text in the terminal"),
            ),
        )
        if text_source in {"table_file", "text_file"}:
            text_file = prompt_existing_file(input_fn=input_fn, output_fn=output_fn)
            if text_source == "table_file" and not is_text_table_file(text_file):
                raise ValueError("Plain text table files must use .csv or .tsv extension.")
        else:
            text_content = prompt_multiline_text(input_fn=input_fn, output_fn=output_fn)
    annotators = _prompt_multi_choice(
        input_fn=input_fn,
        output_fn=output_fn,
        title="Choose annotators, or press Enter for default annotators",
        choices=ANNOTATOR_CHOICES,
        default_values=[value for value, _ in ANNOTATOR_CHOICES if value != "aioner"],
        validate_values=_validate_selected_annotators,
    )
    entity_types = _prompt_entity_types(input_fn=input_fn, output_fn=output_fn, annotators=annotators)
    return TerminalUIAnswers(
        mode,
        pmids,
        pmid_file,
        annotators,
        entity_types,
        plain_text_file=text_file,
        plain_text_source=text_source,
        plain_text_content=text_content,
    )


def create_run_paths(runs_dir: Path, *, now: datetime | None = None) -> RunPaths:
    del now
    run_dir = runs_dir.expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunPaths(
        "annotation",
        run_dir,
        run_dir / "config.toml",
        run_dir / "results.json",
        run_dir / "run_manifest.json",
        run_dir / "pmids.txt",
        run_dir / "plain_text.tsv",
    )


def prepare_input_files(answers: TerminalUIAnswers, paths: RunPaths) -> None:
    if answers.input_mode == "pmid_file" and answers.pmid_file is None:
        raise ValueError("PMID file input mode requires a PMID file path.")
    if answers.input_mode == "plain_text" and not _uses_existing_text_table(answers):
        if answers.plain_text_source == "text_file" and answers.plain_text_file is not None:
            write_generated_text_table_from_raw_text_file(paths.plain_text_path, answers.plain_text_file)
        else:
            text = _plain_text_content(answers)
            write_generated_text_table(paths.plain_text_path, text)


def write_terminal_ui_config(answers: TerminalUIAnswers, config_path: Path, paths: RunPaths) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(build_terminal_ui_config_text(answers, paths), encoding="utf-8")


AIONER_DEFAULT_MODEL_RELPATH = "pretrained_models/AIONER/PubmedBERT-CRF-AIONER.h5"


def aioner_config_paths() -> tuple[str, str]:
    """Resolve AIONER repo/model paths for the generated config."""

    repo_root = Path(__file__).resolve().parents[2]
    repo = os.environ.get("AIONER_REPO") or str(repo_root / "AIONER")
    model = os.environ.get("AIONER_MODEL") or str(Path(repo) / AIONER_DEFAULT_MODEL_RELPATH)
    return repo, model


def build_terminal_ui_config_text(answers: TerminalUIAnswers, paths: RunPaths) -> str:
    lines = ["[input]"]
    if answers.input_mode == "pmids":
        lines += ['mode = "pmids"', f"pmids = {_toml_string_list(answers.pmids)}"]
    elif answers.input_mode == "pmid_file":
        if answers.pmid_file is None:
            raise ValueError("PMID file input mode requires a PMID file path.")
        lines += ['mode = "pmid_file"', f"pmid_file = {_toml_string(str(answers.pmid_file))}"]
    elif answers.input_mode == "plain_text":
        text_file = _plain_text_config_file(answers, paths)
        lines += [
            'mode = "text_table"',
            f"text_file = {_toml_string(str(text_file))}",
            f"format = {_toml_string(text_table_format(text_file))}",
            'document_id_column = "document_id"',
            'title_column = "title"',
            'abstract_column = "abstract"',
        ]
    else:
        raise ValueError(f"Unsupported terminal UI input mode: {answers.input_mode}")
    lines += ["", "[enrichment]", "sources = []", "", "[annotators]", f"enabled = {_toml_string_list(answers.annotators)}"]
    if "bern2" in answers.annotators:
        lines += [
            "",
            "[annotators.bern2]",
            'runtime = "remote_api"',
            f"endpoint = {_toml_string(DEFAULT_BERN2_API_URL)}",
            "timeout = 30",
        ]
    if "pubtator3" in answers.annotators:
        pubtator3_mode = "text_only" if answers.input_mode == "plain_text" else "auto"
        lines += [
            "",
            "[annotators.pubtator3]",
            'runtime = "remote_api"',
            'endpoint = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"',
            'format = "biocjson"',
            "timeout = 60",
            f"mode = {_toml_string(pubtator3_mode)}",
            'bioconcept = "All"',
            "poll_interval_seconds = 2.0",
            "poll_backoff = 1.5",
            "max_poll_interval_seconds = 15.0",
            "max_poll_attempts = 30",
        ]
    if "aioner" in answers.annotators:
        aioner_repo, aioner_model = aioner_config_paths()
        lines += [
            "",
            "[annotators.aioner]",
            'runtime = "local_subprocess"',
            f"repo = {_toml_string(aioner_repo)}",
            f"model = {_toml_string(aioner_model)}",
            f"entity = {_toml_string(DEFAULT_AIONER_ENTITY)}",
            f"project = {_toml_string(DEFAULT_AIONER_PROJECT)}",
        ]
    lines += [
        "",
        "[filters]",
        f"entity_types = {_toml_string_list(answers.entity_types)}",
        "",
        "[output]",
        f"path = {_toml_string(str(paths.results_path))}",
        "",
    ]
    return "\n".join(lines)


def build_run_manifest(answers: TerminalUIAnswers, paths: RunPaths, payload: dict[str, Any]) -> dict[str, Any]:
    manifest = {
        "run_id": paths.run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_mode": answers.input_mode,
        "annotators": answers.annotators,
        "annotator_labels": [_annotator_label(a) for a in answers.annotators],
        "entity_types": answers.entity_types,
        "entity_type_labels": [_entity_type_label(e) for e in answers.entity_types],
        "config_path": str(paths.config_path),
        "results_path": str(paths.results_path),
        "tsv_paths": {key: str(path) for key, path in terminal_ui_tsv_paths(paths).items()},
        "manifest_path": str(paths.manifest_path),
        "document_count": payload.get("document_count", 0),
        "annotation_count": payload.get("annotation_summary", {}).get("annotation_count", 0),
    }
    if answers.input_mode == "pmids":
        manifest.update({"pmids": answers.pmids, "pmids_count": len(answers.pmids)})
    elif answers.input_mode == "pmid_file":
        manifest.update({"pmid_file": str(answers.pmid_file) if answers.pmid_file else None})
    elif answers.input_mode == "plain_text":
        manifest.update(
            {
                "plain_text_source": answers.plain_text_source,
                "plain_text_file": str(answers.plain_text_file) if answers.plain_text_file else None,
                "plain_text_path": str(_plain_text_config_file(answers, paths)),
            }
        )
        if not _uses_existing_text_table(answers):
            manifest["plain_text_document_id"] = GENERATED_TEXT_DOCUMENT_ID
    return manifest


def terminal_ui_tsv_paths(paths: RunPaths) -> dict[str, Path]:
    return {
        "Keywords TSV": paths.results_path.with_name(f"{paths.results_path.stem}.keywords.tsv"),
        "Keyword evidence TSV": paths.results_path.with_name(
            f"{paths.results_path.stem}.keyword_annotator_evidence.tsv"
        ),
        "Annotations TSV": paths.results_path.with_name(f"{paths.results_path.stem}.annotations.tsv"),
    }


def write_plain_text_table(path: Path, *, document_id: str, title: str, abstract: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["document_id", "title", "abstract"], delimiter="\t")
        writer.writeheader()
        writer.writerow({"document_id": document_id, "title": title, "abstract": abstract})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def find_unsupported_entity_types(annotators: list[str], entity_types: list[str]) -> dict[str, list[str]]:
    if not entity_types:
        return {}
    return {
        a: missing
        for a in annotators
        if (missing := [e for e in entity_types if e not in ANNOTATOR_ENTITY_TYPES.get(a, set())])
    }


def _prompt_entity_types(*, input_fn: InputFn, output_fn: OutputFn, annotators: list[str]) -> list[str]:
    while True:
        entity_types = _prompt_multi_choice(
            input_fn=input_fn,
            output_fn=output_fn,
            title="Choose entity types to include, or press Enter for all entity types",
            choices=ENTITY_TYPE_CHOICES,
            default_values=[],
            allow_empty=True,
        )
        unsupported = find_unsupported_entity_types(annotators, entity_types)
        if not unsupported:
            return entity_types
        messages = [
            f"{_annotator_label(annotator)} does not produce: {', '.join(_entity_type_label(e) for e in missing)}"
            for annotator, missing in unsupported.items()
        ]
        emit(output_fn, warning_lines("Entity type compatibility warning", messages))
        if _prompt_yes_no(input_fn=input_fn, prompt="Continue with this selection? [y/N]: "):
            return entity_types


def _prompt_choice(*, input_fn: InputFn, output_fn: OutputFn, title: str, choices: tuple[tuple[str, str], ...]) -> str:
    output_fn("")
    emit(output_fn, choice_lines(title, choices))
    while True:
        raw = input_fn("Choose one: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1][0]
        output_fn(f"Please choose one of: {', '.join(str(i) for i in range(1, len(choices) + 1))}")


def _prompt_multi_choice(
    *,
    input_fn: InputFn,
    output_fn: OutputFn,
    title: str,
    choices: tuple[tuple[str, str], ...],
    default_values: list[str],
    allow_empty: bool = False,
    validate_values: Callable[[list[str]], None] | None = None,
) -> list[str]:
    output_fn("")
    default_indexes = [i for i, (v, _) in enumerate(choices, start=1) if v in default_values]
    emit(output_fn, choice_lines(title, choices, default_indexes=default_indexes))
    default_hint = f" [default: {', '.join(str(i) for i in default_indexes)}]" if default_indexes else ""
    while True:
        raw = input_fn(f"Choose comma-separated numbers{default_hint}: ").strip()
        if not raw and default_values:
            selected = list(default_values)
            if validate_values:
                validate_values(selected)
            return selected
        if not raw and allow_empty:
            return []
        selected: list[str] = []
        ok = True
        for item in re.split(r"[,\s]+", raw):
            if not item:
                continue
            if not item.isdigit() or not 1 <= int(item) <= len(choices):
                ok = False
                break
            value = choices[int(item) - 1][0]
            if value not in selected:
                selected.append(value)
        if ok and (selected or allow_empty):
            if validate_values:
                validate_values(selected)
            return selected
        output_fn("Please choose valid comma-separated numbers.")


def _validate_selected_annotators(annotators: list[str]) -> None:
    unsupported = [a for a in annotators if a not in SUPPORTED_ANNOTATORS]
    if unsupported:
        raise ValueError(f"Unsupported annotators requested: {', '.join(unsupported)}")


def _prompt_pmids(*, input_fn: InputFn) -> list[str]:
    while True:
        pmids = parse_pmids(_prompt_required(input_fn, "Enter PMIDs, separated by commas or spaces: "))
        if pmids:
            return pmids


def _prompt_existing_pmid_file(*, input_fn: InputFn, output_fn: OutputFn) -> Path:
    while True:
        raw = input_fn("PMID file path: ").strip()
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if path.is_file():
            return path
        output_fn(f"File not found: {path}")


def parse_pmids(raw: str) -> list[str]:
    pmids: list[str] = []
    for item in re.split(r"[,\s]+", raw.strip()):
        if item and item not in pmids:
            pmids.append(item)
    return pmids


def _uses_existing_text_table(answers: TerminalUIAnswers) -> bool:
    return answers.plain_text_source == "table_file" and answers.plain_text_file is not None


def _plain_text_config_file(answers: TerminalUIAnswers, paths: RunPaths) -> Path:
    if _uses_existing_text_table(answers):
        assert answers.plain_text_file is not None
        return answers.plain_text_file
    return paths.plain_text_path


def _plain_text_content(answers: TerminalUIAnswers) -> str:
    if answers.plain_text_source == "manual_text":
        return (answers.plain_text_content or "").strip()
    if answers.plain_text_file is None:
        if answers.plain_text_abstract:
            return answers.plain_text_abstract.strip()
        raise ValueError("Plain text input requires a file path or text entered in the terminal.")
    return answers.plain_text_file.read_text(encoding="utf-8").strip()


def _prompt_required(input_fn: InputFn, prompt: str) -> str:
    while True:
        value = input_fn(prompt).strip()
        if value:
            return value


def _prompt_yes_no(*, input_fn: InputFn, prompt: str) -> bool:
    return input_fn(prompt).strip().lower() in {"y", "yes"}


def _input_mode_label(input_mode: str) -> str:
    return {
        "pmids": "PubMed articles by PMID",
        "pmid_file": "PubMed articles from a PMID file",
        "plain_text": "Plain text",
    }.get(input_mode, input_mode)


def _annotator_label(annotator: str) -> str:
    return ANNOTATOR_DISPLAY_NAMES.get(annotator, annotator)


def _entity_type_label(entity_type: str) -> str:
    return ENTITY_TYPE_DISPLAY_NAMES.get(entity_type, entity_type)


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_string_list(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(v) for v in values) + "]"

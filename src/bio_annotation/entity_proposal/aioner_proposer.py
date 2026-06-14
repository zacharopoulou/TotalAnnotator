from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

DEFAULT_AIONER_ENTITY = "ALL"
DEFAULT_AIONER_PROJECT = "tools/aioner"
DEFAULT_AIONER_TIMEOUT = 600

SETUP_HINT = (
    "Run tools/aioner/setup.sh to install AIONER, then set annotators.aioner.repo "
    "and annotators.aioner.model in your config (or the AIONER_REPO / AIONER_MODEL "
    "environment variables)."
)


def build_aioner_pubtator_input(document: Document) -> str:
    """Render a Document as a single-document PubTator file for AIONER.

    AIONER reconstructs the full text as ``title + ' ' + abstract`` and reports
    absolute character offsets over it. We place the whole document text in the
    title line (with newlines flattened to single spaces, preserving length and
    therefore every offset) and leave the abstract empty, so AIONER's offsets map
    directly onto ``document.text``.
    """

    flat_text = document.text.replace("\n", " ")
    doc_id = (document.document_id or "0").replace("|", "_")
    return f"{doc_id}|t|{flat_text}\n{doc_id}|a|\n\n"


def parse_aioner_response(document: Document, payload: Any) -> list[Annotation]:
    if not payload:
        return []

    annotations: list[Annotation] = []
    for line in str(payload).splitlines():
        if not line.strip() or "|t|" in line or "|a|" in line:
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        _, start, end, mention, entity_type = parts[:5]
        try:
            start_offset = int(start)
            end_offset = int(end)
        except ValueError:
            continue
        if not mention:
            continue
        annotations.append(
            make_annotation(
                document=document,
                source="aioner",
                span_text=mention,
                entity_type=entity_type,
                start=start_offset,
                end=end_offset,
            )
        )
    return annotations


def call_aioner(
    document: Document,
    *,
    repo: str | None = None,
    model: str | None = None,
    vocab: str | None = None,
    entity: str = DEFAULT_AIONER_ENTITY,
    project: str = DEFAULT_AIONER_PROJECT,
    python: str | None = None,
    timeout: int = DEFAULT_AIONER_TIMEOUT,
) -> str:
    """Run AIONER as a subprocess in its isolated environment and return raw output.

    AIONER lives in its own Python 3.8 env (it pins TensorFlow 2.3, which has no
    wheel for this project's interpreter), so it is invoked out-of-process. By
    default we launch it through ``uv run --project <project>``; pass ``python`` to
    point at an interpreter directly instead.
    """

    repo = repo or os.getenv("AIONER_REPO")
    model = model or os.getenv("AIONER_MODEL")
    if not repo:
        raise RuntimeError(f"AIONER repo path is not configured. {SETUP_HINT}")
    if not model:
        raise RuntimeError(f"AIONER model path is not configured. {SETUP_HINT}")

    repo_path = Path(repo).resolve()
    model_path = Path(model).resolve()
    script = repo_path / "src" / "AIONER_Run.py"
    vocab_path = Path(vocab).resolve() if vocab else repo_path / "vocab" / "AIO_label.vocab"
    if not script.exists():
        raise RuntimeError(f"AIONER run script not found at {script}. {SETUP_HINT}")

    with tempfile.TemporaryDirectory() as tmp:
        in_dir = Path(tmp) / "input"
        out_dir = Path(tmp) / "output"
        in_dir.mkdir()
        out_dir.mkdir()
        in_file = in_dir / "document.txt"
        in_file.write_text(build_aioner_pubtator_input(document), encoding="utf-8")

        if python:
            command = [python, str(script)]
        else:
            # The subprocess runs with cwd set to the AIONER source dir, so resolve
            # the uv project path to absolute (relative to the launch directory) first.
            project_dir = str(Path(project).resolve())
            command = ["uv", "run", "--project", project_dir, "python", str(script)]
        command += [
            "-i",
            str(in_dir) + os.sep,
            "-m",
            str(model_path),
            "-v",
            str(vocab_path),
            "-e",
            entity,
            "-o",
            str(out_dir) + os.sep,
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=str(repo_path / "src"),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"AIONER could not be launched ('{command[0]}' not found): {exc}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"AIONER timed out after {timeout}s.") from exc

        if completed.returncode != 0:
            raise RuntimeError(
                f"AIONER failed (exit {completed.returncode}): {completed.stderr.strip()}"
            )

        out_file = out_dir / in_file.name
        if not out_file.exists():
            produced = list(out_dir.iterdir())
            if not produced:
                return ""
            out_file = produced[0]
        return out_file.read_text(encoding="utf-8")


def annotate_with_aioner(
    document: Document,
    *,
    response: Any = None,
    request_fn: Callable[[Document], Any] | None = None,
    repo: str | None = None,
    model: str | None = None,
    vocab: str | None = None,
    entity: str = DEFAULT_AIONER_ENTITY,
    project: str = DEFAULT_AIONER_PROJECT,
    python: str | None = None,
    timeout: int = DEFAULT_AIONER_TIMEOUT,
) -> list[Annotation]:
    payload = response
    if payload is None and request_fn is not None:
        payload = request_fn(document)
    if payload is None:
        payload = call_aioner(
            document,
            repo=repo,
            model=model,
            vocab=vocab,
            entity=entity,
            project=project,
            python=python,
            timeout=timeout,
        )
    return parse_aioner_response(document, payload)

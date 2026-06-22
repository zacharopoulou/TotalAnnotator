"""Windows-only AIONER runner.

Two adjustments vs the macOS/Linux ``aioner_proposer`` (which is left untouched):
POSIX paths (AIONER splits the model path on "/", so backslashes break it) and
UTF-8 decoding (a non-UTF-8 console like Greek cp1253 would otherwise crash).
Build/parse helpers are reused from the base module, not duplicated.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from bio_annotation.entity_proposal.aioner_proposer import (
    DEFAULT_AIONER_ENTITY,
    DEFAULT_AIONER_PROJECT,
    DEFAULT_AIONER_TIMEOUT,
    SETUP_HINT,
    build_aioner_pubtator_input,
    parse_aioner_response,
)
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation


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
    """Run AIONER as a subprocess on Windows and return its raw output.

    Mirrors ``aioner_proposer.call_aioner`` but passes POSIX-style paths and
    forces UTF-8 decoding (see the module docstring).
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
            command = [python, script.as_posix()]
        else:
            # The subprocess runs with cwd set to the AIONER source dir, so resolve
            # the uv project path to absolute (relative to the launch directory) first.
            project_dir = str(Path(project).resolve())
            command = ["uv", "run", "--project", project_dir, "python", script.as_posix()]
        # POSIX-style paths: AIONER splits the model path on "/" internally, and
        # Windows accepts forward slashes everywhere else.
        command += [
            "-i",
            in_dir.as_posix() + "/",
            "-m",
            model_path.as_posix(),
            "-v",
            vocab_path.as_posix(),
            "-e",
            entity,
            "-o",
            out_dir.as_posix() + "/",
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=str(repo_path / "src"),
                capture_output=True,
                text=True,
                # AIONER emits UTF-8; decode it as such instead of the Windows
                # locale codec. errors="replace" keeps a stray byte from masking
                # the real subprocess result.
                encoding="utf-8",
                errors="replace",
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

"""Prompted, on-demand installation of optional annotator dependencies.

Extras in this project share a single universal resolution in ``uv.lock``, so
enabling one only adds packages; versions of already-installed packages do not
change. That makes it safe to install mid-process and keep going, without
restarting the interpreter.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Callable, Iterable

from bio_annotation.entity_proposal.apollo_proposer import APOLLO_INSTALL_HINT
from bio_annotation.entity_proposal.bent_proposer import DEFAULT_BENT_PROJECT
from bio_annotation.entity_proposal.biobert_proposer import BIOBERT_INSTALL_HINT
from bio_annotation.entity_proposal.clinicalbert_proposer import CLINICALBERT_INSTALL_HINT
from bio_annotation.entity_proposal.d4data_proposer import D4DATA_INSTALL_HINT
from bio_annotation.entity_proposal.flair_proposer import FLAIR_INSTALL_HINT
from bio_annotation.entity_proposal.scispacy_proposer import (
    SCISPACY_INSTALL_HINT,
    SCISPACY_MODEL_BY_ANNOTATOR,
)
from bio_annotation.entity_proposal.stanza_proposer import (
    STANZA_ANNOTATORS,
    STANZA_INSTALL_HINT,
)

DISABLE_ENV_VAR = "TOTALANNOTATOR_NO_AUTO_INSTALL"

EXTRA_MODULES: dict[str, tuple[str, ...]] = {
    "flair": ("flair",),
    "clinicalbert": ("transformers", "torch"),
    "biobert": ("transformers", "torch"),
    "apollo": ("transformers", "torch"),
    "d4data": ("transformers", "torch"),
    "stanza": ("stanza",),
    "scispacy": ("scispacy", "spacy"),
    "benchmarks": ("datasets", "pandas", "tabulate"),
}

ANNOTATOR_EXTRAS: dict[str, str] = {
    "flair": "flair",
    "clinicalbert": "clinicalbert",
    "biobert": "biobert",
    "apollo": "apollo",
    "d4data": "d4data",
    **{annotator: "scispacy" for annotator in SCISPACY_MODEL_BY_ANNOTATOR},
    **{annotator: "stanza" for annotator in STANZA_ANNOTATORS},
}

EXTRA_INSTALL_HINTS: dict[str, str] = {
    "flair": FLAIR_INSTALL_HINT,
    "clinicalbert": CLINICALBERT_INSTALL_HINT,
    "biobert": BIOBERT_INSTALL_HINT,
    "apollo": APOLLO_INSTALL_HINT,
    "d4data": D4DATA_INSTALL_HINT,
    "stanza": STANZA_INSTALL_HINT,
    "scispacy": SCISPACY_INSTALL_HINT,
}


def extra_installed(extra: str) -> bool:
    try:
        return all(find_spec(module) is not None for module in EXTRA_MODULES[extra])
    except (ImportError, ValueError):
        return False


def missing_extras(annotators: Iterable[str]) -> list[str]:
    """Extras required by ``annotators`` that are not installed, in order."""

    missing: list[str] = []
    for annotator in annotators:
        extra = ANNOTATOR_EXTRAS.get(annotator)
        if extra is not None and extra not in missing and not extra_installed(extra):
            missing.append(extra)
    return missing


def uv_project_root() -> Path | None:
    """Return the uv project directory when running inside its own venv."""

    root = Path(sys.prefix).parent
    if (root / "pyproject.toml").exists() and (root / "uv.lock").exists():
        return root
    return None


def ensure_extras(
    annotators: Iterable[str],
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Offer to install the extras ``annotators`` need.

    Returns without installing when the environment is not uv-managed, the
    session is not interactive, or the user declines; the caller is expected to
    fall back to raising the manual install hint.
    """

    missing = missing_extras(annotators)
    if not missing or os.environ.get(DISABLE_ENV_VAR):
        return
    root = uv_project_root()
    if root is None or shutil.which("uv") is None or not sys.stdin.isatty():
        return

    output_fn("")
    output_fn(f"The selected annotators need optional dependencies: {', '.join(missing)}.")
    output_fn(
        "Installing downloads several GB (PyTorch and model packages) and can take a few minutes."
    )
    if input_fn("Install them now with uv? [Y/n] ").strip().lower() not in ("", "y", "yes"):
        return

    # Every already-installed extra is passed too: uv sync is exact and would
    # otherwise uninstall the extras that are not named here.
    extras = sorted({*missing, *(e for e in EXTRA_MODULES if extra_installed(e))})
    command = ["uv", "sync", "--project", str(root)]
    for extra in extras:
        command += ["--extra", extra]
    output_fn(f"Running: {' '.join(command)}")
    if subprocess.run(command, check=False).returncode != 0:
        output_fn("uv sync failed. Install the extras manually and re-run.")
        return
    importlib.invalidate_caches()


# Annotators provisioned by a setup script instead of a pip extra: they need an
# external repo, their own interpreter, or downloaded resources.
TOOL_SETUP_SCRIPTS: dict[str, str] = {
    "aioner": "tools/aioner/setup.sh",
    "bent": "tools/bent/setup.sh",
}
TOOL_SETUP_NOTES: dict[str, str] = {
    "aioner": (
        "Clones the AIONER repo, downloads ~1.5 GB of pretrained models, and provisions "
        "a separate Python 3.8 environment."
    ),
    "bent": (
        "Provisions a separate Python <=3.10 environment and downloads BENT's resources. "
        "Needs wget, git, make, g++ and javac on PATH."
    ),
}
AIONER_DEFAULT_MODEL_RELPATH = "pretrained_models/AIONER/PubmedBERT-CRF-AIONER.h5"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def aioner_config_paths() -> tuple[str, str]:
    """Resolve AIONER repo/model paths for the generated config."""

    repo = os.environ.get("AIONER_REPO") or str(repo_root() / "AIONER")
    model = os.environ.get("AIONER_MODEL") or str(Path(repo) / AIONER_DEFAULT_MODEL_RELPATH)
    return repo, model


def tool_ready(annotator: str, settings: dict[str, object]) -> bool:
    """Whether a setup-script annotator has its environment and resources in place."""

    if annotator == "aioner":
        _, model = aioner_config_paths()
        configured = settings.get("model")
        if isinstance(configured, str) and configured.strip():
            model = configured.strip()
        return Path(model).exists() and (repo_root() / "tools" / "aioner" / ".venv").exists()
    if annotator == "bent":
        project = settings.get("project")
        directory = project.strip() if isinstance(project, str) and project.strip() else DEFAULT_BENT_PROJECT
        return (Path(directory) / ".venv").exists()
    return True


def ensure_tool_environments(
    annotators: Iterable[str],
    settings_by_annotator: dict[str, dict[str, object]],
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Offer to run the setup script for annotators that need one.

    Never raises: a declined or failed setup leaves the annotator unavailable and
    the run continues without it, as it did before this prompt existed.
    """

    pending = [
        annotator
        for annotator in annotators
        if annotator in TOOL_SETUP_SCRIPTS
        and not tool_ready(annotator, settings_by_annotator.get(annotator, {}))
    ]
    for annotator in pending:
        script = repo_root() / TOOL_SETUP_SCRIPTS[annotator]
        skipped = f"The {annotator} step will return no annotations this run."
        if not script.exists() or shutil.which("bash") is None:
            output_fn(f"Warning: {annotator} is not set up and {script} cannot be run here. {skipped}")
            continue
        if os.environ.get(DISABLE_ENV_VAR) or not sys.stdin.isatty():
            output_fn(f"Warning: {annotator} is not set up. Run {script} first. {skipped}")
            continue

        output_fn("")
        output_fn(f"{annotator} needs a one-time setup: {script}")
        output_fn(TOOL_SETUP_NOTES[annotator])
        if input_fn("Run it now? [Y/n] ").strip().lower() not in ("", "y", "yes"):
            output_fn(f"Skipping setup. {skipped}")
            continue
        if subprocess.run(["bash", str(script)], check=False).returncode != 0:
            output_fn(f"{script} failed. {skipped}")

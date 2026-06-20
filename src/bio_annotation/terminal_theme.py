from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


THEME_WIDTH = 100


def render_lines(renderable: Any) -> list[str]:
    """Render a Rich object to plain terminal lines for the existing output_fn API."""

    console = Console(width=THEME_WIDTH, color_system=None, force_terminal=False, record=True)
    console.print(renderable)
    return console.export_text(clear=True).rstrip("\n").splitlines()


def emit(output_fn, lines: Iterable[str]) -> None:
    for line in lines:
        output_fn(line)


def banner_lines() -> list[str]:
    title = Text("TotalAnnotator", justify="center", style="bold")
    subtitle = Text("Biomedical entity annotation cockpit", justify="center")
    body = Text.assemble(title, "\n", subtitle)
    return render_lines(Panel(body, box=box.ROUNDED, padding=(1, 2)))


def help_lines() -> list[str]:
    return render_lines(
        Panel(
            "Choose an input source, annotators, and entity filters. "
            "Each run writes a reproducible config, JSON results, TSV review tables, and a manifest.",
            title="Workflow",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def choice_lines(title: str, choices: tuple[tuple[str, str], ...], *, default_indexes: list[int] | None = None) -> list[str]:
    table = Table(title=title, box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("Option")
    table.add_column("Default", justify="center", no_wrap=True)
    defaults = set(default_indexes or [])
    for index, (_, label) in enumerate(choices, start=1):
        table.add_row(str(index), label, "yes" if index in defaults else "")
    return render_lines(table)


def warning_lines(title: str, messages: Iterable[str]) -> list[str]:
    return render_lines(
        Panel(
            "\n".join(messages),
            title=title,
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def run_plan_lines(*, input_mode: str, annotators: list[str], entity_types: list[str]) -> list[str]:
    table = Table(title="Run plan", box=box.SIMPLE_HEAVY, show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Input", input_mode)
    table.add_row("Annotators", ", ".join(annotators) or "all")
    table.add_row("Entity filters", ", ".join(entity_types) if entity_types else "all entity types")
    return render_lines(table)


def run_summary_lines(*, document_count: int, annotation_count: int, results_path: Path, tsv_paths: dict[str, Path], config_path: Path, manifest_path: Path) -> list[str]:
    table = Table(title="Run complete", box=box.ROUNDED, show_header=False)
    table.add_column("Item", style="bold")
    table.add_column("Value")
    table.add_row("Documents", str(document_count))
    table.add_row("Annotations", str(annotation_count))
    table.add_row("Results JSON", str(results_path))
    for label, path in tsv_paths.items():
        table.add_row(label, str(path))
    table.add_row("Config", str(config_path))
    table.add_row("Manifest", str(manifest_path))
    return render_lines(table)

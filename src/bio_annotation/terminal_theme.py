from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import Any

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme
from rich.text import Text

from bio_annotation.progress import ProgressEvent, ProgressReporter, describe


THEME_WIDTH = 100
TOTALANNOTATOR_THEME = Theme(
    {
        "brand": "bold cyan",
        "accent": "bold magenta",
        "muted": "cyan",
        "panel.border": "bright_cyan",
        "panel.title": "bold cyan",
        "table.header": "bold cyan",
        "table.title": "bold magenta",
        "field": "bold cyan",
        "ok": "bold green",
        "warning": "bold yellow",
        "path": "bright_blue",
    }
)


@contextmanager
def annotator_spinner(console: Console | None = None) -> Iterator[ProgressReporter]:
    console = console or Console(theme=TOTALANNOTATOR_THEME)
    status = console.status("Running annotation...", spinner="dots")
    status.start()
    try:

        def report(event: ProgressEvent) -> None:
            if event.event == "start":
                status.update(Text(describe(event), style="muted"))
            elif event.event == "error":
                # Printed above the spinner so failures survive the run.
                console.print(Text(describe(event), style="warning"))

        yield report
    finally:
        status.stop()


def render_lines(renderable: Any) -> list[str]:
    """Render a Rich object to plain terminal lines for the existing output_fn API."""

    buffer = StringIO()
    console = Console(
        width=THEME_WIDTH,
        color_system="truecolor",
        force_terminal=True,
        file=buffer,
        theme=TOTALANNOTATOR_THEME,
    )
    console.print(renderable)
    return buffer.getvalue().rstrip("\n").splitlines()


def emit(output_fn, lines: Iterable[str]) -> None:
    for line in lines:
        output_fn(line)


def banner_lines() -> list[str]:
    title = Text("TotalAnnotator", justify="center", style="brand")
    subtitle = Text("Biomedical entity annotation workspace", justify="center", style="muted")
    body = Text.assemble(title, "\n", subtitle)
    return render_lines(
        Panel(
            Align.center(body),
            box=box.ROUNDED,
            border_style="panel.border",
            padding=(1, 2),
        )
    )


def help_lines() -> list[str]:
    return render_lines(
        Panel(
            Text.assemble(
                ("Choose an input source, annotators, and entity filters.\n", "muted"),
                ("Each run writes ", "muted"),
                ("config", "field"),
                (", ", "muted"),
                ("JSON", "field"),
                (", ", "muted"),
                ("TSV review tables", "field"),
                (", and a ", "muted"),
                ("manifest", "field"),
                (".", "muted"),
            ),
            title="Workflow",
            title_align="left",
            border_style="panel.border",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def choice_lines(title: str, choices: tuple[tuple[str, str], ...], *, default_indexes: list[int] | None = None) -> list[str]:
    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="table.header",
        title_style="table.title",
        border_style="panel.border",
        pad_edge=True,
    )
    table.add_column("#", justify="right", no_wrap=True, style="accent")
    table.add_column("Option")
    table.add_column("Default", justify="center", no_wrap=True, style="ok")
    defaults = set(default_indexes or [])
    for index, (_, label) in enumerate(choices, start=1):
        table.add_row(str(index), label, "default" if index in defaults else "")
    return render_lines(table)


def warning_lines(title: str, messages: Iterable[str]) -> list[str]:
    return render_lines(
        Panel(
            "\n".join(messages),
            title=title,
            title_align="left",
            border_style="warning",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def run_plan_lines(*, input_mode: str, annotators: list[str], entity_types: list[str]) -> list[str]:
    table = Table(
        title="Run plan",
        box=box.ROUNDED,
        show_header=False,
        title_style="table.title",
        border_style="panel.border",
    )
    table.add_column("Field", style="field")
    table.add_column("Value")
    table.add_row("Input", input_mode)
    table.add_row("Annotators", ", ".join(annotators) or "all")
    table.add_row("Entity filters", ", ".join(entity_types) if entity_types else "all entity types")
    return render_lines(table)


def run_summary_lines(*, document_count: int, annotation_count: int, results_path: Path, tsv_paths: dict[str, Path], config_path: Path, manifest_path: Path) -> list[str]:
    table = Table(
        title="Run complete",
        box=box.ROUNDED,
        show_header=False,
        title_style="table.title",
        border_style="ok",
    )
    table.add_column("Item", style="field")
    table.add_column("Value")
    table.add_row("Documents", str(document_count))
    table.add_row("Annotations", str(annotation_count))
    table.add_row("Results JSON", str(results_path))
    for label, path in tsv_paths.items():
        table.add_row(label, str(path))
    table.add_row("Config", str(config_path))
    table.add_row("Manifest", str(manifest_path))
    return render_lines(table)

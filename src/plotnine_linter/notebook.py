"""Lint every plot in a Jupyter notebook by running it.

The notebook runs in a fresh kernel, with its own folder as the working
directory and the linter loaded. A cell can fail, for example when a data file
is missing. The run then records the error and continues. So the linter checks
every plot that the notebook can draw. It never changes the notebook file.

    plotnine-linter check project.ipynb
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .findings import Finding, Report, Severity
from .jupyter import COLLECT_MIME

_SETUP = (
    "%load_ext plotnine_linter\n"
    "import plotnine_linter.jupyter as _plotnine_linter_jupyter\n"
    "_plotnine_linter_jupyter._STATE['collect'] = True"
)


@dataclass
class PlotResult:
    cell: int  # 1-based index among the notebook's code cells
    report: Report

    @property
    def audit(self):
        return self.report.audit


@dataclass
class NotebookReport:
    path: str
    plots: list[PlotResult] = field(default_factory=list)
    failed_cells: list[tuple[int, str]] = field(
        default_factory=list
    )  # (cell, error name: message)
    code_cells: int = 0
    empty_figures: int = 0  # figures with no data (not counted as plots)
    error: str | None = None  # the notebook couldn't be run at all

    @property
    def findings(self) -> list[tuple[int, Finding]]:
        return [(p.cell, f) for p in self.plots for f in p.report.findings]

    def at_least(self, severity: str) -> list[tuple[int, Finding]]:
        sev = Severity.parse(severity)
        return [(c, f) for c, f in self.findings if f.severity >= sev]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "code_cells": self.code_cells,
            "plots_linted": len(self.plots),
            "empty_figures": self.empty_figures,
            "failed_cells": [{"cell": c, "error": e} for c, e in self.failed_cells],
            "error": self.error,
            "plots": [{"cell": p.cell, **p.report.to_dict()} for p in self.plots],
        }

    def __str__(self) -> str:
        lines = [
            f"{self.path}: {len(self.plots)} plot(s) linted, {len(self.findings)} finding(s)"
        ]
        if self.error:
            lines.append(f"  could not run: {self.error}")
        if self.empty_figures:
            lines.append(
                f"  {self.empty_figures} empty figure(s) skipped (no data was plotted)"
            )
        if self.failed_cells:
            first = self.failed_cells[0]
            lines.append(
                f"  {len(self.failed_cells)} cell(s) failed and their plots were skipped "
                f"(first: cell {first[0]}, {first[1]})"
            )
        for p in self.plots:
            for f in p.report.findings:
                lines.append(f"  cell {p.cell}: {f.rule_id} {f.severity}: {f.message}")
        return "\n".join(lines)


def _finding_from_dict(f: dict) -> Finding:
    return Finding(
        rule_id=f["rule_id"],
        title=f["title"],
        severity=Severity.parse(f["severity"]),
        message=f["message"],
        fix=f.get("fix", ""),
        why=f.get("why", ""),
        source=f.get("source", ""),
        heuristic=f.get("heuristic", False),
        panel=f.get("panel"),
        details=f.get("details", {}),
    )


def _report_from_dict(d: dict) -> Report:
    findings = [_finding_from_dict(f) for f in d.get("findings", [])]
    audit = None
    if d.get("audit"):
        from .audit import Audit

        audit = Audit.from_dict(d["audit"])
    return Report(
        audit=audit,
        findings=findings,
        source=d.get("source", ""),
        internal_errors=d.get("internal_errors", []),
        image=d.get("image"),
        alt_text=d.get("alt_text", ""),
        empty=d.get("empty", False),
    )


def check_notebook(
    path: str | Path,
    *,
    timeout: int = 900,
    cell_timeout: int = 120,
    kernel_name: str = "python3",
    save_images_to: str | Path | None = None,
    audit: bool = False,
) -> NotebookReport:
    """Run ``path`` in a fresh kernel and lint every plot it draws.

    With ``save_images_to``, it saves a PNG of each linted plot in that folder. The
    plot's report records the path (``report.image``). With ``audit=True``, each plot
    also gets a Chartability audit (``result.plots[i].audit``).
    """
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellTimeoutError, DeadKernelError
    from nbformat import NotebookNode

    path = Path(path)
    result = NotebookReport(path=str(path))
    try:
        nb: NotebookNode = nbformat.read(path, as_version=4)  # pyrefly: ignore[bad-assignment]
    except (OSError, ValueError) as exc:
        result.error = f"unreadable notebook: {exc}"
        return result

    code_cells = [c for c in nb.cells if c.cell_type == "code"]
    result.code_cells = len(code_cells)
    for c in code_cells:
        c.outputs = []
    setup_code = _SETUP
    if audit:
        setup_code += "\n_plotnine_linter_jupyter._STATE['audit'] = True"
    if save_images_to:
        setup_code += f"\n_plotnine_linter_jupyter._STATE['save_dir'] = {str(Path(save_images_to).resolve())!r}"
    setup = nbformat.v4.new_code_cell(setup_code)
    nb.cells.insert(0, setup)

    client = NotebookClient(
        nb,
        timeout=cell_timeout,
        kernel_name=kernel_name,
        allow_errors=True,
        resources={"metadata": {"path": str(path.parent.resolve())}},
    )
    import threading

    failure: dict = {}

    def run() -> None:
        try:
            client.execute()
        except Exception as exc:  # noqa: BLE001  # recorded below
            failure["exc"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        # out of time: stop the kernel; cells that already ran keep their outputs
        result.error = f"stopped after {timeout} s; plots from cells that finished were still linted"
        try:
            from jupyter_client.utils import run_sync

            if client.km is not None:
                # nbclient's kernel manager is async; its stubs say otherwise
                run_sync(client.km.shutdown_kernel)(now=True)  # pyrefly: ignore[bad-argument-type]
        except Exception:  # noqa: BLE001, S110  # best effort: the kernel may already be gone
            pass
        worker.join(10)
    elif "exc" in failure:
        exc = failure["exc"]
        if isinstance(exc, (CellTimeoutError, DeadKernelError)):
            result.error = (
                f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"
            )
        else:  # kernel failed to start, etc.
            result.error = f"{type(exc).__name__}: {exc}"

    n = 0
    for cell in nb.cells[1:]:
        if cell.cell_type != "code":
            continue
        n += 1
        for out in cell.get("outputs", []):
            if out.get("output_type") == "error":
                result.failed_cells.append(
                    (n, f"{out.get('ename')}: {str(out.get('evalue'))[:120]}")
                )
            data = out.get("data", {})
            if COLLECT_MIME in data:
                report = _report_from_dict(data[COLLECT_MIME])
                if report.empty:
                    result.empty_figures += 1  # e.g. plt.figure() before a cell failed
                else:
                    result.plots.append(PlotResult(cell=n, report=report))
    return result

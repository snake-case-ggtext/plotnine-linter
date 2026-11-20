"""Jupyter integration: lint every plot as it is displayed.

    %load_ext plotnine_linter

After that, each cell's plots are linted and any findings appear under the
cell's output. Control it with the ``%plotlint`` magic::

    %plotlint off            # pause
    %plotlint on             # resume
    %plotlint select=tier1,tier2,ST301
    %plotlint ignore=AX203
    %plotlint status
    %plotlint rules          # the rule catalog (also: %plotlint rules 1, %plotlint rules AX)
    %plotlint summary        # every plot linted so far in this notebook, with its findings
    %plotlint profile accessibility   # Chartability/WCAG rules at their published thresholds
    %plotlint audit          # Chartability audit of the last plot (also: %plotlint audit p --markdown)

Suppress a rule for one cell with a comment in that cell::

    # plotlint: ignore[AX201] months are ordinal
"""

from __future__ import annotations

import weakref
from typing import Any

_STATE: dict[str, Any] = {
    "enabled": True,
    "options": {},
    "pending": [],  # reports waiting to be shown after the cell output
    "linted": weakref.WeakSet(),
    "callbacks": [],
    "history": [],  # (cell number, report) for every plot linted this session
    "collect": False,  # set by `plotnine-linter check`: emit machine-readable reports
}

COLLECT_MIME = "application/vnd.plotnine-linter+json"


def _display(report) -> None:
    from IPython.display import display

    _STATE["history"].append((_STATE.get("exec_count"), report))
    if _STATE["collect"]:
        data = report.to_dict()
        if getattr(report, "audit", None) is not None:
            data["audit"] = report.audit.to_dict()
        display({COLLECT_MIME: data}, raw=True)
    elif report.findings or report.internal_errors:
        display(report)


def _lint_quietly(obj, source):
    from .api import lint
    from .session import Session

    session = _STATE.setdefault("session", Session())
    try:
        report = lint(obj, source=source, session=session, **_STATE["options"])
    except Exception as exc:  # noqa: BLE001  # never break a student's notebook
        from .findings import Report

        report = Report(
            internal_errors=[f"plotnine-linter could not lint this plot: {exc}"]
        )
    _STATE["last_plot"] = obj
    if _STATE.get("audit") and not report.empty:  # `plotnine-linter audit`
        try:
            from .audit import audit

            report.audit = audit(obj, session=session, source=source)
        except Exception as exc:  # noqa: BLE001  # the audit is extra; keep the lint report
            report.internal_errors.append(f"audit failed: {exc}")
    save_dir = _STATE.get("save_dir")
    if save_dir:
        _save_image(obj, report, save_dir)
    return report


def _save_image(obj, report, save_dir) -> None:
    """Used by `plotnine-linter check --save-images`: keep a PNG of each linted plot."""
    import os

    os.makedirs(save_dir, exist_ok=True)
    _STATE["saved"] = _STATE.get("saved", 0) + 1
    path = os.path.join(save_dir, f"plot{_STATE['saved']:03d}.png")
    try:
        from .describe.spec import is_ggplot

        if is_ggplot(obj):
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                obj.save(path, dpi=80, verbose=False)
        else:
            obj.savefig(path, dpi=80, bbox_inches="tight")  # as the notebook shows it
        report.image = path
    except Exception as exc:  # noqa: BLE001  # saving is best effort; the lint report still counts
        report.internal_errors.append(f"could not save the plot image: {exc}")


def _make_callbacks(ip):
    def pre_execute():
        _STATE["pending"] = []
        _STATE["cell"] = None

    def pre_run_cell(info):
        _STATE["cell"] = getattr(info, "raw_cell", None)
        _STATE["exec_count"] = getattr(ip, "execution_count", None)

    def before_flush():
        """Runs on post_execute *before* the inline backend closes figures."""
        if not _STATE["enabled"]:
            return
        try:
            from matplotlib._pylab_helpers import Gcf
        except ImportError:  # pragma: no cover
            return
        for manager in Gcf.get_all_fig_managers():
            fig = manager.canvas.figure
            if fig in _STATE["linted"] or getattr(fig, "_plotnine_linter_skip", False):
                continue
            _STATE["linted"].add(fig)
            _STATE["pending"].append(_lint_quietly(fig, _STATE.get("cell")))

    def post_run_cell(result):
        if not _STATE["enabled"]:
            return
        try:
            from .describe.spec import is_ggplot

            value = getattr(result, "result", None)
            if value is not None and is_ggplot(value):
                _STATE["pending"].append(_lint_quietly(value, _STATE.get("cell")))
        finally:
            for report in _STATE["pending"]:
                _display(report)
            _STATE["pending"] = []

    return {
        "pre_execute": pre_execute,
        "pre_run_cell": pre_run_cell,
        "post_execute": before_flush,
        "post_run_cell": post_run_cell,
    }


def _patch_ggplot_show():
    """Lint plots shown with ``p.show()`` too (not just a cell's last expression)."""
    try:
        from plotnine import ggplot
    except ImportError:
        return
    if getattr(ggplot.show, "_plotnine_linter", False):
        return
    original = ggplot.show

    def show(self, *args, **kwargs):
        _STATE["in_ggplot_show"] = (
            True  # its matplotlib figure is linted from the spec instead
        )
        try:
            out = original(self, *args, **kwargs)
        finally:
            _STATE["in_ggplot_show"] = False
        if _STATE["enabled"] and _STATE.get("loaded"):
            _STATE["pending"].append(_lint_quietly(self, _STATE.get("cell")))
        return out

    show._plotnine_linter = True
    show._original = original
    ggplot.show = show


def _patch_pyplot_show(before_flush):
    """Lint figures shown with ``plt.show()``, which displays and closes them mid-cell."""
    import matplotlib.pyplot as plt

    if getattr(plt.show, "_plotnine_linter", False):
        return
    original = plt.show

    def show(*args, **kwargs):
        if _STATE.get("loaded") and not _STATE.get("in_ggplot_show"):
            before_flush()
        return original(*args, **kwargs)

    show._plotnine_linter = True
    show._original = original
    plt.show = show


def _parse_magic(line: str) -> str:
    line = line.strip()
    if line in ("", "status"):
        state = "on" if _STATE["enabled"] else "off"
        return f"plotnine-linter is {state}; options: {_STATE['options'] or 'defaults'}"
    if line == "on":
        _STATE["enabled"] = True
        return "plotnine-linter on"
    if line == "off":
        _STATE["enabled"] = False
        return "plotnine-linter off"
    if line == "reset":
        _STATE["options"] = {}
        _STATE["history"] = []
        if "session" in _STATE:
            _STATE["session"].reset()
        return "plotnine-linter reset: options, summary and cross-figure memory cleared"
    words = line.split()
    if words and words[0] == "profile":
        name = words[1] if len(words) > 1 else "none"
        from .config import profiles

        if name.lower() in ("none", "default"):
            _STATE["options"].pop("profile", None)
            return "plotnine-linter profile cleared"
        if name.lower() not in profiles():
            raise ValueError(
                f"unknown profile {name!r}; available: {', '.join(profiles())}"
            )
        _STATE["options"]["profile"] = name.lower()
        return f"plotnine-linter profile: {name.lower()} ({profiles()[name.lower()]['description']})"
    for part in words:
        if "=" not in part:
            raise ValueError(
                f"unrecognized option {part!r}; try on, off, status, reset, rules, summary, select=..., ignore=..."
            )
        key, value = part.split("=", 1)
        if key not in ("select", "ignore"):
            raise ValueError(f"unknown option {key!r}; use select= or ignore=")
        _STATE["options"][key] = [v for v in value.split(",") if v]
    return f"plotnine-linter options: {_STATE['options']}"


def load_ipython_extension(ip) -> None:
    if _STATE.get("loaded"):
        return
    callbacks = _make_callbacks(ip)
    for event, fn in callbacks.items():
        if event == "post_execute":
            # run before matplotlib-inline's flush_figures closes the figures
            ip.events.callbacks[event].insert(0, fn)
        else:
            ip.events.register(event, fn)
    _STATE["callbacks"] = list(callbacks.items())
    _patch_ggplot_show()
    _patch_pyplot_show(callbacks["post_execute"])
    from .describe.render import tag_histograms

    tag_histograms()

    def plotlint(line):
        words = line.split()
        if words and words[0] == "summary":
            from IPython.display import display

            display(summary())
            return
        if words and words[0] == "audit":
            _audit_magic(ip, words[1:])
            return
        if words and words[0] == "rules":
            from IPython.display import display

            from .catalog import show_rules

            arg = words[1] if len(words) > 1 else None
            display(show_rules(int(arg) if arg and arg.isdigit() else arg))
            return
        print(_parse_magic(line))

    ip.register_magic_function(plotlint, magic_kind="line", magic_name="plotlint")
    _STATE["loaded"] = True


def _audit_magic(ip, args: list[str]) -> None:
    from IPython.display import display

    from .audit import audit

    markdown = "--markdown" in args
    names = [a for a in args if not a.startswith("--")]
    if names:
        obj = eval(names[0], ip.user_ns)
    else:
        obj = _STATE.get("last_plot")
        if obj is None:
            print("No plot to audit yet: draw one first, or name it: %plotlint audit p")
            return
    result = audit(obj, session=_STATE.get("session"), source=_STATE.get("cell"))
    if markdown:
        print(result.to_markdown())
    else:
        display(result)


def unload_ipython_extension(ip) -> None:
    for event, fn in _STATE.get("callbacks", []):
        try:
            ip.events.unregister(event, fn)
        except ValueError:
            pass
    _STATE["callbacks"] = []
    _STATE["loaded"] = False
    try:
        from plotnine import ggplot

        if getattr(ggplot.show, "_plotnine_linter", False):
            ggplot.show = ggplot.show._original
    except ImportError:
        pass
    import matplotlib.pyplot as plt

    if getattr(plt.show, "_plotnine_linter", False):
        plt.show = plt.show._original


class NotebookSummary:
    """Every plot linted in this session, with its findings: `%plotlint summary`."""

    def __init__(self, history):
        self.history = list(history)

    def _rows(self):
        from collections import Counter

        rows = []
        for i, (cell, report) in enumerate(self.history, start=1):
            sev = Counter(str(f.severity) for f in report.findings)
            rows.append((i, cell, sev, [f.rule_id for f in report.findings], report))
        return rows

    def __str__(self) -> str:
        if not self.history:
            return "plotnine-linter: no plots linted yet in this session."
        lines = [f"plotnine-linter: {len(self.history)} plot(s) linted"]
        for i, cell, sev, ids, _ in self._rows():
            where = f"cell [{cell}]" if cell else "cell [?]"
            lines.append(
                f"  plot {i} ({where}): {', '.join(ids) if ids else 'no issues'}"
            )
        return "\n".join(lines)

    __repr__ = __str__

    def _repr_html_(self) -> str:
        import html
        from collections import Counter

        from ._html import FONT, MUTED, RULE_LINE, pill

        if not self.history:
            return f'<div style="{FONT}">No plots linted yet in this session.</div>'
        rows = self._rows()
        totals = Counter()
        rule_counts = Counter()
        for _, _, sev, ids, _ in rows:
            totals.update(sev)
            rule_counts.update(set(ids))
        clean = sum(1 for r in rows if not r[3])
        head = (
            f"<div style='margin-bottom:6px'><b>{len(rows)} plot(s) linted</b> &middot; "
            f"{pill(str(totals['error']), 'error')} error(s) &middot; "
            f"{pill(str(totals['warning']), 'warning')} warning(s) &middot; "
            f"{pill(str(totals['info']), 'info')} info &middot; "
            f"{pill(str(clean), 'ok')} clean</div>"
        )
        common = ""
        if rule_counts:
            items = ", ".join(
                f"<code>{r}</code> ({n})" for r, n in rule_counts.most_common(5)
            )
            common = (
                f"<div style='margin-bottom:6px;{MUTED}'>Most common: {items}</div>"
            )
        cell_style = f"padding:3px 8px;{RULE_LINE};text-align:left;vertical-align:top"
        body = []
        for i, cell, sev, ids, report in rows:
            msgs = "<br>".join(
                f"<code>{html.escape(f.rule_id)}</code> {html.escape(f.message)}"
                for f in report.findings
            ) or pill("no issues", "ok")
            body.append(
                f"<tr><td style='{cell_style}'>{i}</td><td style='{cell_style}'>[{cell or '?'}]</td>"
                f"<td style='{cell_style}'>{pill(str(sev['error']), 'error') if sev['error'] else ''}</td>"
                f"<td style='{cell_style}'>{pill(str(sev['warning']), 'warning') if sev['warning'] else ''}</td>"
                f"<td style='{cell_style}'>{msgs}</td></tr>"
            )
        table = (
            "<table style='border-collapse:collapse;font-size:12.5px;color:inherit;background:transparent'><thead><tr>"
            + "".join(
                f"<th style='{cell_style}'>{h}</th>"
                for h in ("Plot", "Cell", "Errors", "Warnings", "Findings")
            )
            + "</tr></thead><tbody>"
            + "".join(body)
            + "</tbody></table>"
        )
        return f'<div style="{FONT};max-width:900px">{head}{common}{table}</div>'


def summary() -> NotebookSummary:
    """All plots linted in this notebook session so far."""
    return NotebookSummary(_STATE["history"])

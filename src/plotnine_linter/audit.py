"""Chartability audit: every test that applies to a static chart, with a verdict.

    from plotnine_linter import audit
    a = audit(p)            # a plotnine plot, or a matplotlib Figure/Axes
    a                       # in a notebook: the checklist, with a status for every test
    print(a.to_markdown())  # paste into a markdown cell under the chart and answer it

``lint()`` reports only problems. ``audit()`` walks through Chartability's
tests (https://chartability.github.io/POUR-CAF/) and marks each one:

- **pass** / **fail**: decided by the linter's rules
- **partly checked**: the linter gathered evidence; the author answers a question
- **your call**: only the author can decide; the audit asks
- **n/a**: about interactive or web charts, not a static plot

In a notebook, ``%plotlint audit`` audits the last plot. On the command line,
``plotnine-linter audit project.ipynb`` audits every plot in a notebook, and
``plotnine-linter audit project.ipynb --check-answers`` reports checklist items
students left unanswered.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .findings import Finding, Severity

PASS, FAIL, PARTLY, ASK, NA = "pass", "fail", "partly", "ask", "na"
STATUS_LABEL = {
    PASS: "Pass",
    FAIL: "Fail",
    PARTLY: "Partly checked",
    ASK: "Your call",
    NA: "N/A",
}
_STATUS_PILL = {PASS: "ok", FAIL: "error", PARTLY: "warning", ASK: "info", NA: "off"}
_ORDER = {FAIL: 0, PARTLY: 1, ASK: 2, PASS: 3, NA: 4}
MARKER = "<!-- plotnine-linter audit"


@dataclass
class AuditItem:
    test: str
    principle: str
    critical: bool
    status: str
    evidence: str = ""
    question: str = ""  # what the author should answer or do (partly / ask / fail)
    rules: list[str] = field(default_factory=list)  # the linter rules behind this test
    findings: list[Finding] = field(default_factory=list)

    @property
    def needs_author(self) -> bool:
        return self.status in (FAIL, PARTLY, ASK)

    def to_dict(self) -> dict:
        return {
            "test": self.test,
            "principle": self.principle,
            "critical": self.critical,
            "status": self.status,
            "evidence": self.evidence,
            "question": self.question,
            "rules": list(self.rules),
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class Audit:
    items: list[AuditItem]
    alt_text: str = ""
    title: str = ""
    kind: str = ""  # e.g. "bar chart"
    source: str = ""
    table_rows: int | None = None  # rows in data_table(), if one could be built
    internal_errors: list[str] = field(default_factory=list)

    # ----- convenience -------------------------------------------------
    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, test: str) -> AuditItem:
        for item in self.items:
            if item.test.lower() == test.lower():
                return item
        raise KeyError(test)

    def by_status(self, status: str) -> list[AuditItem]:
        return [i for i in self.items if i.status == status]

    @property
    def counts(self) -> dict[str, int]:
        return {s: len(self.by_status(s)) for s in (PASS, FAIL, PARTLY, ASK, NA)}

    @property
    def to_answer(self) -> list[AuditItem]:
        """Items the author still has to fix or answer, worst first."""
        return sorted(
            (i for i in self.items if i.needs_author),
            key=lambda i: (_ORDER[i.status], not i.critical),
        )

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "kind": self.kind,
            "source": self.source,
            "alt_text": self.alt_text,
            "table_rows": self.table_rows,
            "counts": self.counts,
            "items": [i.to_dict() for i in self.items],
            "internal_errors": list(self.internal_errors),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Audit:
        from .notebook import _finding_from_dict

        items = [
            AuditItem(
                test=i["test"],
                principle=i["principle"],
                critical=i["critical"],
                status=i["status"],
                evidence=i.get("evidence", ""),
                question=i.get("question", ""),
                rules=i.get("rules", []),
                findings=[_finding_from_dict(f) for f in i.get("findings", [])],
            )
            for i in d.get("items", [])
        ]
        return cls(
            items=items,
            alt_text=d.get("alt_text", ""),
            title=d.get("title", ""),
            kind=d.get("kind", ""),
            source=d.get("source", ""),
            table_rows=d.get("table_rows"),
            internal_errors=d.get("internal_errors", []),
        )

    # ----- output ------------------------------------------------------
    def _headline(self) -> str:
        c = self.counts
        parts = [
            f"{c[s]} {STATUS_LABEL[s].lower()}"
            for s in (PASS, FAIL, PARTLY, ASK, NA)
            if c[s]
        ]
        return ", ".join(parts)

    def __str__(self) -> str:
        name = (
            f": {self.title}"
            if self.title
            else (f": untitled {self.kind}" if self.kind else "")
        )
        lines = [f"Chartability audit{name} ({self._headline()})"]
        for item in sorted(self.items, key=lambda i: _ORDER[i.status]):
            if item.status == NA:
                continue
            star = " *" if item.critical else ""
            lines.append(f"  [{STATUS_LABEL[item.status]}] {item.test}{star}")
            if item.evidence:
                lines.append(f"      {item.evidence}")
            for f in item.findings:
                lines.append(f"      {f.rule_id}: {f.message}")
                if f.fix:
                    lines.append(f"      fix: {f.fix}")
            if item.question and item.status != FAIL:
                lines.append(f"      -> {item.question}")
        lines.append(
            f"  ({self.counts[NA]} tests don't apply to a static chart; * = critical)"
        )
        return "\n".join(lines)

    __repr__ = __str__

    def to_markdown(self, heading_level: int = 4) -> str:
        """A checklist to paste into a markdown cell under the chart.

        Automatic passes are pre-checked. Everything else is an open box; questions get an
        ``Answer:`` line. The draft alt text is filled in for the author to edit.
        ``plotnine-linter audit --check-answers`` reads these checklists back.
        """
        h = "#" * heading_level
        name = self.title or (self.kind.capitalize() if self.kind else "chart")
        out = [
            f"{h} Accessibility checklist: {name}",
            f"{MARKER} v1 draft={_digest(self.alt_text)} -->",
            "",
        ]
        if self.alt_text:
            out += [
                "**Alt text** (a draft: edit it to say your takeaway):",
                "",
                f"> {self.alt_text}",
                "",
            ]
        for item in self.to_answer:
            label = f"**{item.test}**" + (" (critical)" if item.critical else "")
            if item.status == FAIL:
                details = (
                    " ".join(_finding_line(f) for f in item.findings) or item.evidence
                )
                out.append(f"- [ ] Fix: {label}. {details}")
            else:
                evidence = f" {item.evidence}" if item.evidence else ""
                out.append(f"- [ ] {label}.{evidence} {item.question}".rstrip())
                if not item.question.endswith("Then check this box."):
                    out.append("  - Answer: ")
        for item in self.by_status(PASS):
            out.append(
                f"- [x] {item.test} (checked automatically): {item.evidence}".rstrip(
                    ": "
                )
            )
        na = self.by_status(NA)
        if na:
            out += [
                "",
                f"<details><summary>{len(na)} tests don't apply to a static chart</summary>",
                "",
                "; ".join(i.test for i in na) + ".",
                "",
                "</details>",
            ]
        return "\n".join(out) + "\n"

    def _repr_html_(self) -> str:
        from ._html import FONT, MUTED, RULE_LINE, pill
        from .findings import _md_code

        name = (
            html.escape(self.title)
            if self.title
            else f"untitled {self.kind or 'chart'}"
        )
        pills = " ".join(
            pill(f"{n} {STATUS_LABEL[s].lower()}", _STATUS_PILL[s])
            for s, n in self.counts.items()
            if n
        )
        rows = []
        for item in sorted(
            self.items, key=lambda i: (_ORDER[i.status], not i.critical)
        ):
            if item.status == NA:
                continue
            crit = (
                f" <span style='{MUTED};font-size:11.5px'>critical</span>"
                if item.critical
                else ""
            )
            meta = f"<span style='{MUTED};font-size:11.5px'> · {item.principle}"
            meta += (
                (" · " + ", ".join(item.rules))
                if item.rules and item.status == FAIL
                else ""
            )
            meta += "</span>"
            body = []
            if item.status == FAIL and item.findings:
                for f in item.findings:
                    fix = f" <b>Fix:</b> {_md_code(f.fix)}" if f.fix else ""
                    body.append(
                        f"<div><code>{f.rule_id}</code> {_md_code(f.message)}{fix}</div>"
                    )
            elif item.evidence:
                body.append(f"<div style='{MUTED}'>{_md_code(item.evidence)}</div>")
            if item.question and item.status != FAIL:
                body.append(
                    "<div style='margin-top:3px;padding-left:8px;border-left:2px solid #175cd3'>"
                    f"{_md_code(item.question)}</div>"
                )
            rows.append(
                f"<div style='display:grid;grid-template-columns:110px 1fr;gap:10px;padding:7px 0;{RULE_LINE}'>"
                f"<div>{pill(STATUS_LABEL[item.status], _STATUS_PILL[item.status])}</div>"
                f"<div><b>{html.escape(item.test)}</b>{crit}{meta}{''.join(body)}</div></div>"
            )
        na = self.by_status(NA)
        na_html = (
            f"<details style='margin-top:6px'><summary style='cursor:pointer;{MUTED}'>{len(na)} tests don't apply "
            f"to a static chart</summary><div style='{MUTED}'>{html.escape('; '.join(i.test for i in na))}.</div>"
            "</details>"
        )
        alt = (
            f"<div style='margin:6px 0'><b>Draft alt text</b> <span style='{MUTED}'>(edit it to say your "
            f"takeaway)</span><div style='padding-left:8px;border-left:2px solid rgba(127,127,127,.4)'>"
            f"{html.escape(self.alt_text)}</div></div>"
            if self.alt_text
            else ""
        )
        tip = (
            f"<div style='{MUTED};margin-top:6px;font-size:12px'>Test names are Chartability's and name the "
            "problem to look for. To answer it in your notebook: "
            "<code>print(audit(p).to_markdown())</code> or <code>%plotlint audit --markdown</code>, "
            "then paste the checklist into a markdown cell.</div>"
        )
        return (
            f"<div style=\"{FONT};max-width:780px\"><div style='margin-bottom:6px'><b>Chartability audit</b> · "
            f"{name} &nbsp; {pills}</div>{alt}{''.join(rows)}{na_html}{tip}</div>"
        )


# ---------------------------------------------------------------------------
# Running the audit
# ---------------------------------------------------------------------------
def audit(
    obj: Any, *, session=None, config=None, source: str | None = None, suppress=None
) -> Audit:
    """Audit a plotnine plot or a matplotlib Figure/Axes against Chartability's tests.

    Rules run under the accessibility profile (marks 3:1, text at least 9 pt). Pass a
    :class:`~plotnine_linter.session.Session` to compare this chart with others (the
    "consistent and familiar" test); ``%plotlint audit`` does this for you.
    """
    from .config import load_config
    from .describe import describe

    cfg = (config or load_config()).merged(profile="accessibility", select=["a11y"])
    desc = describe(obj)
    desc.session = session
    try:
        return audit_description(desc, cfg, source=source, suppress=suppress)
    finally:
        if desc.source == "plotnine" and desc.render is not None:
            import matplotlib.pyplot as plt

            plt.close(desc.render.figure)


def audit_description(desc, cfg, *, source=None, suppress=None) -> Audit:
    from .api import lint_description
    from .registry import all_rules, load_catalog

    report = lint_description(desc, cfg, source=source, suppress=suppress)
    tests = load_catalog()["chartability"]["tests"]
    rules_for: dict[str, list] = {}
    for r in all_rules():
        for t in r.chartability:
            rules_for.setdefault(t, []).append(r)
    ctx = _Context(desc, report)
    items = []
    for t in tests:
        name, typ = t["name"], t["static"]
        item = AuditItem(
            test=name, principle=t["principle"], critical=t["critical"], status=NA
        )
        if typ == "na":
            item.evidence = t.get("na", "")
            items.append(item)
            continue
        rules = rules_for.get(name, [])
        item.rules = [r.id for r in rules]
        active = [r for r in rules if cfg.is_selected(r.id, r.tier)]
        found = [f for f in report.findings if f.rule_id in item.rules]
        suppressed = [
            (f, why) for f, why in report.suppressed if f.rule_id in item.rules
        ]
        if t.get("needs_session") and desc.session is None:
            item.evidence = "Needs the other charts in the notebook; use `%plotlint audit` or audit the notebook."
            items.append(item)
            continue
        hard = [f for f in found if f.severity >= Severity.WARNING]
        soft = [f for f in found if f.severity < Severity.WARNING]
        special = _SPECIAL.get(name)
        if hard:
            item.status, item.findings = FAIL, hard
        elif suppressed:
            item.status = PARTLY
            item.evidence = " ".join(
                f"{f.rule_id} is suppressed ({why or 'no reason given'}): {f.message}"
                for f, why in suppressed
            )
            item.question = "Check that the reason still holds for readers with low vision or color-vision deficiency."
        elif soft:  # heuristic findings: the linter isn't sure
            item.status = PARTLY
            item.evidence = " ".join(f"{f.rule_id}: {f.message}" for f in soft)
            item.question = (
                "The linter isn't sure about this one. Look at the chart and decide."
            )
        elif rules and not active:
            item.status = ASK
            item.evidence = (
                f"Not checked: {', '.join(item.rules)} turned off in your settings."
            )
            item.question = t.get("ask", "Check this yourself.")
        elif special is not None:
            special(item, t, ctx)
        elif typ in ("partly", "ask"):
            item.status = PARTLY if typ == "partly" else ASK
            item.question = t.get("ask", "")
        else:
            item.status, item.evidence = PASS, t.get("pass", "")
            if name in _PASS_EVIDENCE:
                item.evidence = _PASS_EVIDENCE[name](ctx) or item.evidence
        items.append(item)
    return Audit(
        items=items,
        alt_text=report.alt_text,
        title=ctx.title,
        kind=f_kind(ctx),
        source=desc.source,
        table_rows=None if ctx.table is None else len(ctx.table),
        internal_errors=report.internal_errors,
    )


class _Context:
    """What the per-test evidence functions share."""

    def __init__(self, desc, report):
        self.desc = desc
        self.report = report
        self.features = chart_features(desc)
        self.texts = chart_texts(desc)
        self.title = self.texts.get("title", "")
        try:
            self.table = _table(desc)
        except Exception:  # noqa: BLE001  # the table is optional evidence
            self.table = None
        from .readability import analyze

        self.reading = analyze(list(self.texts.values()))


# ----- per-test evidence ------------------------------------------------------
def _content_only_visual(item, t, ctx):
    item.status = PARTLY
    item.evidence = (
        "A draft alt text is filled in above." if ctx.report.alt_text else ""
    )
    item.question = t["ask"] + " Then check this box."


def _how_to_read(item, t, ctx):
    item.status = ASK
    nudges = []
    f = ctx.features
    if "boxplot" in f:
        nudges.append("say what the box, the middle line and the whiskers show")
    if "violin" in f:
        nudges.append("say that the width shows how many values fall there")
    if f & {"log_x", "log_y"}:
        axes = " and ".join(a[-1] for a in sorted(f & {"log_x", "log_y"}))
        nudges.append(f"say the {axes}-axis is on a log scale, so each step multiplies")
    if "heatmap" in f:
        nudges.append("say what the colors stand for and point to the color key")
    if "density" in f:
        nudges.append("say the curve shows where values are common, not counts")
    if "twin" in f:
        nudges.append("say which line goes with which y-axis")
    item.evidence = f"This chart is a {f_kind(ctx)}." if f_kind(ctx) else ""
    item.question = t["ask"] + (" Also " + "; ".join(nudges) + "." if nudges else "")


def _title(item, t, ctx):
    title = ctx.title
    if not title:
        item.status = FAIL
        item.evidence = "No title."
        return
    item.status = PARTLY
    caption = ctx.texts.get("subtitle") or ctx.texts.get("caption")
    item.evidence = f"Title: “{title}”." + (
        f" Caption: “{caption}”." if caption else " No subtitle or caption."
    )
    names_variables = re.search(
        r"\b(by|vs\.?|versus|over|across|against)\b|^(distribution|number|count|average|mean) of\b",
        title,
        re.IGNORECASE,
    )
    item.question = (
        "The title names what is plotted. Could it say what to notice instead?"
        if names_variables
        else t["ask"]
    )


def _reading_level(item, t, ctx):
    r = ctx.reading
    if r.scored and r.grade > 10:
        item.status = PARTLY
        long = f" Long words: {', '.join(r.long_words[:4])}." if r.long_words else ""
        item.evidence = (
            f"The chart's text reads at grade {r.grade:.0f} ({r.words} words).{long}"
        )
        item.question = t["ask"] + " Aim for grade 9 or below."
        return
    item.status = PASS
    item.evidence = (
        f"The chart's text reads at grade {r.grade:.0f}."
        if r.scored
        else f"Too little text to score ({r.words} word{'s' if r.words != 1 else ''})."
    )
    if r.long_words:
        item.status = PARTLY
        item.evidence += f" Long words: {', '.join(r.long_words[:4])}."
        item.question = "Is there a plainer word your readers would know?"


def _metrics(item, t, ctx):
    abbr = ctx.reading.abbreviations
    if abbr:
        item.status = PARTLY
        quoted = ", ".join(f"“{a}”" for a in abbr[:5])
        item.evidence = f"Abbreviations not defined on the chart: {quoted}."
        item.question = t["ask"]
    else:
        item.status, item.evidence = PASS, t["pass"]


def _uncertainty(item, t, ctx):
    marks = ctx.features & {"errorbar", "ribbon"}
    if not marks:
        item.status, item.evidence = PASS, "No uncertainty marks; nothing to explain."
        return
    what = {"errorbar": "error bars", "ribbon": "a confidence band"}
    item.status = PARTLY
    item.evidence = (
        "The chart draws " + " and ".join(what[m] for m in sorted(marks)) + "."
    )
    item.question = t["ask"]


def _table_item(item, t, ctx):
    item.status = ASK
    if ctx.table is not None:
        n = len(ctx.table)
        item.evidence = f"`data_table(p)` gives the {n:,} row{'s' if n != 1 else ''} behind the chart."
        if n > 50:
            item.evidence += " That's long; a summary table may serve readers better."
    else:
        item.evidence = "A table couldn't be built automatically."
    item.question = t["ask"]


def _features_described(item, t, ctx):
    item.status = PARTLY
    alt = ctx.report.alt_text or ""
    if re.search(r"Highest|lowest|relationship|Rises|Falls|flat|Most values", alt):
        item.evidence = "The draft alt text gives the extremes or the overall trend, not why they matter."
    else:
        item.evidence = "The draft alt text names only the chart type and variables."
    item.question = t["ask"]


def _extremes(item, t, ctx):
    found = _extreme_value(ctx.desc)
    if found is None:
        item.status, item.evidence = PASS, t["pass"]
        return
    item.status = PARTLY
    item.evidence = found
    item.question = t["ask"]


def _difficult(item, t, ctx):
    hard = {
        "pie": "Pie charts", "heatmap": "Heatmaps", "boxplot": "Box plots", "violin": "Violin plots",
        "density": "Density plots", "twin": "Charts with two y-axes", "polar": "Polar charts", "3d": "3D charts",
    }  # fmt: skip
    kinds = [hard[k] for k in hard if k in ctx.features]
    if not kinds:
        item.status = PASS
        item.evidence = (
            f"A familiar chart type ({f_kind(ctx)})." if f_kind(ctx) else t["pass"]
        )
        return
    item.status = PARTLY
    item.evidence = f"{kinds[0]} are hard for many readers."
    item.question = t["ask"]


def _smallest_text(ctx) -> str:
    sizes = (
        [t.fontsize for t in ctx.desc.render.texts if t.text.strip()]
        if ctx.desc.render
        else []
    )
    return (
        f"The smallest text is {min(sizes):.1f} pt (at least 9 pt is the target)."
        if sizes
        else ""
    )


_PASS_EVIDENCE = {"Small text size": _smallest_text}

_SPECIAL = {
    "Content is only visual": _content_only_visual,
    "No explanation for purpose or for how to read": _how_to_read,
    "No title, summary, or caption": _title,
    "Reading level inappropriate": _reading_level,
    "Metrics and variables are undefined": _metrics,
    "Statistical uncertainty isn't clearly communicated": _uncertainty,
    "No table": _table_item,
    "Visually apparent features and relationships are not described": _features_described,
    "Space does not handle extremes": _extremes,
    "Difficult chart type has no alternative": _difficult,
}


# ---------------------------------------------------------------------------
# What the chart contains
# ---------------------------------------------------------------------------
_KIND_NAMES = {
    "bar": "bar chart", "hist": "histogram", "scatter": "scatter plot", "line": "line chart", "pie": "pie chart",
    "heatmap": "heatmap", "boxplot": "box plot", "violin": "violin plot", "density": "density plot",
}  # fmt: skip


def f_kind(ctx) -> str:
    for k in (
        "boxplot",
        "violin",
        "heatmap",
        "pie",
        "density",
        "hist",
        "bar",
        "line",
        "scatter",
    ):
        if k in ctx.features:
            return _KIND_NAMES[k]
    return ""


def chart_features(desc) -> set[str]:
    """Chart types and marks that change what a reader needs to be told."""
    f: set[str] = set()
    spec, render = desc.spec, desc.render
    if spec is not None:
        from .rules.axes import _log_scale

        for layer in spec.layers:
            g = layer.geom
            if g in (
                "geom_errorbar",
                "geom_errorbarh",
                "geom_pointrange",
                "geom_linerange",
                "geom_crossbar",
            ):
                f.add("errorbar")
            if layer.stat == "stat_summary":
                f.add("errorbar")
            if g == "geom_ribbon" or (
                g == "geom_smooth" and layer.stat_params.get("se", True)
            ):
                f.add("ribbon")
            kind = {
                "geom_boxplot": "boxplot", "geom_violin": "violin", "geom_tile": "heatmap", "geom_raster": "heatmap",
                "geom_density": "density", "geom_density_2d": "density", "geom_histogram": "hist", "geom_col": "bar",
                "geom_bar": "bar", "geom_point": "scatter", "geom_jitter": "scatter", "geom_line": "line",
                "geom_path": "line",
            }.get(g)  # fmt: skip
            if kind:
                f.add(kind)
            if g == "geom_bar" and layer.stat == "stat_bin":
                f.add("hist")
        for aes in ("x", "y"):
            if _log_scale(spec.user_scale_for(aes)):
                f.add(f"log_{aes}")
        if spec.coord == "coord_polar":
            f.add("polar")
    if render is not None:
        for p in render.panels:
            if p.n_wedges:
                f.add("pie")
            if p.twin_of is not None:
                f.add("twin")
            if getattr(p, "is_3d", False):
                f.add("3d")
            if spec is None:
                if p.cmaps:
                    f.add("heatmap")
                bars = [s for s in p.series if s.kind == "bar"]
                if bars:
                    f.add("hist" if all(s.from_hist for s in bars) else "bar")
                if p.of_kind("line"):
                    f.add("line")
                if p.of_kind("scatter"):
                    f.add("scatter")
                if p.x.scale in ("log", "symlog"):
                    f.add("log_x")
                if p.y.scale in ("log", "symlog"):
                    f.add("log_y")
                if getattr(p.ax, "name", "") == "polar":
                    f.add("polar")
                for c in getattr(p.ax, "containers", []):
                    if type(c).__name__ == "ErrorbarContainer":
                        f.add("errorbar")
                for coll in p.ax.collections:
                    if type(coll).__name__ == "FillBetweenPolyCollection" or (
                        type(coll).__name__ == "PolyCollection" and p.of_kind("line")
                    ):
                        f.add("ribbon")
                if _mpl_boxplot(p):
                    f.add("boxplot")
    return f


def _mpl_boxplot(p) -> bool:
    """Box plots (matplotlib or seaborn): whisker and box segments, at most a few outlier points."""
    segments = [s for s in p.series if s.kind == "segment"]
    if not segments or p.of_kind("line"):
        return False
    if any(
        type(c).__name__ == "ErrorbarContainer" for c in getattr(p.ax, "containers", [])
    ):
        return False
    points = sum(len(s.x) for s in p.of_kind("scatter") if s.x is not None)
    if points > 2 * len(segments):  # a scatter plot, not outliers drawn by a box plot
        return False
    boxes = sum(type(a).__name__ == "PathPatch" for a in p.ax.patches)
    return boxes >= 1 or len(segments) >= 5


def chart_texts(desc) -> dict[str, str]:
    """Text the author wrote for the chart: titles, captions, axis and legend titles."""
    out: dict[str, str] = {}
    if desc.spec is not None:
        from .rules._util import looks_like_code

        labels = dict(desc.spec.final_labels)
        labels.update(desc.spec.user_labels)
        for key in (
            "title",
            "subtitle",
            "caption",
            "x",
            "y",
            "color",
            "colour",
            "fill",
            "size",
            "shape",
        ):
            v = labels.get(key)
            if v and str(v).strip() and not looks_like_code(str(v)):
                out.setdefault(
                    "colour" if key == "color" else key, " ".join(str(v).split())
                )
        return out
    render = desc.render
    fig = render.figure
    sup = getattr(fig, "_suptitle", None)
    if sup is not None and sup.get_text().strip():
        out["title"] = " ".join(sup.get_text().split())
    for p in render.panels:
        t = p.ax.get_title().strip()
        if t:
            out.setdefault("title", " ".join(t.split()))
            if out["title"] != t:
                out[f"panel {p.index + 1} title"] = t
        if p.x.label:
            out.setdefault("x", p.x.label)
        if p.y.label:
            out.setdefault("y", p.y.label)
        if p.legend_title:
            out.setdefault("legend", p.legend_title)
    return out


def _extreme_value(desc) -> str | None:
    """A sentence naming one value that squashes the rest of the chart, or None."""
    if desc.spec is not None:
        from .rules.axes import _log_scale

        if _log_scale(desc.spec.user_scale_for("y")):
            return None
    for p in desc.render.panels:
        if p.y.scale != "linear":
            continue
        bars = [
            s
            for s in p.series
            if s.kind == "bar" and not s.from_hist and s.heights is not None
        ]
        if bars:
            h = np.concatenate([np.abs(np.asarray(s.heights, float)) for s in bars])
            h = h[np.isfinite(h) & (h > 0)]
            if len(h) >= 4:
                med = float(np.median(h))
                ratio = float(h.max()) / med if med > 0 else 0
                if ratio >= 10:
                    return f"The largest bar is {ratio:.0f}× the median bar, so the smaller bars are hard to compare."
            continue
        ys = [
            s.y for s in p.series if s.kind in ("scatter", "line") and s.y is not None
        ]
        if ys:
            y = np.concatenate([np.asarray(v, float) for v in ys])
            y = y[np.isfinite(y)]
            if len(y) >= 10:
                lo, hi = np.percentile(y, [5, 95])
                core = hi - lo
                span = float(y.max() - y.min())
                if core > 0 and span / core >= 10:
                    return f"A few extreme values stretch the y-axis to {span / core:.0f}× the range where most values are."
    return None


# ---------------------------------------------------------------------------
# The data behind the chart
# ---------------------------------------------------------------------------
def data_table(obj: Any) -> pd.DataFrame:
    """The data behind a chart, as a DataFrame you can show under it.

    For a plotnine plot with computed statistics (histograms, counts, box plots), the
    computed values; otherwise the plotted columns, named by their axis labels.
    """
    from .describe import describe

    desc = describe(obj)
    try:
        table = _table(desc)
    finally:
        if desc.source == "plotnine" and desc.render is not None:
            import matplotlib.pyplot as plt

            plt.close(desc.render.figure)
    if table is None:
        raise ValueError("couldn't find the data behind this chart")
    return table


_AES_ORDER = (
    "x",
    "y",
    "ymin",
    "ymax",
    "xmin",
    "xmax",
    "color",
    "colour",
    "fill",
    "size",
    "shape",
    "label",
)
_STAT_COLUMNS = (
    "x",
    "xmin",
    "xmax",
    "count",
    "density",
    "y",
    "ymin",
    "lower",
    "middle",
    "upper",
    "ymax",
)


def _table(desc) -> pd.DataFrame | None:
    if desc.spec is not None:
        return _plotnine_table(desc)
    return _matplotlib_table(desc)


def _plotnine_table(desc) -> pd.DataFrame | None:
    from .describe.model import PROBE_ERRORS, scale_categories

    spec = desc.spec
    labels = spec.final_labels
    skip = {
        "geom_text",
        "geom_label",
        "geom_hline",
        "geom_vline",
        "geom_abline",
        "geom_smooth",
        "geom_errorbar",
    }
    layers = [l for l in spec.layers if l.geom not in skip] or spec.layers
    if not layers:
        return None
    layer = layers[0]
    if layer.stat == "stat_identity" and layer.raw_data is not None:
        from .rules._util import base_var

        cols, names = [], {}
        for aes in _AES_ORDER:
            expr = layer.mapping.get(aes)
            if isinstance(expr, str) and expr not in layer.raw_data.columns:
                expr = base_var(expr)  # reorder(region, income) -> region
            if (
                isinstance(expr, str)
                and expr in layer.raw_data.columns
                and expr not in cols
            ):
                cols.append(expr)
                label = labels.get(aes)
                if label and label != expr:
                    names[expr] = " ".join(str(label).split())
        if not cols:
            return None
        table = layer.raw_data[cols].rename(columns=names)
        return table.reset_index(drop=True)
    data = layer.built_data
    if data is None:
        return None
    cols = [c for c in _STAT_COLUMNS if c in data.columns]
    table = data[cols].copy()
    if layer.stat == "stat_bin" and {"xmin", "xmax", "count"} <= set(table):
        label = " ".join(str(labels.get("x", "x")).split())
        table = table[["xmin", "xmax", "count"]].rename(
            columns={"xmin": f"{label} from", "xmax": f"{label} to"}
        )
        return table.reset_index(drop=True)
    for aes in ("x", "y"):
        if aes in table and spec.is_discrete(aes):
            try:
                cats = scale_categories(spec.scale_for(aes))
                table[aes] = [
                    cats[round(v) - 1] if 1 <= round(v) <= len(cats) else v
                    for v in table[aes]
                ]
            except PROBE_ERRORS:
                pass
    if "fill" in layer.mapping or "color" in layer.mapping:
        aes = "fill" if "fill" in layer.mapping else "color"
        try:
            cats = scale_categories(spec.scale_for(aes))
            if "group" in data and data["group"].nunique() == len(cats):
                order = sorted(data["group"].unique())
                lookup = {g: cats[i] for i, g in enumerate(order)}
                table.insert(
                    0,
                    " ".join(str(labels.get(aes, aes)).split()),
                    data["group"].map(lookup).values,
                )
        except PROBE_ERRORS:
            pass
    if "PANEL" in data and data["PANEL"].nunique() > 1:
        table.insert(0, "panel", data["PANEL"].astype(int).values)
    rename = {"x": labels.get("x", "x"), "y": labels.get("y", "y")}
    if spec.coord == "coord_flip":
        rename = {"x": labels.get("y", "x"), "y": labels.get("x", "y")}
    table = table.rename(
        columns={k: " ".join(str(v).split()) for k, v in rename.items() if k in table}
    )
    return table.reset_index(drop=True)


def _matplotlib_table(desc) -> pd.DataFrame | None:
    frames = []
    panels = [p for p in desc.render.panels if p.has_data]
    for p in panels:
        rows = []
        for s in p.series:
            name = s.label if s.label and not s.label.startswith("_") else ""
            if s.kind == "bar" and s.heights is not None:
                vertical = s.orientation == "vertical"
                ticks = p.ax.get_xticks() if vertical else p.ax.get_yticks()
                labs = p.ax.get_xticklabels() if vertical else p.ax.get_yticklabels()
                lookup = {
                    round(float(t), 6): lab.get_text() for t, lab in zip(ticks, labs)
                }
                cat_label = (p.x.label if vertical else p.y.label) or (
                    "bin" if s.from_hist else "category"
                )
                val_label = (p.y.label if vertical else p.x.label) or (
                    "count" if s.from_hist else "value"
                )
                for pos, h in zip(np.asarray(s.x, float), np.asarray(s.heights, float)):
                    cat = lookup.get(round(float(pos), 6)) or (
                        round(float(pos), 6) if s.from_hist else ""
                    )
                    rows.append(
                        {
                            "series": name,
                            cat_label: cat if cat != "" else pos,
                            val_label: h,
                        }
                    )
            elif s.kind in ("line", "scatter") and s.x is not None and s.y is not None:
                xl, yl = p.x.label or "x", p.y.label or "y"
                for xv, yv in zip(np.asarray(s.x), np.asarray(s.y)):
                    rows.append({"series": name, xl: xv, yl: yv})
        if not rows:
            continue
        df = pd.DataFrame(rows)
        if (
            df["series"].eq("").all()
            or df["series"].nunique() == 1
            and len(p.series) == 1
        ):
            df = df.drop(columns="series")
        if len(panels) > 1:
            df.insert(0, "panel", p.index + 1)
        frames.append(df)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Reading checklists back (for graders)
# ---------------------------------------------------------------------------
_ITEM = re.compile(r"^\s*- \[( |x|X)\] (.*)$")
_ANSWER = re.compile(r"^\s+- Answer:\s*(.*)$")
_DRAFT = re.compile(r"draft=([0-9a-f]{8})")


@dataclass
class ChecklistStatus:
    title: str
    open_items: list[str] = field(default_factory=list)  # unchecked boxes
    blank_answers: list[str] = field(
        default_factory=list
    )  # checked, but the Answer line is empty
    alt_text_unchanged: bool = False

    @property
    def complete(self) -> bool:
        return not (self.open_items or self.blank_answers or self.alt_text_unchanged)

    def __str__(self) -> str:
        if self.complete:
            return f"{self.title}: complete"
        lines = [
            f"{self.title}: {len(self.open_items) + len(self.blank_answers)} item(s) left"
        ]
        lines += [f"  open: {t}" for t in self.open_items]
        lines += [f"  checked but unanswered: {t}" for t in self.blank_answers]
        if self.alt_text_unchanged:
            lines.append("  alt text is still the draft")
        return "\n".join(lines)


def read_checklists(markdown: str) -> list[ChecklistStatus]:
    """Find audit checklists in markdown text and report what is still unanswered."""
    results: list[ChecklistStatus] = []
    lines = markdown.splitlines()
    current: ChecklistStatus | None = None
    last_item: tuple[str, bool] | None = None
    draft = None
    quote: list[str] = []

    for i, line in enumerate(lines):
        if MARKER in line:
            if current is not None:
                _finish(current, draft, quote)
                results.append(current)
            heading = next(
                (lines[j] for j in range(i - 1, -1, -1) if lines[j].startswith("#")),
                "checklist",
            )
            current = ChecklistStatus(
                title=heading.lstrip("#")
                .strip()
                .removeprefix("Accessibility checklist:")
                .strip()
            )
            m = _DRAFT.search(line)
            draft, quote = (m.group(1) if m else None), []
            continue
        if current is None:
            continue
        if line.startswith(">"):
            quote.append(line.lstrip("> ").rstrip())
            continue
        m = _ITEM.match(line)
        if m:
            text = re.sub(r"\*\*", "", m.group(2)).split(".")[0].removeprefix("Fix: ")
            text = text.replace(" (critical)", "").strip()
            checked = m.group(1).lower() == "x"
            if not checked:
                current.open_items.append(text)
            last_item = (text, checked)
            continue
        m = _ANSWER.match(line)
        if m and last_item is not None:
            text, checked = last_item
            if checked and not m.group(1).strip():
                current.blank_answers.append(text)
            last_item = None
    if current is not None:
        _finish(current, draft, quote)
        results.append(current)
    return results


def _finish(status: ChecklistStatus, draft: str | None, quote: list[str]) -> None:
    if draft and quote:
        status.alt_text_unchanged = _digest(" ".join(quote)) == draft


def _digest(text: str) -> str:
    return hashlib.sha1(" ".join(str(text).split()).encode("utf-8")).hexdigest()[:8]


def _finding_line(f: Finding) -> str:
    fix = f" Fix: {f.fix}" if f.fix else ""
    return f"{f.rule_id}: {f.message}{fix}"

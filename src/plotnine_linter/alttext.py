"""Draft alt text from the chart description.

The draft gives the chart type, the plotted variables and the most salient
numbers. The author adds the takeaway in their own words. ``lint()`` also puts
the draft on ``report.alt_text``.

    from plotnine_linter import alt_text
    alt_text(p)
"""

from __future__ import annotations

from typing import Any

import numpy as np

GEOM_KIND = {
    "geom_col": "Bar chart",
    "geom_bar": "Bar chart",
    "geom_histogram": "Histogram",
    "geom_point": "Scatter plot",
    "geom_jitter": "Strip plot",
    "geom_line": "Line chart",
    "geom_path": "Line chart",
    "geom_area": "Area chart",
    "geom_boxplot": "Box plot",
    "geom_violin": "Violin plot",
    "geom_density": "Density plot",
    "geom_tile": "Heatmap",
    "geom_raster": "Heatmap",
    "geom_smooth": "Trend line",
}


def _fmt(v: float) -> str:
    if v is None or not np.isfinite(v):
        return "n/a"
    a = abs(v)
    if a >= 1e6:
        return f"{v / 1e6:.3g} million"
    if a >= 100 or float(v).is_integer():
        return f"{v:,.0f}"
    return f"{v:.3g}"


def _clean(label: str) -> str:
    return " ".join(str(label).split())


def alt_text(obj: Any) -> str:
    """Return a draft alt text for a plotnine plot or matplotlib Figure/Axes."""
    from .describe import describe

    desc = describe(obj)
    try:
        return describe_alt_text(desc)
    finally:
        if desc.source == "plotnine":
            import matplotlib.pyplot as plt

            plt.close(desc.render.figure)


def describe_alt_text(desc) -> str:
    try:
        if desc.spec is not None:
            return _plotnine_alt(desc)
        return _matplotlib_alt(desc)
    except Exception:  # noqa: BLE001  # alt text is a convenience; never fail
        return "Chart."


# ---------------------------------------------------------------------------
def _plotnine_alt(desc) -> str:
    spec = desc.spec
    main = next(
        (l for l in spec.layers if l.geom in GEOM_KIND and l.geom != "geom_smooth"),
        spec.layers[0] if spec.layers else None,
    )
    kind = GEOM_KIND.get(main.geom, "Chart") if main else "Chart"
    labels = spec.final_labels
    x, y = labels.get("x"), labels.get("y")
    if kind == "Histogram" or (
        main and main.geom == "geom_bar" and "y" not in main.mapping
    ):
        what = f"of {_clean(x)}" if kind == "Histogram" else f"of counts by {_clean(x)}"
    elif x and y:
        what = (
            f"of {_clean(y)} by {_clean(x)}"
            if kind
            in ("Bar chart", "Box plot", "Violin plot", "Line chart", "Area chart")
            else f"of {_clean(y)} against {_clean(x)}"
        )
    else:
        what = ""
    parts = [f"{kind} {what}".strip()]
    color = labels.get("color") or labels.get("fill")
    color_aes = "color" if "color" in (main.mapping if main else {}) else "fill"
    if (
        main
        and color_aes in main.mapping
        and main.mapping.get(color_aes)
        not in (main.mapping.get("x"), main.mapping.get("y"))
    ):
        parts[0] += f", colored by {_clean(color)}"
    if spec.facet_type != "facet_null":
        n = len(desc.render.panels)
        parts[0] += f", in {n} panels"
    parts[0] += "."
    title = spec.user_labels.get("title")
    if title:
        parts.insert(0, f"{_clean(title)}.")
    detail = _plotnine_detail(desc, main, kind)
    if detail:
        parts.append(detail)
    return " ".join(parts)


def _category_names(desc, data_aes: str) -> list[str]:
    flipped = desc.spec.coord == "coord_flip"
    display = {"x": "y", "y": "x"}[data_aes] if flipped else data_aes
    panel = desc.render.panels[0]
    axis = panel.x if display == "x" else panel.y
    key = (lambda t: t.bbox.x0) if display == "x" else (lambda t: t.bbox.y0)
    return [t.text for t in sorted(axis.tick_labels, key=key)]


def _plotnine_detail(desc, main, kind) -> str:
    if main is None or main.built_data is None:
        return ""
    data = main.built_data
    if kind == "Bar chart" and "x" in data and desc.spec.is_discrete("x"):
        first = (
            data[data["PANEL"] == data["PANEL"].iloc[0]] if "PANEL" in data else data
        )
        value = "ymax" if "ymax" in first else "y"
        totals = first.groupby(first["x"].round())[value].max().sort_index()
        names = _category_names(desc, "x")
        if len(names) == len(totals) and len(totals) >= 2:
            hi, lo = int(np.argmax(totals.values)), int(np.argmin(totals.values))
            return f"Highest: {names[hi]} ({_fmt(totals.values[hi])}); lowest: {names[lo]} ({_fmt(totals.values[lo])})."
    if kind == "Scatter plot" and {"x", "y"} <= set(data.columns):
        return _scatter_sentence(data["x"].to_numpy(float), data["y"].to_numpy(float))
    if (
        kind == "Line chart"
        and {"x", "y"} <= set(data.columns)
        and not desc.spec.is_discrete("x")
    ):
        groups = data.groupby("group") if "group" in data else [(None, data)]
        groups = list(groups)
        if len(groups) == 1:
            g = groups[0][1].sort_values("x")
            return _trend_sentence(g["y"].iloc[0], g["y"].iloc[-1])
        return f"{len(groups)} lines."
    if kind == "Histogram" and "x" in data and "count" in data:
        peak = data.loc[data["count"].idxmax()]
        return (
            f"Most values fall near {_fmt(peak['x'])}; range about {_fmt(data['xmin'].min())} to {_fmt(data['xmax'].max())}."
            if {"xmin", "xmax"} <= set(data.columns)
            else ""
        )
    return ""


def _scatter_sentence(x: np.ndarray, y: np.ndarray) -> str:
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 3:
        return ""
    r = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 0 and np.std(y) > 0 else 0.0
    strength = (
        "no clear"
        if abs(r) < 0.2
        else "a weak"
        if abs(r) < 0.4
        else "a moderate"
        if abs(r) < 0.7
        else "a strong"
    )
    direction = "" if abs(r) < 0.2 else (" positive" if r > 0 else " negative")
    return f"{len(x):,} points show {strength}{direction} relationship (r = {r:.2f})."


def _trend_sentence(start: float, end: float) -> str:
    if not (np.isfinite(start) and np.isfinite(end)):
        return ""
    if np.isclose(start, end, rtol=0.02):
        return f"Roughly flat at about {_fmt(end)}."
    word = "Rises" if end > start else "Falls"
    return f"{word} from {_fmt(start)} to {_fmt(end)}."


# ---------------------------------------------------------------------------
def _matplotlib_alt(desc) -> str:
    sentences = []
    fig = desc.render.figure
    suptitle = getattr(fig, "_suptitle", None)
    if suptitle is not None and suptitle.get_text().strip():
        sentences.append(f"{_clean(suptitle.get_text())}.")
    panels = [p for p in desc.render.panels if p.twin_of is None]
    if len(panels) > 1:
        sentences.append(f"Figure with {len(panels)} panels.")
    for p in panels[:4]:
        sentences.append(_panel_sentence(p, numbered=len(panels) > 1))
    return " ".join(s for s in sentences if s)


def _panel_sentence(p, numbered: bool) -> str:
    xl, yl = _clean(p.x.label), _clean(p.y.label)
    bars = [s for s in p.series if s.kind == "bar"]
    lines = p.of_kind("line")
    scatters = p.of_kind("scatter")
    if p.n_wedges:
        kind, what = "Pie chart", f"with {p.n_wedges} slices"
    elif bars and all(s.from_hist for s in bars):
        kind, what = "Histogram", f"of {xl}" if xl else ""
    elif bars:
        kind = "Bar chart"
        cat_axis, val_axis = (
            (p.x, p.y) if bars[0].orientation == "vertical" else (p.y, p.x)
        )
        what = (
            f"of {_clean(val_axis.label)} by {_clean(cat_axis.label)}"
            if val_axis.label and cat_axis.label
            else ""
        )
    elif lines:
        kind, what = "Line chart", f"of {yl} over {xl}" if xl and yl else ""
    elif scatters:
        kind, what = "Scatter plot", f"of {yl} against {xl}" if xl and yl else ""
    elif p.cmaps:
        kind, what = "Heatmap", ""
    else:
        kind, what = "Chart", ""
    title = _clean(p.ax.get_title())
    head = f"{kind} {what}".strip()
    if title:
        head = f"{title}: {head[0].lower() + head[1:]}"
    if numbered:
        head = f"Panel {p.index + 1}: {head}"
    detail = ""
    if bars and not bars[0].from_hist and len(bars) == 1:
        s = bars[0]
        ticks = {
            round(float(t), 6): lab.get_text()
            for t, lab in zip(
                axis_ticks(p, s.orientation),
                (
                    p.ax.get_xticklabels()
                    if s.orientation == "vertical"
                    else p.ax.get_yticklabels()
                ),
            )
        }
        heights = np.asarray(s.heights, dtype=float)
        if len(heights) >= 2:
            hi, lo = int(np.argmax(heights)), int(np.argmin(heights))
            name = lambda i: ticks.get(round(float(s.x[i]), 6), "")
            if name(hi) and name(lo):
                detail = f" Highest: {name(hi)} ({_fmt(heights[hi])}); lowest: {name(lo)} ({_fmt(heights[lo])})."
    elif scatters and not lines and scatters[0].x is not None:
        detail = " " + _scatter_sentence(
            np.concatenate([s.x for s in scatters]),
            np.concatenate([s.y for s in scatters]),
        )
    elif lines:
        if len(lines) == 1 and lines[0].x is not None:
            s = lines[0]
            order = np.argsort(s.x)
            detail = " " + _trend_sentence(s.y[order][0], s.y[order][-1])
        else:
            detail = (
                f" {len(lines)} lines"
                + (f" ({', '.join(p.legend_labels[:5])})" if p.legend_labels else "")
                + "."
            )
    return (head + "." + detail).strip()


def axis_ticks(p, orientation):
    return p.ax.get_xticks() if orientation == "vertical" else p.ax.get_yticks()

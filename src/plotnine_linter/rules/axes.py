"""AX: axes and scales."""

from __future__ import annotations

import re

import numpy as np

from ..describe.model import PROBE_ERRORS, scale_categories
from ..registry import Hit, rule
from ._util import (
    is_unordered_column,
    monotone,
    natural_order,
    ordinal_like,
    plural,
    quote,
)

BAR_GEOMS = {"geom_bar", "geom_col", "geom_area", "geom_histogram"}


def _log_scale(scale) -> bool:
    if scale is None:
        return False
    trans = getattr(scale, "trans", None)
    name = (
        trans
        if isinstance(trans, str)
        else getattr(trans, "__name__", type(trans).__name__)
    )
    text = f"{name} {type(scale).__name__}".lower()
    if "symlog" in text or "pseudo" in text:
        return False  # defined at zero; nothing is dropped
    return "log" in text


# ---------------------------------------------------------------- AX101
@rule("AX101")
def ax101(desc, cfg):
    if desc.spec is not None:
        spec = desc.spec
        if _log_scale(spec.user_scale_for("y")):
            return
        geoms = [l.geom for l in spec.layers if l.geom in BAR_GEOMS]
        if not geoms:
            return
        for i, ranges in enumerate(spec.panel_ranges):
            rng = ranges.get("y")
            if rng and (min(rng) > 0 or max(rng) < 0):
                yield Hit(
                    f"`{geoms[0]}` draws bars from zero, but the value axis shows "
                    f"{min(rng):.3g} to {max(rng):.3g}, so bar lengths are not proportional.",
                    fix="Drop `ylim()`, `coord_cartesian(ylim=...)` or the scale `limits=` so the bars "
                    "start at zero; if the zoom matters, use `geom_point()` or `geom_line()`.",
                    panel=i,
                )
                return
        return

    for panel in desc.render.panels:
        for s in panel.of_kind("bar"):
            axis = panel.y if s.orientation == "vertical" else panel.x
            if axis.scale != "linear" or axis.limits is None:
                continue
            lo, hi = sorted(axis.limits)
            base = 0.0
            span = hi - lo
            if not (
                lo - 1e-9 * max(1, abs(span)) <= base <= hi + 1e-9 * max(1, abs(span))
            ):
                which = "y" if s.orientation == "vertical" else "x"
                yield Hit(
                    f"Bars start at zero, but the {which}-axis shows {lo:.3g} to {hi:.3g}, "
                    "so bar lengths are not proportional.",
                    fix=f"Remove `ax.set_{which}lim(...)` so the bars start at zero; if the zoom "
                    "matters, plot points or a line instead.",
                    source="render",
                    panel=panel.index,
                )
                return


# ---------------------------------------------------------------- AX102
@rule("AX102")
def ax102(desc, cfg):
    if desc.render is None:
        return
    for panel in desc.render.panels:
        if panel.twin_of is None:
            continue
        own = panel.y if panel.twin_shared == "x" else panel.x
        if (
            own.visible and own.tick_labels
        ):  # seaborn pairplot's hidden diagonal twins don't count
            yield Hit(
                "This figure overlays two axes with independent scales (`twinx`/`twiny`).",
                fix="Use `fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)`, or index both series "
                "(e.g. percent change from the first value) and plot them on one axis.",
                source="render",
                panel=panel.index,
            )
            return


# ---------------------------------------------------------------- AX103
@rule("AX103")
def ax103(desc, cfg):
    if desc.spec is not None:
        spec = desc.spec
        for aes in ("x", "y"):
            if not _log_scale(spec.user_scale_for(aes)):
                continue
            for layer in spec.layers:
                col = spec.column(layer, aes)
                if col is None or not np.issubdtype(np.asarray(col).dtype, np.number):
                    continue
                n_bad = int((col <= 0).sum())
                if n_bad:
                    yield Hit(
                        f"The {aes}-axis is log-scaled, but `{layer.mapping[aes]}` has "
                        f"{plural(n_bad, 'value')} at or below zero; they are not shown.",
                        fix=f"Use `scale_{aes}_continuous(trans='pseudo_log')`, or filter those rows and "
                        "say so in the caption.",
                    )
                    break
        return

    for panel in desc.render.panels:
        for which, axis in (("x", panel.x), ("y", panel.y)):
            if axis.scale != "log":
                continue
            n_bad = 0
            for s in panel.series:
                if s.kind == "bar":
                    along = "y" if s.orientation == "vertical" else "x"
                    vals = s.y if which == along else None
                    if vals is not None and s.from_hist:
                        vals = np.asarray(vals, dtype=float)[
                            np.asarray(s.heights) != 0
                        ]  # empty bins
                else:
                    vals = s.x if which == "x" else s.y
                if vals is not None:
                    v = np.asarray(vals, dtype=float)
                    n_bad += int(np.sum(v[~np.isnan(v)] <= 0))
            if n_bad:
                yield Hit(
                    f"The {which}-axis is log-scaled, but {plural(n_bad, 'plotted value')} are at or "
                    "below zero and are not shown.",
                    fix=f"Use `ax.set_{which}scale('symlog')`, or filter those values and say so.",
                    source="render",
                    panel=panel.index,
                )


# ---------------------------------------------------------------- AX201
@rule("AX201")
def ax201(desc, cfg):
    min_bars = int(cfg.t("min_bars_to_sort"))
    if desc.spec is not None:
        spec = desc.spec
        for layer in spec.layers:
            if layer.geom not in ("geom_col", "geom_bar") or layer.built_data is None:
                continue
            if not spec.is_discrete("x"):
                continue
            col = spec.column(layer, "x")
            if not is_unordered_column(col):
                continue  # expression (e.g. reorder()), ordered Categorical, or numbers
            levels = [str(v) for v in col.dropna().unique()]
            if ordinal_like(levels):
                continue
            data = layer.built_data
            if "x" not in data or "PANEL" not in data:
                continue
            first_panel = data[data["PANEL"] == data["PANEL"].iloc[0]]
            value = "ymax" if "ymax" in first_panel else "y"
            totals = (
                first_panel.groupby(first_panel["x"].round())[value].max().sort_index()
            )
            if len(totals) >= min_bars and not monotone(totals.values):
                xname = layer.mapping.get("x")
                yname = layer.mapping.get("y", "count")
                fix = (
                    f"`aes(x='reorder({xname}, {yname})')`, or make `{xname}` an ordered Categorical "
                    "sorted by value. Suppress if the order is meaningful."
                    if layer.geom == "geom_col"
                    else f"Make `{xname}` a Categorical ordered by frequency, e.g. "
                    f"`pd.Categorical(df['{xname}'], categories=df['{xname}'].value_counts().index)`."
                )
                yield Hit(
                    f"The {len(totals)} bars for `{xname}` are in alphabetical order, not sorted by value.",
                    fix=fix,
                )
                return
        return

    for panel in desc.render.panels:
        bars = panel.of_kind("bar")
        if len(bars) != 1 or bars[0].from_hist:
            continue
        s = bars[0]
        axis = panel.x if s.orientation == "vertical" else panel.y
        if axis.kind != "discrete" or len(s.heights) < min_bars:
            continue
        labels = [t.text for t in axis.tick_labels]
        if ordinal_like(labels):
            continue
        order = np.argsort(s.x)
        if not monotone(np.asarray(s.heights)[order]):
            yield Hit(
                f"The {len(s.heights)} bars aren't sorted by value.",
                fix="Sort before plotting, e.g. `counts.sort_values().plot.barh()`; suppress if the "
                "order is meaningful.",
                source="render",
                panel=panel.index,
            )


# ---------------------------------------------------------------- AX202
def _is_rotated(angle: float) -> bool:
    a = ((angle + 180) % 360) - 180
    return abs(a) > 1


@rule("AX202")
def ax202(desc, cfg):
    if desc.render is None:
        return
    plotnine = desc.source == "plotnine"
    reported = set()
    for panel in desc.render.panels:
        for which, axis in (("x", panel.x), ("y", panel.y)):
            if (
                which in reported
                or not axis.tick_labels
                or axis.kind not in ("discrete", "datetime")
            ):
                continue
            rotated = [t for t in axis.tick_labels if _is_rotated(t.rotation)]
            if axis.kind == "datetime":
                if rotated:
                    reported.add(which)
                    yield Hit(
                        f"Date labels on the {which}-axis are rotated {rotated[0].rotation % 360:.0f}°.",
                        fix=(
                            "Keep time horizontal; use fewer breaks and a shorter format, e.g. "
                            "`scale_x_datetime(date_breaks='3 months', date_labels='%b %Y')`."
                            if plotnine
                            else "Keep time horizontal; use `ax.xaxis.set_major_formatter("
                            "mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))`."
                        ),
                        source="render",
                        panel=panel.index,
                    )
                continue
            other = panel.y if which == "x" else panel.x
            if other.kind == "discrete":
                continue  # both axes categorical (a heatmap): swapping axes doesn't help
            swap = (
                "`coord_flip()`"
                if plotnine
                else "a horizontal layout (`barh`, or swap x and y)"
            )
            if rotated:
                reported.add(which)
                yield Hit(
                    f"Category labels on the {which}-axis are rotated "
                    f"{rotated[0].rotation % 360:.0f}° (e.g. '{quote(rotated[0].text)}').",
                    fix=f"Swap the axes with {swap} so the labels read horizontally.",
                    source="render",
                    panel=panel.index,
                )


# ---------------------------------------------------------------- AX203
@rule("AX203")
def ax203(desc, cfg):
    spec = desc.spec
    if spec is None or spec.facet_type == "facet_null":
        return
    free = [a for a in ("x", "y") if spec.facet_free.get(a)]
    if free:
        mode = "free" if len(free) == 2 else f"free_{free[0]}"
        yield Hit(
            f"Facets use `scales='{mode}'`, so panels aren't on a common {' and '.join(free)} scale.",
            fix="Drop `scales=` to share axes, or note in the title or caption that each panel has "
            "its own scale.",
        )


# ---------------------------------------------------------------- AX204
@rule("AX204")
def ax204(desc, cfg):
    if desc.spec is not None:
        for layer in desc.spec.layers:
            if layer.stat != "stat_bin":
                continue
            p = layer.stat_params
            if (
                p.get("bins") is None
                and p.get("binwidth") is None
                and p.get("breaks") is None
            ):
                yield Hit(
                    f"`{layer.geom}` uses plotnine's automatic bins.",
                    fix="Set a meaningful width, e.g. `geom_histogram(binwidth=5)` for 5-year age bands.",
                )
                return
        return

    for panel in desc.render.panels:
        for s in panel.of_kind("bar"):
            if s.from_hist and len(s.heights) == 10:
                yield Hit(
                    "This histogram has 10 equal bins, matplotlib's default.",
                    fix="Pass bin edges with meaning, e.g. `ax.hist(x, bins=np.arange(0, 101, 5))`.",
                    source="render",
                    heuristic=True,
                    panel=panel.index,
                )
                return


# ---------------------------------------------------------------- AX205
@rule("AX205")
def ax205(desc, cfg):
    spec = desc.spec

    def categorical_fix(expr, natural):
        return f"`df['{expr}'] = pd.Categorical(df['{expr}'], categories={natural!r}, ordered=True)` before plotting."

    # legends (plotnine): the scale's categories in legend order
    if spec is not None:
        for aes in ("color", "fill"):
            if not spec.is_discrete(aes):
                continue
            try:
                shown = scale_categories(spec.scale_for(aes))
            except PROBE_ERRORS:
                continue
            natural = natural_order(shown)
            if (
                natural is not None
                and natural != shown
                and list(reversed(natural)) != shown
            ):
                expr = next(
                    (l.mapping[aes] for l in spec.layers if aes in l.mapping), aes
                )
                yield Hit(
                    f"The {aes} legend lists `{expr}` alphabetically ({', '.join(shown[:4])}…) instead of in "
                    f"its natural order ({', '.join(natural[:4])}…).",
                    fix=categorical_fix(expr, natural),
                )
                return

    # axes (both libraries): tick labels in display order
    flipped = spec is not None and spec.coord == "coord_flip"
    for panel in desc.render.panels:
        for which, axis in (("x", panel.x), ("y", panel.y)):
            if axis.kind != "discrete" or len(axis.tick_labels) < 2:
                continue
            key = (lambda t: t.bbox.x0) if which == "x" else (lambda t: -t.bbox.y0)
            shown = [t.text for t in sorted(axis.tick_labels, key=key)]
            natural = natural_order(shown)
            if natural is None or natural == shown or list(reversed(natural)) == shown:
                continue  # natural order either way round (Small to Large, or Large to Small)
            if spec is not None:
                data_aes = {"x": "y", "y": "x"}[which] if flipped else which
                expr = next(
                    (l.mapping[data_aes] for l in spec.layers if data_aes in l.mapping),
                    data_aes,
                )
                yield Hit(
                    f"`{expr}` is shown in alphabetical order ({', '.join(shown[:4])}…) instead of its "
                    f"natural order ({', '.join(natural[:4])}…).",
                    fix=categorical_fix(expr, natural),
                    panel=panel.index,
                )
            else:
                yield Hit(
                    f"Categories on the {which}-axis ({', '.join(shown[:4])}…) are out of their natural order.",
                    fix="Sort the data into natural order before plotting, e.g. with an ordered "
                    "`pd.Categorical` and `sort_values`.",
                    source="render",
                    panel=panel.index,
                )
            return


# ---------------------------------------------------------------- AX206
_LOG_LABEL = re.compile(
    r"\blog\s*\d*\b|\blog\s*\(|\bln\b|\bln\s*\(|log10|log_|_log\b", re.IGNORECASE
)


@rule("AX206")
def ax206(desc, cfg):
    if desc.render is None:
        return
    for panel in desc.render.panels:
        for which, axis in (("x", panel.x), ("y", panel.y)):
            if (
                axis.kind != "continuous"
                or axis.scale != "linear"
                or not _LOG_LABEL.search(axis.label)
            ):
                continue
            if re.search(r"log[ -]?scale|\(log\)", axis.label, re.IGNORECASE):
                continue  # the label says the axis itself is log-scaled
            if desc.spec is not None:
                flipped = desc.spec.coord == "coord_flip"
                data_aes = {"x": "y", "y": "x"}[which] if flipped else which
                if _log_scale(desc.spec.user_scale_for(data_aes)):
                    continue  # plotnine draws log scales on linear matplotlib axes
            fix = (
                f"Map the original column and add `scale_{which}_log10()`."
                if desc.source == "plotnine"
                else f"Plot the original values with `ax.set_{which}scale('log')`."
            )
            yield Hit(
                f"The {which}-axis shows log-transformed values ('{quote(axis.label, 40)}') on a linear scale.",
                fix=fix,
                source="render",
                heuristic=True,
                panel=panel.index,
            )
            return


# ---------------------------------------------------------------- AX207
def _numeric_ticks(axis) -> list[float]:
    out = []
    for t in axis.tick_labels:
        try:
            out.append(float(t.text.replace("−", "-").replace(",", "")))
        except ValueError:
            return []
    return out


def _whole(values) -> bool:
    """Values on a whole-number grid (years, counts of things): at least 4 distinct, all integers."""
    v = np.asarray(values, dtype=float)
    v = np.unique(v[np.isfinite(v)])
    return len(v) >= 4 and bool(np.allclose(v, np.round(v))) and np.ptp(v) <= 60


@rule("AX207")
def ax207(desc, cfg):
    if desc.render is None:
        return
    spec = desc.spec
    flipped = spec is not None and spec.coord == "coord_flip"
    for panel in desc.render.panels:
        # only the independent (horizontal) axis: years, rounds, weeks; fractional ticks on a
        # measured value axis are normal
        for which, axis in (("x", panel.x),):
            if axis.kind != "continuous" or axis.scale != "linear":
                continue
            ticks = _numeric_ticks(axis)
            if len(ticks) < 2 or all(float(t).is_integer() for t in ticks):
                continue
            if spec is not None:
                data_aes = {"x": "y", "y": "x"}[which] if flipped else which
                cols = [spec.column(l, data_aes) for l in spec.layers]
                cols = [
                    c
                    for c in cols
                    if c is not None and np.issubdtype(np.asarray(c).dtype, np.number)
                ]
                if not cols or not all(_whole(c) for c in cols):
                    continue
                if any(l.stat == "stat_bin" for l in spec.layers):
                    continue  # histograms bin the axis themselves
                fix = f"`scale_{data_aes}_continuous(breaks=range(start, stop + 1))`, or map a whole-number step."
            else:
                vals = [
                    s.x if which == "x" else s.y
                    for s in panel.series
                    if s.kind in ("line", "scatter")
                ]
                vals = [v for v in vals if v is not None]
                if not vals or not all(_whole(v) for v in vals):
                    continue
                fix = (
                    f"`from matplotlib.ticker import MaxNLocator`; "
                    f"`ax.{which}axis.set_major_locator(MaxNLocator(integer=True))`."
                )
            frac = next(t for t in ticks if not float(t).is_integer())
            yield Hit(
                f"The {which}-axis has a tick at {frac:g}, but the plotted values are whole numbers.",
                fix=fix,
                source="render",
                panel=panel.index,
            )
            return

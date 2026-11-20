"""LB: labels and text content."""

from __future__ import annotations

import re

import numpy as np

from ..registry import Hit, rule
from ._util import base_var, humanize, looks_like_code, quote

LEGEND_AES = ("color", "fill", "size", "shape", "alpha", "linetype")


# ---------------------------------------------------------------- LB101
@rule("LB101")
def lb101(desc, cfg):
    if desc.source != "matplotlib" or desc.render is None:
        return  # plotnine always labels axes; LB201 checks what it says
    for panel in desc.render.panels:
        if panel.axis_off or panel.is_3d or panel.n_wedges or not panel.series:
            continue
        if getattr(panel.ax, "name", "") == "polar":
            continue
        ax = panel.ax
        for which, axis in (("x", panel.x), ("y", panel.y)):
            if not axis.visible or axis.kind != "continuous" or not axis.tick_labels or axis.label.strip():
                continue
            group = ax.get_shared_x_axes() if which == "x" else ax.get_shared_y_axes()
            siblings = group.get_siblings(ax)
            if any((s.get_xlabel() if which == "x" else s.get_ylabel()).strip() for s in siblings):
                continue
            yield Hit(
                f"The {which}-axis shows numbers but has no label.",
                fix=f"`ax.set_{which}label('What is measured (units)')`",
                source="render",
                panel=panel.index,
            )


# ---------------------------------------------------------------- LB201
@rule("LB201")
def lb201(desc, cfg):
    if desc.spec is not None:
        spec = desc.spec
        has_legend = desc.render.has_legend if desc.render else True
        mapped: dict[str, str] = {}
        for layer in spec.layers:
            for aes, expr in layer.mapping.items():
                if aes in ("x", "y") or (aes in LEGEND_AES and layer.show_legend is not False):
                    mapped.setdefault(aes, expr)
        seen_labels = set()
        for aes in ("x", "y", *LEGEND_AES):
            if aes not in mapped or aes in spec.user_labels:
                continue
            if aes in LEGEND_AES and (not has_legend or spec.legend_position == "none"):
                continue
            label = spec.final_labels.get(aes, mapped[aes])
            if not looks_like_code(label) or (aes in LEGEND_AES and label in seen_labels):
                continue
            seen_labels.add(label)
            where = f"{aes}-axis" if aes in ("x", "y") else f"{aes} legend"
            numeric = aes in ("x", "y") and not spec.is_discrete(aes)
            yield Hit(
                f"The {where} is labeled `{label}`, the raw variable name.",
                fix=f"`+ labs({aes}='{humanize(label, add_units=numeric)}')`",
            )
        title = spec.user_labels.get("title")
        if looks_like_code(title):
            yield Hit(
                f"The title is `{title}`, which reads as code.",
                fix=f"`+ labs(title='{humanize(title)}')`, or better, a sentence stating the takeaway.",
            )
        yield from _strip_hits(desc, plotnine=True)
        return

    seen = set()
    for panel in desc.render.panels:
        checks = [
            ("x-axis", panel.x.label, "ax.set_xlabel", panel.x.kind == "continuous"),
            ("y-axis", panel.y.label, "ax.set_ylabel", panel.y.kind == "continuous"),
        ]
        if panel.legend_title:
            checks.append(("legend title", panel.legend_title, "ax.legend", False))
        for name, label, setter, numeric in checks:
            if looks_like_code(label) and (name, label) not in seen:
                seen.add((name, label))
                fix = (
                    f"`{setter}('{humanize(label, add_units=numeric)}')`"
                    if setter.startswith("ax.set")
                    else f"`ax.legend(title='{humanize(label)}')`"
                )
                yield Hit(
                    f"The {name} is labeled `{label}`, a raw variable name.",
                    fix=fix,
                    source="render",
                    panel=panel.index,
                )
        title = panel.ax.get_title()
        if looks_like_code(title) and ("title", title) not in seen:
            seen.add(("title", title))
            yield Hit(
                f"The panel title is `{title}`, which reads as code.",
                fix=f"`ax.set_title('{humanize(title)}')`, or better, a sentence stating the takeaway.",
                source="render",
                panel=panel.index,
            )
        code_entries = [l for l in panel.legend_labels if not l.startswith("_") and looks_like_code(l)]
        if code_entries and ("legend", code_entries[0]) not in seen:
            seen.add(("legend", code_entries[0]))
            yield Hit(
                f"Legend entries are raw variable names (e.g. `{code_entries[0]}`).",
                fix="Pass `label='...'` to each plot call, or rename columns before `df.plot()`, e.g. "
                "`df.rename(columns={...})`.",
                source="render",
                panel=panel.index,
            )


def _strip_hits(desc, plotnine: bool):
    """Facet strip labels that are raw codes, e.g. `non_profit` or `drv_f`."""
    if desc.render is None:
        return
    strips = sorted({t.text for t in desc.render.texts if t.role == "strip"})
    coded = [s for s in strips if looks_like_code(s)]
    if strips and len(coded) * 2 >= len(strips):
        facet = ""
        spec = desc.spec
        if spec is not None:
            facet = f" (`{type(spec.plot.facet).__name__}`)"
        yield Hit(
            f"Facet labels show raw values such as `{coded[0]}`{facet}.",
            fix="Recode the values to readable text before plotting, e.g. "
            "`df['col'].map({'non_profit': 'Non-profit', ...})`, or use a labeller.",
            source="render",
        )


# ---------------------------------------------------------------- LB301
_UNIT_HINT = re.compile(
    r"[(\[]|%|\$|€|£|°|#|\bper\b|/|\b(percent|percentage|pct|dollars?|cents?|usd|eur|kg|mg|lb|lbs|km|cm|mm|mi|ft|sec|ms|min|hr|hrs|"
    r"hours?|minutes?|seconds?|days?|weeks?|months?|years?|yrs?|ppm|mph|kph|kwh|°c|°f)\b",
    re.I,
)
_UNITLESS = re.compile(
    r"\b(count|counts|number|n|total|frequency|freq|rate|rates|gpa|coefficient|correlation|latitude|longitude|"
    r"lat|lon|hdi|sentiment|normalized|standardized|z|"
    r"rank|ranking|score|scores|index|ratio|proportion|"
    r"fraction|probability|density|z|z-score|share|percentile|quantile|rating|level|"
    r"pc\d|pc|component|dimension|umap|tsne|t-sne|x|y)\b",
    re.I,
)


@rule("LB301")
def lb301(desc, cfg):
    if desc.render is None:
        return
    reported = set()
    for panel in desc.render.panels:
        for which, axis in (("x", panel.x), ("y", panel.y)):
            label = axis.label.strip()
            if which in reported or axis.kind != "continuous" or not label or looks_like_code(label):
                continue
            if _UNIT_HINT.search(label) or _UNITLESS.search(label):
                continue
            reported.add(which)
            setter = f"labs({which}='{label} (units)')" if desc.source == "plotnine" else f"ax.set_{which}label('{label} (units)')"
            yield Hit(
                f"The {which}-axis label '{quote(label, 40)}' doesn't mention units.",
                fix=f"`{setter}`, if the measure has units.",
                source="render",
                heuristic=True,
                panel=panel.index,
            )


# ---------------------------------------------------------------- LB203
@rule("LB203")
def lb203(desc, cfg):
    if desc.spec is not None:
        spec = desc.spec
        if desc.render is not None and not desc.render.has_legend:
            return
        if spec.legend_position == "none":
            return
        for layer in spec.layers:
            if layer.show_legend is False:
                continue
            for aes in ("fill", "color"):
                expr = layer.mapping.get(aes)
                for axis in ("x", "y"):
                    if expr is not None and base_var(expr) == base_var(layer.mapping.get(axis)):
                        yield Hit(
                            f"`{expr}` is mapped to both {axis} and {aes}, so the legend repeats the {axis}-axis.",
                            fix=f"Drop `{aes}='{expr}'` and use one color (the axis already names each "
                            "category); save color for another variable or a highlight.",
                        )
                        return
        return

    for panel in desc.render.panels:
        if panel.legend is None:
            continue
        data_series = [s for s in panel.series if s.kind in ("line", "scatter", "bar")]
        if len(panel.legend_labels) == 1 and len(data_series) == 1:
            yield Hit(
                f"The legend has a single entry ('{quote(panel.legend_labels[0])}') for the only series.",
                fix="Remove it (`legend=False` in `df.plot()` / seaborn, or `ax.get_legend().remove()`) and let the "
                "axis label or title say what is plotted.",
                source="render",
                panel=panel.index,
            )
            continue
        if len(panel.legend_labels) < 2:
            continue
        for axis in (panel.x, panel.y):
            ticks = {t.text.strip() for t in axis.tick_labels}
            if axis.kind == "discrete" and set(l.strip() for l in panel.legend_labels) <= ticks:
                yield Hit(
                    "The legend lists the same categories as the axis.",
                    fix="Use one color and drop the legend (seaborn: remove `hue=`, or pass `color=`); the axis "
                    "already names each category.",
                    source="render",
                    panel=panel.index,
                )
                break


# ---------------------------------------------------------------- LB205
_PERCENT = re.compile(r"%|\bpercent(age)?s?\b|\bpct\b", re.I)
_PROPORTION = re.compile(r"\b(proportion|fraction|probability|density|share)\b", re.I)


def _tick_values(axis) -> list[float]:
    vals = []
    for t in axis.tick_labels:
        try:
            vals.append(float(t.text.replace("−", "-").replace(",", "")))
        except ValueError:
            pass
    return vals


@rule("LB205")
def lb205(desc, cfg):
    if desc.render is None:
        return
    for panel in desc.render.panels:
        for which, axis in (("x", panel.x), ("y", panel.y)):
            label = axis.label.strip()
            if axis.kind != "continuous" or not label:
                continue
            ticks = _tick_values(axis)
            if len(ticks) < 2:
                continue
            if _PERCENT.search(label) and max(ticks) <= 1.0 and min(ticks) >= -1.0:
                yield Hit(
                    f"The {which}-axis label says percent ('{quote(label, 40)}'), but the ticks run "
                    f"{min(ticks):g} to {max(ticks):g}, which look like fractions.",
                    fix="Multiply by 100, or format ticks as percents (`labels=percent_format()` / "
                    "`ax.yaxis.set_major_formatter(PercentFormatter(1.0))`).",
                    source="render",
                    heuristic=True,
                    panel=panel.index,
                )
                return
            bars = [s for s in panel.of_kind("bar") if s.from_hist]
            heights = np.concatenate([np.asarray(s.heights, float) for s in bars]) if bars else np.array([])
            counts_like = heights.size and np.allclose(heights, np.round(heights)) and heights.max() > 1
            if which == "y" and _PROPORTION.search(label) and counts_like:
                yield Hit(
                    f"The y-axis says '{quote(label, 40)}', but the bars are whole-number counts.",
                    fix="Pass `density=True` (or `stat='density'` in seaborn) to plot a density, or label the axis 'Count'.",
                    source="render",
                    heuristic=True,
                    panel=panel.index,
                )
                return


# ---------------------------------------------------------------- LB206
@rule("LB206")
def lb206(desc, cfg):
    if desc.render is None:
        return
    for panel in desc.render.panels:
        for which in ("x", "y"):
            axis = panel.ax.xaxis if which == "x" else panel.ax.yaxis
            text = axis.get_offset_text()
            if text.get_visible() and text.get_text().strip():
                yield Hit(
                    f"The {which}-axis ticks are scaled by an easy-to-miss offset '{text.get_text().strip()}'.",
                    fix=f"Divide the values (e.g. by 1e6) and put the unit in the label: "
                    f"`ax.set_{which}label('Revenue (millions USD)')`; or `ax.ticklabel_format(style='plain', axis='{which}')`.",
                    source="render",
                    panel=panel.index,
                )
                return

"""MK: marks and geoms."""

from __future__ import annotations

import numpy as np

from ..registry import Hit, rule
from ._util import is_unordered_column, ordinal_like

UNCERTAINTY_GEOMS = {
    "geom_errorbar",
    "geom_linerange",
    "geom_pointrange",
    "geom_crossbar",
    "geom_point",
    "geom_jitter",
    "geom_boxplot",
    "geom_violin",
    "geom_sina",
    "geom_dotplot",
}


# ---------------------------------------------------------------- MK101
@rule("MK101")
def mk101(desc, cfg):
    plotnine = desc.source == "plotnine"
    if desc.spec is not None:
        spec = desc.spec
        per_cat = int(cfg.t("discrete_points_per_category"))
        for layer in spec.layers:
            if layer.geom != "geom_point" or layer.position != "position_identity":
                continue
            data = layer.built_data
            if data is None:
                continue
            for aes in ("x", "y"):
                if spec.is_discrete(aes) and aes in data:
                    counts = (
                        data.groupby(["PANEL", aes]).size()
                        if "PANEL" in data
                        else data.groupby(aes).size()
                    )
                    if len(counts) and counts.max() >= per_cat:
                        yield Hit(
                            f"`geom_point` stacks up to {int(counts.max())} points on each category of the "
                            f"discrete {aes}-axis, hiding how many there are.",
                            fix="Use `geom_jitter(width=0.2, height=0)` (add `alpha=0.5`), or "
                            "`geom_boxplot()` / `geom_violin()` with points on top.",
                        )
                        return

    if desc.render is None:
        return
    min_n = int(cfg.t("overplot_min_points"))
    threshold = float(cfg.t("overplot_fraction"))
    dpi = desc.render.figure.dpi
    for panel in desc.render.panels:
        for s in panel.of_kind("scatter"):
            if s.x is None or len(s.x) < min_n or s.alpha < 0.9:
                continue
            xy = np.column_stack([s.x, s.y])
            xy = xy[~np.isnan(xy).any(axis=1)]
            disp = panel.ax.transData.transform(xy)
            diam = max(float(np.sqrt(np.median(s.sizes))) * dpi / 72.0, 1.0)
            cells = np.floor(disp / diam).astype(np.int64)
            _, inverse, counts = np.unique(
                cells, axis=0, return_inverse=True, return_counts=True
            )
            shared = counts[inverse.ravel()] > 1
            frac = float(shared.mean()) if len(shared) else 0.0
            if frac > threshold:
                fix = (
                    "`geom_point(alpha=0.3)`, or `geom_bin_2d()` for very large data."
                    if plotnine
                    else "`ax.scatter(x, y, alpha=0.3, s=10)`, or `ax.hexbin(x, y, gridsize=40)` for very large data."
                )
                yield Hit(
                    f"{frac:.0%} of the {len(xy)} points overlap another point at full opacity.",
                    fix=fix,
                    source="render",
                    panel=panel.index,
                    details={"overlap_fraction": round(frac, 3)},
                )
                return


# ---------------------------------------------------------------- MK102
@rule("MK102")
def mk102(desc, cfg):
    if desc.render is None:
        return
    for panel in desc.render.panels:
        if panel.has_3d_bars:
            yield Hit(
                "This chart draws bars in 3D (`bar3d`).",
                fix="Use grouped 2D bars, or a heatmap (`ax.imshow` / `seaborn.heatmap`) for two categorical dimensions.",
                source="render",
                panel=panel.index,
            )
            return


# ---------------------------------------------------------------- MK103
@rule("MK103")
def mk103(desc, cfg):
    if desc.spec is not None:
        spec = desc.spec
        if not spec.is_discrete("x"):
            return
        for layer in spec.layers:
            if layer.geom not in ("geom_line", "geom_path") or layer.built_data is None:
                continue
            col = spec.column(layer, "x")
            if not is_unordered_column(col) or ordinal_like(col.dropna().unique()):
                continue
            data = layer.built_data
            if (
                "group" in data
                and data.groupby(["PANEL", "group"] if "PANEL" in data else "group")
                .size()
                .max()
                < 2
            ):
                continue  # plotnine draws nothing between single-point groups
            yield Hit(
                f"`{layer.geom}` connects the unordered categories of `{layer.mapping['x']}`.",
                fix="Use `geom_point()` or `geom_col()`; if the categories are ordered, make the column "
                "an ordered Categorical and suppress this rule.",
            )
            return
        return

    for panel in desc.render.panels:
        if panel.x.kind != "discrete":
            continue
        labels = [t.text for t in panel.x.tick_labels]
        if ordinal_like(labels):
            continue
        if panel.of_kind("line"):
            yield Hit(
                "A line connects categories on the x-axis that have no inherent order.",
                fix="Use `ax.scatter` or `ax.bar`; suppress if the categories are ordered.",
                source="render",
                panel=panel.index,
            )
            return


# ---------------------------------------------------------------- MK201
@rule("MK201")
def mk201(desc, cfg):
    if desc.render is None:
        return
    limit = int(cfg.t("max_pie_slices"))
    for panel in desc.render.panels:
        if panel.n_wedges > limit:
            yield Hit(
                f"This pie has {panel.n_wedges} slices (more than {limit}).",
                fix="`s.sort_values().plot.barh()` shows the same parts in a readable order.",
                source="render",
                panel=panel.index,
            )


# ---------------------------------------------------------------- MK202
@rule("MK202")
def mk202(desc, cfg):
    limit = int(cfg.t("max_lines"))
    if desc.spec is not None:
        for layer in desc.spec.layers:
            if layer.geom not in ("geom_line", "geom_path") or layer.built_data is None:
                continue
            data = layer.built_data
            if "group" not in data:
                continue
            key = (
                "color" if "color" in data and data["color"].nunique() > 1 else "group"
            )
            per_panel = (
                data.groupby("PANEL")[key].nunique()
                if "PANEL" in data
                else data[key].nunique()
            )
            n = int(
                np.max(per_panel)
            )  # distinctly colored lines; many gray lines + a few colored ones is fine
            if n > limit:
                group_var = (
                    layer.mapping.get("color")
                    or layer.mapping.get("group")
                    or "the grouping variable"
                )
                yield Hit(
                    f"One panel draws {n} differently colored lines (more than {limit}).",
                    fix=f"Gray most lines and color a few, or `facet_wrap('{group_var}')`.",
                )
                return
        return

    for panel in desc.render.panels:
        lines = panel.of_kind("line")
        n = len(
            {tuple(np.round(s.color[:3], 3)) for s in lines if s.color is not None}
        ) or len(lines)
        if n > limit:
            yield Hit(
                f"This panel draws {n} differently colored lines (more than {limit}).",
                fix="Plot most lines in light gray and color a few, or use small multiples (`plt.subplots`).",
                source="render",
                panel=panel.index,
            )
            return


# ---------------------------------------------------------------- MK203
@rule("MK203")
def mk203(desc, cfg):
    spec = desc.spec
    if spec is None:
        return
    summary_bars = [
        l
        for l in spec.layers
        if l.geom in ("geom_bar", "geom_col") and l.stat == "stat_summary"
    ]
    if not summary_bars:
        return
    if any(l.geom in UNCERTAINTY_GEOMS for l in spec.layers):
        return
    yield Hit(
        "Bars show a summary statistic with no error bars or data points.",
        fix="Add `stat_summary(geom='errorbar', fun_data='mean_cl_normal', width=0.2)` or "
        "`geom_jitter(width=0.15, alpha=0.4)`.",
    )


# ---------------------------------------------------------------- MK204
POINT_GEOMS = {"geom_point", "geom_jitter", "geom_sina", "geom_dotplot", "geom_count"}


@rule("MK204")
def mk204(desc, cfg):
    spec = desc.spec
    if spec is None:
        return
    min_n = int(cfg.t("min_box_group_n"))
    if any(l.geom in POINT_GEOMS for l in spec.layers):
        return
    for layer in spec.layers:
        if layer.geom != "geom_boxplot" or layer.raw_data is None:
            continue
        y, x = layer.mapping.get("y"), layer.mapping.get("x")
        if y not in layer.raw_data:
            continue
        data = layer.raw_data
        if x in data:
            counts = data.groupby(x, observed=True)[y].count()
            if counts.empty:
                continue
            smallest = int(counts.min())
            where = f" (smallest: `{counts.idxmin()}`, n = {smallest})"
        else:
            smallest = int(data[y].count())
            where = f" (n = {smallest})"
        if smallest < min_n:
            yield Hit(
                f"Some boxes summarize fewer than {min_n} observations{where}.",
                fix="Add the points: `+ geom_jitter(width=0.15, alpha=0.6)`, and consider showing n per group.",
            )
            return


# ---------------------------------------------------------------- MK205
@rule("MK205")
def mk205(desc, cfg):
    limit = int(cfg.t("max_stack_segments"))
    if desc.spec is not None:
        spec = desc.spec
        for layer in spec.layers:
            if layer.geom not in ("geom_bar", "geom_col") or layer.position not in (
                "position_stack",
                "position_fill",
            ):
                continue
            for aes in ("fill", "color"):
                col = spec.column(layer, aes)
                if col is None or not spec.is_discrete(aes):
                    continue
                n = col.nunique(dropna=True)
                if n > limit:
                    yield Hit(
                        f"Bars stack {n} segments of `{layer.mapping[aes]}`; only the bottom one can be "
                        "compared across bars.",
                        fix=f"Use `position='dodge'`, or `facet_wrap('{layer.mapping[aes]}')`, or lump small "
                        "levels into 'Other'.",
                    )
                    return
        return

    for panel in desc.render.panels:
        bars = [s for s in panel.of_kind("bar") if not s.from_hist]
        stacked = [
            s
            for s in bars
            if s.bottoms is not None and np.any(np.abs(s.bottoms) > 1e-12)
        ]
        if stacked and len(bars) > limit:
            yield Hit(
                f"Bars stack {len(bars)} segments; only the bottom one can be compared across bars.",
                fix="Use grouped bars (`df.plot.bar()` without `stacked=True`) or small multiples, or "
                "combine small categories.",
                source="render",
                panel=panel.index,
            )
            return

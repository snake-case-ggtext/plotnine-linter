"""CL: color."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.colors import to_hex, to_rgb

from ..colors import blend, confusable_pairs, contrast_ratio
from ..describe.model import scale_categories
from ..registry import Hit, rule
from ._util import base_var, is_discrete_column

RAINBOW = {"jet", "rainbow", "hsv", "gist_rainbow", "nipy_spectral", "gist_ncar", "prism", "flag"}
# Okabe-Ito without its yellow, which has too little contrast on white (1.3:1)
OKABE_ITO = '["#E69F00", "#56B4E9", "#009E73", "#0072B2", "#D55E00", "#CC79A7", "#000000"]'


def _base_cmap(name: str) -> str:
    name = str(name)
    return name[:-2] if name.endswith("_r") else name


# ---------------------------------------------------------------- CL101
@rule("CL101")
def cl101(desc, cfg):
    if desc.spec is not None:
        for scale in desc.spec.user_scales:
            palette = getattr(scale, "palette", None)
            name = getattr(palette, "name", None) or getattr(scale, "cmap_name", None)
            if name and _base_cmap(name) in RAINBOW:
                aes = scale.aesthetics[0]
                yield Hit(
                    f"`{type(scale).__name__}` uses the rainbow colormap `{name}`.",
                    fix=f"`scale_{aes}_cmap('viridis')` for sequential data, or `scale_{aes}_cmap('RdBu')` "
                    "with a meaningful midpoint.",
                )
                return
        return

    for panel in desc.render.panels:
        bad = [n for n in panel.cmaps if _base_cmap(n) in RAINBOW]
        if bad:
            yield Hit(
                f"This plot uses the rainbow colormap `{bad[0]}`.",
                fix="Pass `cmap='viridis'` (sequential) or `cmap='RdBu'` with `vmin`/`vmax` centered "
                "on the midpoint (diverging).",
                source="render",
                panel=panel.index,
            )
            return


# ---------------------------------------------------------------- CL102
@rule("CL102")
def cl102(desc, cfg):
    limit = int(cfg.t("max_categorical_colors"))
    if desc.spec is not None:
        spec = desc.spec
        for aes in ("color", "fill"):
            for layer in spec.layers:
                col = spec.column(layer, aes)
                if col is None or not (is_discrete_column(col) or spec.is_discrete(aes)):
                    continue
                n = col.nunique(dropna=True)
                if n > limit:
                    name = layer.mapping[aes]
                    yield Hit(
                        f"`{name}` maps {n} categories to {aes}; more than {limit} hues can't be told apart.",
                        fix=f"Lump rare levels into 'Other', highlight a few and gray the rest, or "
                        f"`facet_wrap('{name}')`.",
                    )
                    break
        return

    for panel in desc.render.panels:
        if _colors_repeat_axis(panel):
            continue
        if panel.legend is not None and len(panel.legend_labels) > limit:
            n = len(panel.legend_labels)
        else:
            colors = {tuple(round(c, 3) for c in s.color[:3]) for s in panel.series if s.color is not None}
            n = len(colors) if len(panel.series) > 1 else 0
        if n > limit:
            yield Hit(
                f"This panel uses {n} categorical colors; more than {limit} can't be told apart.",
                fix="Highlight the few series that matter (gray for the rest), or use small multiples.",
                source="render",
                panel=panel.index,
            )


def _colors_repeat_axis(panel) -> bool:
    """Each color sits on its own category (seaborn hue=x, per-bar palettes)."""
    bars = [s for s in panel.of_kind("bar") if not s.from_hist]
    if not bars or len(bars) != len([s for s in panel.series if s.kind in ("bar", "line", "scatter")]):
        return False
    if len(bars) == 1:
        return False
    occupied = [set(np.round(np.asarray(b.x)[np.abs(np.asarray(b.heights)) > 0], 6)) for b in bars]
    if any(not o for o in occupied):
        occupied = [o for o in occupied if o]
    disjoint = all(occupied[i].isdisjoint(occupied[j]) for i in range(len(occupied)) for j in range(i))
    ticks = {t.text.strip() for t in (panel.x.tick_labels + panel.y.tick_labels)}
    legend_is_axis = bool(panel.legend_labels) and set(l.strip() for l in panel.legend_labels) <= ticks
    return disjoint or legend_is_axis


# ---------------------------------------------------------------- CL201
@rule("CL201")
def cl201(desc, cfg):
    min_de = float(cfg.t("cvd_min_delta_e"))
    if desc.spec is not None:
        spec = desc.spec
        done_exprs = set()
        for aes in ("color", "fill"):
            if not spec.is_discrete(aes):
                continue
            layers = [l for l in spec.layers if aes in l.mapping]
            exprs = {l.mapping[aes] for l in layers}
            if not exprs or exprs <= done_exprs:
                continue  # color and fill mapped to the same variable: one finding
            # redundant encodings: the same variable is also shown by shape, linetype or position
            bases = {base_var(e) for e in exprs}
            redundant = any(
                base_var(l.mapping.get(other)) in bases for l in spec.layers for other in ("shape", "linetype", "x", "y")
            )
            if redundant:
                continue
            colors = []
            for layer in layers:
                if layer.built_data is not None and aes in layer.built_data:
                    colors += [c for c in pd.unique(layer.built_data[aes].dropna()) if isinstance(c, str)]
            pairs = confusable_pairs(colors, min_de)
            if pairs:
                done_exprs |= exprs
                a, b, kind, d = pairs[0]
                names = _color_names(spec, aes)
                la, lb = names.get(a, a), names.get(b, b)
                yield Hit(
                    f"With {kind}, the {aes}s for {la} and {lb} look nearly the same "
                    f"(ΔE2000 {d:g}; {len(pairs)} confusable pair(s) in total).",
                    fix=f"`scale_{aes}_manual(values={OKABE_ITO})`"
                    + (
                        ", or also map `shape` (points) or `linetype` (lines) to the same variable."
                        if aes == "color"
                        else ", or label the categories directly."
                    ),
                    details={"pairs": pairs},
                )
        return

    for panel in desc.render.panels:
        series = [s for s in panel.series if s.kind in ("line", "scatter", "bar") and (s.color is not None or s.palette)]
        if _colors_repeat_axis(panel):
            continue  # each color sits on its own category (hue=x): color repeats the axis
        style_of, colors = {}, []
        for s in series:
            for c in (s.palette or [s.color]):
                colors.append(c[:3])
                style_of.setdefault(to_hex(c[:3]), _style(s))
        if len(colors) < 2:
            continue
        pairs = [
            p for p in confusable_pairs(colors, min_de)
            if style_of.get(p[0]) == style_of.get(p[1])  # a different marker or linestyle keeps a pair apart
        ]
        if pairs:
            a, b, kind, d = pairs[0]
            yield Hit(
                f"With {kind}, series colors {a} and {b} look nearly the same (ΔE2000 {d:g}).",
                fix=f"Use a CVD-safe palette, e.g. `plt.rcParams['axes.prop_cycle'] = "
                f"plt.cycler(color={OKABE_ITO})` (seaborn: `palette='colorblind'`), or vary "
                "markers/linestyles too.",
                source="render",
                panel=panel.index,
                details={"pairs": pairs},
            )
            return


def _color_names(spec, aes) -> dict[str, str]:
    """hex color -> category label, when the scale can tell us."""
    scale = spec.scale_for(aes)
    try:
        limits = scale_categories(scale)
        colors = scale.palette(len(limits))
        return {str(c).lower(): f"'{lim}'" for lim, c in zip(limits, colors)}
    except Exception:
        return {}


# ---------------------------------------------------------------- CL202
SEQUENTIAL = {
    "viridis", "plasma", "inferno", "magma", "cividis", "rocket", "mako", "flare", "crest", "turbo",
    "Blues", "Reds", "Greens", "Greys", "Oranges", "Purples", "BuGn", "BuPu", "GnBu", "OrRd", "PuBu",
    "PuBuGn", "PuRd", "RdPu", "YlGn", "YlGnBu", "YlOrBr", "YlOrRd", "gray", "grey", "binary", "bone",
    "pink", "hot", "afmhot", "cool", "copper", "summer", "autumn", "winter", "spring", "Wistia",
    "jet", "rainbow", "gist_rainbow", "hsv", "nipy_spectral", "gist_ncar", "cubehelix", "gist_heat",
}
DIVERGING = {
    "RdBu", "coolwarm", "bwr", "seismic", "PuOr", "BrBG", "PiYG", "PRGn", "RdGy", "RdYlBu", "RdYlGn",
    "Spectral", "icefire", "vlag", "managua", "berlin", "vanimo",
}


def _spans_zero(values) -> bool:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < 3:
        return False
    lo, hi = v.min(), v.max()
    span = hi - lo
    return lo < 0 < hi and min(-lo, hi) >= 0.1 * span  # real values on both sides of zero


@rule("CL202")
def cl202(desc, cfg):
    if desc.spec is not None:
        spec = desc.spec
        for aes in ("fill", "color"):
            if spec.is_discrete(aes):
                continue
            col = next(
                (spec.column(l, aes) for l in spec.layers if spec.column(l, aes) is not None), None
            )
            if col is None or not pd.api.types.is_numeric_dtype(col) or not _spans_zero(col):
                continue
            scale = spec.user_scale_for(aes)
            name = type(scale).__name__ if scale is not None else f"scale_{aes}_continuous"
            palette = getattr(getattr(scale, "palette", None), "name", None) or getattr(scale, "palette", None)
            pal = _base_cmap(palette) if isinstance(palette, str) else None
            if "gradient2" in name or (pal is not None and pal in DIVERGING) or "gradientn" in name:
                continue
            if pal is not None and pal not in SEQUENTIAL and "cmap" in name:
                continue  # an unfamiliar colormap: can't tell
            expr = next(l.mapping[aes] for l in spec.layers if aes in l.mapping)
            yield Hit(
                f"`{expr}` runs from negative to positive, but {aes} uses a sequential scale, so zero "
                "has no distinct color.",
                fix=f"`scale_{aes}_gradient2(low='#2166ac', mid='white', high='#b2182b', midpoint=0)`",
            )
            return
        return

    for panel in desc.render.panels:
        for artist in list(panel.ax.collections) + list(panel.ax.images):
            get_array = getattr(artist, "get_array", None)
            if get_array is None or getattr(artist, "get_cmap", None) is None:
                continue
            try:
                arr = get_array()
                cmap_name = _base_cmap(artist.get_cmap().name)
            except Exception:
                continue
            if arr is None or not _spans_zero(np.ma.filled(np.ma.asarray(arr, dtype=float), np.nan)):
                continue
            if cmap_name in SEQUENTIAL:
                yield Hit(
                    f"The colored values run from negative to positive, but the colormap `{cmap_name}` is "
                    "sequential, so zero has no distinct color.",
                    fix="Pass `cmap='RdBu_r', vmin=-m, vmax=m` (seaborn heatmap: `cmap='vlag', center=0`).",
                    source="render",
                    panel=panel.index,
                )
                return
            if cmap_name in DIVERGING:
                norm = artist.norm
                if type(norm).__name__ in ("TwoSlopeNorm", "CenteredNorm"):
                    continue
                vmin, vmax = norm.vmin, norm.vmax
                if vmin is not None and vmax is not None and abs(vmin + vmax) > 0.1 * (vmax - vmin):
                    yield Hit(
                        f"The diverging colormap `{cmap_name}` isn't centered at zero "
                        f"(color limits {vmin:.3g} to {vmax:.3g}), so its neutral color isn't zero.",
                        fix="Set symmetric limits, e.g. `vmin=-m, vmax=m`, or `norm=TwoSlopeNorm(vcenter=0)`.",
                        source="render",
                        panel=panel.index,
                    )
                    return


# ---------------------------------------------------------------- CL203
@rule("CL203")
def cl203(desc, cfg):
    if desc.spec is not None:
        spec = desc.spec
        legend_hidden = spec.legend_position == "none" or (desc.render is not None and not desc.render.has_legend)
        for layer in spec.layers:
            if layer.geom not in ("geom_col", "geom_bar", "geom_boxplot", "geom_violin"):
                continue
            for aes in ("fill", "color"):
                expr = layer.mapping.get(aes)
                if expr is None or base_var(expr) not in (base_var(layer.mapping.get("x")), base_var(layer.mapping.get("y"))):
                    continue
                if legend_hidden or layer.show_legend is False:
                    yield Hit(
                        f"Each bar gets its own {aes} from `{expr}`, which the axis already shows, so the "
                        "colors carry no information.",
                        fix=f"Drop `{aes}='{expr}'` and use one color, e.g. `{layer.geom}(fill='#4C72B0')`.",
                    )
                    return
        return

    for panel in desc.render.panels:
        if panel.legend is not None:
            continue  # with a legend, LB203 covers color that repeats the axis
        bars = [s for s in panel.of_kind("bar") if not s.from_hist]
        if len(bars) == 1:
            colors = {tuple(np.round(r.get_facecolor()[:3], 3)) for r in bars[0].artist.patches}
            if len(colors) >= 3 and len(colors) == len(bars[0].artist.patches):
                yield Hit(
                    f"Each of the {len(colors)} bars has its own color, but the colors don't stand for anything.",
                    fix="Use one color: `ax.bar(x, y, color='#4C72B0')` (seaborn: `color=` instead of `palette=`).",
                    source="render",
                    panel=panel.index,
                )
                return
        elif len(bars) >= 3:
            positions = [set(np.round(b.x, 6)) for b in bars]
            disjoint = all(positions[i].isdisjoint(positions[j]) for i in range(len(bars)) for j in range(i))
            colors = {b.color[:3] for b in bars if b.color is not None}
            if disjoint and len(colors) == len(bars) and all(len(p) == 1 for p in positions):
                yield Hit(
                    f"Each of the {len(bars)} bars has its own color, but the colors don't stand for anything.",
                    fix="Use one color (seaborn: drop `hue=` or pass `color=`), and keep color for a real variable.",
                    source="render",
                    panel=panel.index,
                )
                return


# ---------------------------------------------------------------- CL204 / CL301 helpers
def _panel_bg(ax):
    fc = ax.get_facecolor()
    if fc[3] < 0.5:  # transparent axes: the figure shows through
        fc = ax.figure.get_facecolor()
    return tuple(fc[:3])


def _saturation(rgb) -> float:
    mx, mn = max(rgb[:3]), min(rgb[:3])
    return 0.0 if mx == 0 else (mx - mn) / mx


def _mark_colors(desc, panel):
    """(label, rgb, alpha, has_dark_edge) for the data marks drawn on ``panel``."""
    out = []
    spec = desc.spec
    if spec is not None:
        for layer in spec.layers:
            data = layer.built_data
            if data is None:
                continue
            if "PANEL" in data:
                data = data[data["PANEL"].astype(str) == str(panel.index + 1)]
            filled = layer.geom in ("geom_col", "geom_bar", "geom_histogram", "geom_area", "geom_boxplot",
                                    "geom_violin", "geom_tile", "geom_density", "geom_ribbon")
            key = "fill" if filled else "color"
            if key not in data:
                continue
            if key in layer.mapping and not spec.is_discrete(key):
                continue  # continuous scales run light to dark on purpose
            alpha = layer.aes_params.get("alpha", 1.0)
            if "alpha" in data and data["alpha"].notna().any():
                alpha = float(data["alpha"].dropna().max())
            edge = None
            if filled:
                edge = layer.aes_params.get("color")
                if edge is None and "color" in data and data["color"].notna().any():
                    edge = data["color"].dropna().iloc[0]
                if edge is not None and not isinstance(edge, str):
                    edge = None
            for c in pd.unique(data[key].dropna()):
                if not isinstance(c, str):
                    continue
                try:
                    rgb = tuple(to_rgb(c))
                except ValueError:
                    continue
                out.append((c, rgb, float(alpha if alpha is not None else 1.0), edge))
        return out
    for s in panel.series:
        if s.kind not in ("line", "scatter", "bar"):
            continue
        colors = s.palette or ([s.color] if s.color is not None else [])
        edge = None
        if s.kind == "bar" and s.artist is not None and s.artist.patches:
            patch = s.artist.patches[0]
            if patch.get_linewidth() > 0:
                edge = patch.get_edgecolor()
        for c in colors:
            alpha = s.alpha if s.kind != "bar" else (c[3] if len(c) > 3 else 1.0)
            out.append((s.label or "", tuple(c[:3]), float(alpha), edge))
    return out


# ---------------------------------------------------------------- CL204
@rule("CL204")
def cl204(desc, cfg):
    if desc.render is None:
        return
    min_cr = float(cfg.t("min_mark_contrast"))
    for panel in desc.render.panels:
        bg = _panel_bg(panel.ax)
        marks = [m for m in _mark_colors(desc, panel) if m[2] >= 0.9]  # translucent marks are deliberate
        if not marks:
            continue
        ratios = [(contrast_ratio(rgb, bg), name, rgb, edge) for name, rgb, _, edge in marks]
        best = max(r[0] for r in ratios)
        for cr, name, rgb, edge in sorted(ratios, key=lambda r: r[0]):
            if cr >= min_cr:
                break
            if edge is not None and contrast_ratio(to_rgb(edge), bg) >= 3.0:
                continue  # a dark outline carries the shape
            if _saturation(rgb) < 0.12 and best >= min_cr and len(ratios) > 1:
                continue  # light gray context behind highlighted marks
            hexcode = to_hex(rgb)
            yield Hit(
                f"Marks colored {hexcode} have a contrast of only {cr:.1f}:1 against the "
                f"{to_hex(bg)} background (WCAG asks 3:1).",
                fix=(
                    "Pick a darker color, e.g. from `scale_color_manual(values=[...])` without yellow or pastels, "
                    "or outline light fills: `geom_col(color='#333333')`."
                    if desc.source == "plotnine"
                    else "Pick a darker color, or outline light fills: `ax.bar(..., edgecolor='#333333')`."
                ),
                source="render",
                panel=panel.index,
                details={"contrast": round(cr, 2), "color": hexcode},
            )
            return


def _style(series) -> tuple:
    """What distinguishes a series besides color: linestyle and marker shape."""
    artist = series.artist
    if hasattr(artist, "get_marker"):  # Line2D
        return (str(artist.get_linestyle()), str(artist.get_marker()))
    paths = getattr(artist, "get_paths", lambda: [])()
    if paths:  # PathCollection (scatter): compare marker shapes
        return ("scatter", np.round(paths[0].vertices, 2).tobytes())
    return ("", id(artist))


# ---------------------------------------------------------------- CL301
@rule("CL301")
def cl301(desc, cfg):
    min_de = float(cfg.t("cvd_min_delta_e"))
    spec = desc.spec
    if spec is not None:
        for aes in ("color", "fill"):
            if not spec.is_discrete(aes):
                continue
            exprs = {l.mapping[aes] for l in spec.layers if aes in l.mapping}
            if not exprs:
                continue
            bases = {base_var(e) for e in exprs}
            if any(base_var(l.mapping.get(o)) in bases for l in spec.layers for o in ("shape", "linetype", "x", "y")):
                continue
            if any(l.geom in ("geom_text", "geom_label") for l in spec.layers):
                continue  # direct labels
            colors = []
            for layer in spec.layers:
                if aes in layer.mapping and layer.built_data is not None and aes in layer.built_data:
                    colors += [c for c in pd.unique(layer.built_data[aes].dropna()) if isinstance(c, str)]
            pairs = confusable_pairs(colors, min_de, kinds=("grayscale",))
            if pairs:
                names = _color_names(spec, aes)
                a, b, _, d = pairs[0]
                expr = next(iter(exprs))
                yield Hit(
                    f"`{expr}` is shown by color alone, and in grayscale {names.get(a, a)} and {names.get(b, b)} "
                    f"look the same.",
                    fix=(
                        f"Also map `shape='{expr}'` (points) or `linetype='{expr}'` (lines), or label the groups "
                        "directly with `geom_text`."
                    ),
                    details={"pairs": pairs},
                )
                return
        return
    for panel in desc.render.panels:
        series = [s for s in panel.series if s.kind in ("line", "scatter") and (s.color is not None or s.palette)]
        if len(series) < 2 and not any(s.palette for s in series):
            continue
        styles = {_style(s) for s in series}
        if len(series) > 1 and len(styles) == len(series):
            continue  # every series also differs in linestyle or marker shape
        colors = []
        for s in series:
            colors += [c[:3] for c in s.palette] if s.palette else [s.color[:3]]
        pairs = confusable_pairs(colors, min_de, kinds=("grayscale",))
        if pairs:
            a, b, _, d = pairs[0]
            yield Hit(
                f"Groups are told apart by color alone, and in grayscale {a} and {b} look the same.",
                fix="Vary markers or linestyles too (seaborn: `style=` the same variable as `hue=`), or label the "
                "groups directly with `ax.annotate`.",
                source="render",
                panel=panel.index,
                details={"pairs": pairs},
            )
            return

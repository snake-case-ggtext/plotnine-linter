"""Render adapter: read a drawn matplotlib figure.

It reads any matplotlib figure, including the figure that plotnine draws. So
the render-level rules (overlap, font sizes, legends, colors, point density)
apply to both libraries.
"""

from __future__ import annotations

import functools

import matplotlib
import numpy as np
from matplotlib import category, ticker
from matplotlib import dates as mdates
from matplotlib.collections import PathCollection
from matplotlib.colors import to_rgba
from matplotlib.container import BarContainer
from matplotlib.patches import Wedge
from matplotlib.text import Text

from .model import PROBE_ERRORS, AxisInfo, PanelInfo, RenderInfo, Series, TextBox

# Measuring text can fail on bad mathtext (ValueError) or a missing renderer (RuntimeError).
TEXT_ERRORS = (ValueError, RuntimeError)


def get_renderer(fig):
    """Return a renderer for ``fig``, drawing it so text extents are final."""
    canvas = fig.canvas
    if not hasattr(canvas, "get_renderer"):
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        canvas = FigureCanvasAgg(fig)
    canvas.draw()
    return canvas.get_renderer()


# ---------------------------------------------------------------------------
# axes helpers
# ---------------------------------------------------------------------------


def _converter(axis):
    getter = getattr(axis, "get_converter", None)
    return getter() if getter else getattr(axis, "converter", None)


def _axis_kind(axis) -> str:
    conv = _converter(axis)
    if isinstance(conv, category.StrCategoryConverter) or isinstance(
        getattr(axis, "units", None), category.UnitData
    ):
        return "discrete"
    date_converters = tuple(
        c
        for c in (
            getattr(mdates, "DateConverter", None),
            getattr(mdates, "ConciseDateConverter", None),
            getattr(mdates, "_SwitchableDateConverter", None),
        )
        if c is not None
    )
    if date_converters and isinstance(conv, date_converters):
        return "datetime"
    fmt = axis.get_major_formatter()
    if isinstance(
        fmt,
        (mdates.AutoDateFormatter, mdates.ConciseDateFormatter, mdates.DateFormatter),
    ):
        return "datetime"
    labels = None
    if isinstance(fmt, ticker.FixedFormatter):
        labels = list(fmt.seq)
    elif isinstance(fmt, ticker.FuncFormatter):
        # set_xticks(pos, labels) / set_xticklabels install
        # FuncFormatter(partial(axis._format_with_dict, {pos: label})) in matplotlib >= 3.5
        func = getattr(fmt, "func", None)
        if (
            isinstance(func, functools.partial)
            and getattr(func.func, "__name__", "") == "_format_with_dict"
        ):
            labels = list(func.args[0].values()) if func.args else None
    if labels:
        labels = [s for s in labels if str(s).strip()]
        if labels and not all(_looks_numeric(s) for s in labels):
            return "discrete"
    return "continuous"


def _looks_numeric(s) -> bool:
    try:
        float(str(s).replace("−", "-").replace(",", "").replace("%", ""))
        return True
    except ValueError:
        return False


def _tick_boxes(labels, renderer, role, panel) -> list[TextBox]:
    out = []
    for t in labels:
        if not t.get_visible() or not t.get_text().strip():
            continue
        out.append(
            TextBox(
                text=t.get_text(),
                bbox=t.get_window_extent(renderer),
                fontsize=float(t.get_fontsize()),
                rotation=float(t.get_rotation()) % 360,
                role=role,
                panel=panel,
            )
        )
    return out


def _axis_info(ax, which: str, renderer, panel: int) -> AxisInfo:
    axis = ax.xaxis if which == "x" else ax.yaxis
    labels = ax.get_xticklabels() if which == "x" else ax.get_yticklabels()
    label = axis.label.get_text() if axis.label.get_visible() else ""
    return AxisInfo(
        kind=_axis_kind(axis),
        label=label or "",
        scale=ax.get_xscale() if which == "x" else ax.get_yscale(),
        limits=tuple(ax.get_xlim() if which == "x" else ax.get_ylim()),
        tick_labels=_tick_boxes(labels, renderer, f"{which}tick", panel),
        visible=bool(ax.axison and axis.get_visible()),
    )


def _rgba(color) -> tuple | None:
    try:
        return tuple(float(c) for c in to_rgba(color))
    except (ValueError, TypeError):
        return None


def _single_color(colors) -> tuple | None:
    arr = np.asarray(colors)
    if arr.ndim == 2 and len(arr) >= 1:
        if len(np.unique(np.round(arr, 3), axis=0)) == 1:
            return tuple(float(c) for c in arr[0])
        return None
    return _rgba(colors)


def _uses_data_coords(transform, ax) -> bool:
    try:
        return transform == ax.transData
    except (TypeError, ValueError):  # pragma: no cover - odd transforms
        return False


def _series(ax) -> list[Series]:
    series: list[Series] = []

    # lines (and marker-only "lines", which read as scatter)
    for line in ax.get_lines():
        if not line.get_visible() or not _uses_data_coords(line.get_transform(), ax):
            continue
        x = (
            np.asarray(line.get_xdata(orig=False), dtype=float)
            if _is_num(line.get_xdata(orig=False))
            else None
        )
        y = (
            np.asarray(line.get_ydata(orig=False), dtype=float)
            if _is_num(line.get_ydata(orig=False))
            else None
        )
        n = len(line.get_xdata(orig=False))
        if n < 2:
            continue
        ls = line.get_linestyle()
        no_line = ls in ("None", "none", " ", "")
        alpha = line.get_alpha()
        if no_line and line.get_marker() not in (None, "None", "none", ""):
            ms = float(line.get_markersize())
            series.append(
                Series(
                    kind="scatter",
                    color=_rgba(line.get_markerfacecolor()),
                    label=line.get_label(),
                    x=x,
                    y=y,
                    alpha=1.0 if alpha is None else float(alpha),
                    sizes=np.full(n, ms**2),
                    artist=line,
                )
            )
        elif not no_line:
            series.append(
                Series(
                    kind="segment" if _is_glyph(x, y) else "line",
                    color=_rgba(line.get_color()),
                    label=line.get_label(),
                    x=x,
                    y=y,
                    alpha=1.0 if alpha is None else float(alpha),
                    artist=line,
                )
            )

    # scatter collections (plt.scatter and plotnine geom_point)
    for coll in ax.collections:
        if not isinstance(coll, PathCollection) or not coll.get_visible():
            continue
        offsets = np.asarray(coll.get_offsets())
        if offsets.ndim != 2 or len(offsets) == 0:
            continue
        if not _uses_data_coords(coll.get_offset_transform(), ax):
            continue
        fc = np.asarray(coll.get_facecolor())
        a = coll.get_alpha()
        if a is None:
            a = float(fc[:, 3].mean()) if fc.ndim == 2 and len(fc) else 1.0
        sizes = np.asarray(coll.get_sizes(), dtype=float)
        if sizes.size == 0:
            sizes = np.array([matplotlib.rcParams["lines.markersize"] ** 2])
        palette = None
        if fc.ndim == 2 and len(fc) > 1:
            uniq = np.unique(np.round(fc[:, :3], 3), axis=0)
            if 2 <= len(uniq) <= 12:
                palette = [tuple(float(v) for v in c) for c in uniq]
        series.append(
            Series(
                kind="scatter",
                palette=palette,
                color=_single_color(fc) if fc.size else None,
                label=str(coll.get_label()),
                x=offsets[:, 0].astype(float),
                y=offsets[:, 1].astype(float),
                alpha=float(a),
                sizes=np.resize(sizes, len(offsets)),
                artist=coll,
            )
        )

    # bars
    for cont in ax.containers:
        if not isinstance(cont, BarContainer) or not len(cont.patches):
            continue
        orient = getattr(cont, "orientation", None) or "vertical"
        rects = [r for r in cont.patches if r.get_visible()]
        if not rects:
            continue
        if orient == "vertical":
            pos = np.array([r.get_x() + r.get_width() / 2 for r in rects])
            width = np.array([r.get_width() for r in rects])
            bottoms = np.array([r.get_y() for r in rects])
            heights = np.array([r.get_height() for r in rects])
        else:
            pos = np.array([r.get_y() + r.get_height() / 2 for r in rects])
            width = np.array([r.get_height() for r in rects])
            bottoms = np.array([r.get_x() for r in rects])
            heights = np.array([r.get_width() for r in rects])
        tagged = getattr(cont, "_plotnine_linter_hist", None)
        from_hist = (
            bool(tagged)
            if tagged is not None
            else (not _HIST_TAGGING and _contiguous(pos, width))
        )
        series.append(
            Series(
                kind="bar",
                color=_rgba(rects[0].get_facecolor()),
                label=cont.get_label() or "",
                x=pos,
                y=bottoms + heights,
                orientation=orient,
                bottoms=bottoms,
                heights=heights,
                from_hist=from_hist,
                artist=cont,
            )
        )
    return series


def _is_glyph(x, y) -> bool:
    """Short axis-aligned pieces drawn by box plots, error bars and CIs, not data lines."""
    if x is None or y is None:
        return False
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    if len(x) < 2:
        return True
    ux = len(np.unique(np.round(x, 9)))
    uy = len(np.unique(np.round(y, 9)))
    if ux <= 1:  # vertical: whiskers, error bars, CI lines
        return True
    if len(x) == 2 and uy <= 1:  # short horizontal: caps, medians
        return True
    closed = np.allclose([x[0], y[0]], [x[-1], y[-1]])
    return bool(closed and len(x) <= 5 and ux <= 2 and uy <= 2)  # box outline


_HIST_TAGGING: bool = False  # set once tag_histograms() has wrapped Axes.hist


def tag_histograms() -> None:
    """Wrap ``Axes.hist`` to tag the bars it draws as a histogram.

    The Jupyter hook and ``plotnine-linter check`` call this before any plotting.
    Without it (e.g. ``lint(fig)`` on a figure made earlier), the render adapter
    treats touching bars of equal width as a histogram.
    """
    global _HIST_TAGGING
    from matplotlib.axes import Axes

    if getattr(Axes.hist, "_plotnine_linter", False):
        _HIST_TAGGING = True
        return
    original = Axes.hist

    def hist(self, *args, **kwargs):
        out = original(self, *args, **kwargs)
        containers = out[2] if isinstance(out, tuple) and len(out) == 3 else None
        items = containers if isinstance(containers, list) else [containers]
        for c in items:
            if isinstance(c, BarContainer):
                setattr(c, "_plotnine_linter_hist", True)  # noqa: B010
        for c in self.containers:  # bars drawn by bar() keep no tag
            if isinstance(c, BarContainer) and not hasattr(c, "_plotnine_linter_hist"):
                setattr(c, "_plotnine_linter_hist", False)  # noqa: B010
        return out

    setattr(hist, "_plotnine_linter", True)  # noqa: B010
    setattr(Axes, "hist", hist)  # noqa: B010
    _wrap_bar()
    _HIST_TAGGING = True


def _wrap_bar() -> None:
    from matplotlib.axes import Axes

    if getattr(Axes.bar, "_plotnine_linter", False):
        return
    original = Axes.bar

    def bar(self, *args, **kwargs):
        out = original(self, *args, **kwargs)
        if isinstance(out, BarContainer) and not hasattr(out, "_plotnine_linter_hist"):
            # hist() re-tags its own bars after this returns
            setattr(out, "_plotnine_linter_hist", False)  # noqa: B010
        return out

    setattr(bar, "_plotnine_linter", True)  # noqa: B010
    setattr(Axes, "bar", bar)  # noqa: B010


def _is_num(values) -> bool:
    try:
        np.asarray(values, dtype=float)
        return True
    except (TypeError, ValueError):
        return False


def _contiguous(pos, width) -> bool:
    """True when bars touch with equal widths, as Axes.hist draws them."""
    if len(pos) < 3:
        return False
    order = np.argsort(pos)
    p, w = pos[order], width[order]
    if not np.allclose(w, w[0], rtol=1e-6):
        return False
    return bool(np.allclose(np.diff(p), w[0], rtol=1e-6))


def _has_3d_bars(ax) -> bool:
    try:
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except ImportError:  # pragma: no cover
        return False
    for coll in ax.collections:
        if not isinstance(coll, Poly3DCollection):
            continue
        segs = getattr(coll, "_faces", None)  # matplotlib >= 3.10
        if (
            segs is None
            and getattr(coll, "_vec", None) is not None
            and getattr(coll, "_segslices", None)
        ):
            vec = np.asarray(
                coll._vec
            )  # matplotlib <= 3.10: homogeneous coords + per-face slices
            segs = [vec[:3, sl].T for sl in coll._segslices]
        if segs is None:
            segs = getattr(coll, "_segments3d", None)  # older matplotlib
        if segs is None or len(segs) == 0:
            continue
        aligned = 0
        for face in segs:
            face = np.asarray(face, dtype=float)
            if face.ndim != 2 or face.shape[1] != 3:
                break
            if any(np.allclose(face[:, k], face[0, k]) for k in range(3)):
                aligned += 1
        if aligned == len(segs) and len(segs) % 6 == 0:
            return True
    return False


def _cmaps(ax) -> list[str]:
    names = []
    for artist in list(ax.collections) + list(ax.images):
        get_array = getattr(artist, "get_array", None)
        get_cmap = getattr(artist, "get_cmap", None)
        if get_array is None or get_cmap is None:
            continue
        try:
            if get_array() is None:
                continue
            names.append(get_cmap().name)
        except PROBE_ERRORS:
            continue
    return names


def _is_colorbar(ax) -> bool:
    return hasattr(ax, "_colorbar") or ax.get_label() == "<colorbar>"


# ---------------------------------------------------------------------------
# the adapter
# ---------------------------------------------------------------------------


def describe_figure(fig, is_plotnine: bool = False) -> RenderInfo:
    renderer = get_renderer(fig)
    axes = [ax for ax in fig.axes if ax.get_visible() and not _is_colorbar(ax)]
    panels: list[PanelInfo] = []
    for i, ax in enumerate(axes):
        legend = ax.get_legend()
        panels.append(
            PanelInfo(
                index=i,
                ax=ax,
                x=_axis_info(ax, "x", renderer, i),
                y=_axis_info(ax, "y", renderer, i),
                series=_series(ax),
                n_wedges=sum(
                    isinstance(p, Wedge) and p.get_visible() for p in ax.patches
                ),
                cmaps=_cmaps(ax),
                is_3d=getattr(ax, "name", "") == "3d",
                has_3d_bars=getattr(ax, "name", "") == "3d" and _has_3d_bars(ax),
                legend=legend,
                legend_labels=[t.get_text() for t in legend.get_texts()]
                if legend
                else [],
                legend_title=legend.get_title().get_text() if legend else "",
                axis_off=not ax.axison,
            )
        )

    # twins: same position, sharing one axis (Axes.twinx / twiny)
    for i, a in enumerate(axes):
        for j in range(i):
            b = axes[j]
            same_box = np.allclose(
                a.get_position().bounds, b.get_position().bounds, atol=1e-6
            )
            shared_x = a.get_shared_x_axes().joined(a, b)
            shared_y = a.get_shared_y_axes().joined(a, b)
            if same_box and (shared_x or shared_y) and panels[j].twin_of is None:
                panels[i].twin_of = j
                panels[i].twin_shared = "x" if shared_x else "y"
                break

    # every visible text, with its role
    roles: dict[int, tuple[str, int | None]] = {}
    for p in panels:
        ax = p.ax
        for t in ax.get_xticklabels():
            roles[id(t)] = ("xtick", p.index)
        for t in ax.get_yticklabels():
            roles[id(t)] = ("ytick", p.index)
        roles[id(ax.xaxis.label)] = ("xlabel", p.index)
        roles[id(ax.yaxis.label)] = ("ylabel", p.index)
        roles[id(ax.title)] = ("title", p.index)
        if p.legend is not None:
            for t in p.legend.get_texts():
                roles[id(t)] = ("legend", p.index)
            roles[id(p.legend.get_title())] = ("legend", p.index)

    legend_bboxes = []
    figure_legend_labels: list[str] = []
    fig_legends = list(getattr(fig, "legends", []))
    offsetbox_legends = [
        a for a in fig.artists if type(a).__name__ == "FlexibleAnchoredOffsetbox"
    ]
    for leg in fig_legends + offsetbox_legends:
        try:
            legend_bboxes.append(leg.get_window_extent(renderer))
        except TEXT_ERRORS:
            continue
        for t in leg.findobj(Text):
            if t.get_text().strip():
                roles[id(t)] = ("legend", None)
                figure_legend_labels.append(t.get_text())
    for t in fig.findobj(Text):
        if type(t).__name__ == "StripText":
            roles.setdefault(id(t), ("strip", None))

    texts = []
    seen = set()
    for t in fig.findobj(Text):
        if id(t) in seen or not t.get_visible() or not t.get_text().strip():
            continue
        seen.add(id(t))
        role, panel = roles.get(id(t), ("other", None))
        if role in ("xtick", "ytick"):
            # skip tick labels for ticks outside the view
            try:
                bb = t.get_window_extent(renderer)
            except TEXT_ERRORS:
                continue
            if bb.width == 0 and bb.height == 0:
                continue
        try:
            bbox = t.get_window_extent(renderer)
        except TEXT_ERRORS:
            continue
        color = _rgba(t.get_color())
        if color is not None and t.get_alpha() is not None:
            color = (*color[:3], color[3] * float(t.get_alpha()))
        texts.append(
            TextBox(
                text=t.get_text(),
                bbox=bbox,
                fontsize=float(t.get_fontsize()),
                rotation=float(t.get_rotation()) % 360,
                role=role,
                panel=panel,
                color=color,
                weight=str(t.get_fontweight()),
                artist=t,
            )
        )

    return RenderInfo(
        figure=fig,
        renderer=renderer,
        panels=panels,
        texts=texts,
        legend_bboxes=legend_bboxes,
        figure_legend_labels=figure_legend_labels,
        is_plotnine=is_plotnine,
    )

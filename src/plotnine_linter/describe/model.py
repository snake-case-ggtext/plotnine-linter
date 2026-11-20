"""The shared chart description that every rule reads.

Two adapters fill it in:

* the **spec adapter** (plotnine only) records intent: which column maps to
  which aesthetic, which geoms and stats are used, scales, facets, labels;
* the **render adapter** (any matplotlib figure, including plotnine's) records
  what the reader sees: marks, tick labels, text sizes, legends, colors.

Rules ask for ``desc.spec`` and/or ``desc.render`` and skip silently when the
part they need is missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Render side
# ---------------------------------------------------------------------------


@dataclass
class TextBox:
    text: str
    bbox: Any  # matplotlib.transforms.Bbox in display pixels
    fontsize: float  # points
    rotation: float  # degrees
    role: str  # xtick, ytick, xlabel, ylabel, title, legend, strip, other
    panel: int | None = None
    color: tuple | None = None  # RGBA as drawn (alpha folded in)
    weight: str = "normal"
    artist: object = None


@dataclass
class AxisInfo:
    kind: str = "unknown"  # continuous, discrete, datetime, unknown
    label: str = ""
    scale: str = "linear"  # matplotlib scale name: linear, log, symlog...
    limits: tuple[float, float] | None = None  # visible range, data units
    tick_labels: list[TextBox] = field(default_factory=list)
    visible: bool = True


@dataclass
class Series:
    """One drawn series (a line, a scatter layer, a bar group) on a panel."""

    kind: str  # line, scatter, bar, segment (box/whisker/CI pieces, not data lines)
    color: tuple | None = None  # RGBA of the series, when it has one color
    label: str = ""
    x: np.ndarray | None = None
    y: np.ndarray | None = None
    alpha: float = 1.0  # effective alpha of the marks
    sizes: np.ndarray | None = None  # scatter marker areas, pt^2
    artist: Any = None
    orientation: str = "vertical"  # bars only
    bottoms: np.ndarray | None = None  # bars only: baseline per bar
    heights: np.ndarray | None = None  # bars only: signed length per bar
    from_hist: bool = False  # bars only: drawn by Axes.hist
    palette: list[tuple] | None = None  # scatter with per-point colors: its distinct colors


@dataclass
class PanelInfo:
    index: int
    ax: Any
    x: AxisInfo
    y: AxisInfo
    series: list[Series] = field(default_factory=list)
    n_wedges: int = 0
    cmaps: list[str] = field(default_factory=list)  # colormap names in use
    is_3d: bool = False
    has_3d_bars: bool = False
    legend: Any = None  # matplotlib Legend attached to this axes
    legend_labels: list[str] = field(default_factory=list)
    legend_title: str = ""
    twin_of: int | None = None
    twin_shared: str | None = None  # "x" for twinx (shared x), "y" for twiny
    axis_off: bool = False

    def of_kind(self, kind: str) -> list[Series]:
        return [s for s in self.series if s.kind == kind]

    @property
    def has_data(self) -> bool:
        """False for empty axes (e.g. a cell that made a figure, then failed before plotting)."""
        ax = self.ax
        return bool(
            self.series or self.n_wedges or self.cmaps or self.is_3d
            or len(ax.collections) or len(ax.images) or len(ax.patches) or len(ax.lines)
        )


@dataclass
class RenderInfo:
    figure: Any
    renderer: Any
    panels: list[PanelInfo]
    texts: list[TextBox]
    legend_bboxes: list[Any]  # figure-level legends (plotnine puts its legend here)
    figure_legend_labels: list[str] = field(default_factory=list)
    is_plotnine: bool = False

    @property
    def has_legend(self) -> bool:
        return bool(self.legend_bboxes) or any(p.legend is not None for p in self.panels)


# ---------------------------------------------------------------------------
# Spec side (plotnine)
# ---------------------------------------------------------------------------


@dataclass
class LayerSpec:
    index: int
    geom: str  # e.g. "geom_col"
    stat: str  # e.g. "stat_identity"
    position: str  # e.g. "position_stack"
    mapping: dict[str, str]  # effective mapping (plot mapping + layer mapping)
    geom_params: dict
    stat_params: dict
    aes_params: dict  # fixed aesthetics, e.g. alpha=0.3
    raw_data: pd.DataFrame | None
    built_data: pd.DataFrame | None
    show_legend: Any = None


@dataclass
class SpecInfo:
    plot: Any  # the user's ggplot object (never mutated)
    built: Any  # a drawn deep copy
    mapping: dict[str, str]
    layers: list[LayerSpec]
    user_labels: dict[str, str]  # labels the user set with labs()/xlab()...
    final_labels: dict[str, str]  # labels plotnine actually shows
    scales: list[Any]  # trained scales from the drawn copy
    user_scales: list[Any]  # scales the user added
    facet_free: dict[str, bool]
    facet_type: str
    coord: str
    coord_limits: dict[str, Any]
    panel_ranges: list[dict[str, tuple[float, float]]]  # per panel, keyed by data aesthetic x/y
    legend_position: Any = None

    # ----- helpers rules use ------------------------------------------
    def column(self, layer: LayerSpec, aes: str) -> pd.Series | None:
        """The raw data column mapped to ``aes`` in ``layer``, if it is a plain column."""
        expr = layer.mapping.get(aes)
        if not isinstance(expr, str) or layer.raw_data is None:
            return None
        if expr in layer.raw_data.columns:
            return layer.raw_data[expr]
        return None

    def scale_for(self, aes: str) -> Any:
        for s in self.scales:
            if aes in getattr(s, "aesthetics", []):
                return s
        return None

    def user_scale_for(self, aes: str) -> Any:
        found = None
        for s in self.user_scales:
            if aes in getattr(s, "aesthetics", []):
                found = s  # later scales replace earlier ones
        return found

    def is_discrete(self, aes: str) -> bool:
        s = self.scale_for(aes)
        return s is not None and _is_discrete_scale(s)

    def is_datetime(self, aes: str) -> bool:
        s = self.scale_for(aes)
        return s is not None and any(k in type(s).__name__ for k in ("datetime", "date", "timedelta"))


def _is_discrete_scale(scale: Any) -> bool:
    return any("discrete" in cls.__name__ for cls in type(scale).__mro__)


# ---------------------------------------------------------------------------
# Together
# ---------------------------------------------------------------------------


@dataclass
class ChartDescription:
    source: str  # "plotnine" or "matplotlib"
    spec: SpecInfo | None = None
    render: RenderInfo | None = None
    errors: list[str] = field(default_factory=list)  # adapter problems, for debugging
    session: Any = None  # a session.Session when figures are linted as a set (notebooks)


def scale_categories(scale: Any) -> list[str]:
    """Category names of a trained discrete scale, in legend order (plotnine 0.13-0.15)."""
    if scale is None:
        raise ValueError("no scale")
    for attr in ("final_limits", "limits"):
        try:
            value = getattr(scale, attr)
            value = value() if callable(value) else value
        except Exception:
            continue
        if value is not None and len(value) and all(isinstance(v, str) for v in value):
            return [str(v) for v in value]
    rng = getattr(getattr(scale, "range", None), "range", None)
    if rng is not None and len(rng):
        return [str(v) for v in rng]
    raise ValueError("scale has no categories")

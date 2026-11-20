"""Build a :class:`ChartDescription` from a plotnine plot or matplotlib figure."""

from __future__ import annotations

from typing import Any

from .model import ChartDescription
from .render import describe_figure
from .spec import describe_plotnine, is_ggplot

__all__ = ["describe", "ChartDescription"]


def describe(obj: Any) -> ChartDescription:
    """Describe ``obj``: a plotnine ``ggplot``, a matplotlib ``Figure`` or ``Axes``."""
    if is_ggplot(obj):
        spec, fig = describe_plotnine(obj)
        render = describe_figure(fig, is_plotnine=True)
        _apply_spec_axis_kinds(spec, render)
        return ChartDescription(source="plotnine", spec=spec, render=render)

    fig = _figure_of(obj)
    if fig is None:
        raise TypeError(
            f"plotnine-linter can lint a plotnine ggplot, a matplotlib Figure or Axes; got {type(obj).__name__}"
        )
    return ChartDescription(source="matplotlib", render=describe_figure(fig))


def _figure_of(obj: Any):
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure, SubFigure

    if isinstance(obj, (Figure, SubFigure)):
        return obj
    if isinstance(obj, Axes):
        return obj.figure
    # an array or list of Axes, as returned by plt.subplots(1, 2) or df.hist()
    try:
        import numpy as np

        flat = np.asarray(obj, dtype=object).ravel()
        if flat.size and all(isinstance(a, Axes) for a in flat):
            return flat[0].figure
    except Exception:
        pass
    # seaborn FacetGrid / JointGrid / PairGrid and similar wrappers
    for attr in ("figure", "fig"):
        fig = getattr(obj, attr, None)
        if isinstance(fig, Figure):
            return fig
    return None


def _apply_spec_axis_kinds(spec, render) -> None:
    """plotnine draws every axis as numeric; take axis kinds from its scales."""
    flipped = spec.coord == "coord_flip"
    for panel in render.panels:
        for display, data_aes in (("x", "y" if flipped else "x"), ("y", "x" if flipped else "y")):
            axis = panel.x if display == "x" else panel.y
            if spec.is_discrete(data_aes):
                axis.kind = "discrete"
            elif spec.is_datetime(data_aes):
                axis.kind = "datetime"
            else:
                axis.kind = "continuous"
            label = spec.final_labels.get(data_aes)
            if label:
                axis.label = label

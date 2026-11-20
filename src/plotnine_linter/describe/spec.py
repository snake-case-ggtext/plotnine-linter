"""Spec adapter: read a plotnine ``ggplot`` object.

The user's plot is never mutated: we read the spec as written, then draw a
deep copy to get trained scales, built layer data, panel ranges and the
matplotlib figure for the render adapter.

This reads some plotnine internals (``layer._data``, ``ggplot.layout``) that
are not public API; tested against plotnine 0.13-0.15.
"""

from __future__ import annotations

import copy
import warnings
from typing import Any

import pandas as pd

from .model import PROBE_ERRORS, LayerSpec, SpecInfo


def is_ggplot(obj: Any) -> bool:
    try:
        from plotnine import ggplot
    except ImportError:
        return False
    return isinstance(obj, ggplot)


def _labels_dict(labels) -> dict[str, str]:
    try:
        items = vars(labels).items()
    except TypeError:
        items = dict(labels).items()
    out = {}
    for k, v in items:
        if v is None:
            continue
        out["color" if k == "colour" else k] = str(v)
    return out


def _mapping_dict(mapping) -> dict[str, str]:
    out = {}
    for k, v in dict(mapping).items():
        key = "color" if k == "colour" else k
        out[key] = v if isinstance(v, str) else str(v)
    return out


def _panel_ranges(built) -> list[dict[str, tuple[float, float]]]:
    ranges = []
    layout = getattr(built, "layout", None)
    for pp in getattr(layout, "panel_params", None) or []:
        entry = {}
        for view in (pp.x, pp.y):
            aes = (
                view.scale.aesthetics[0]
                if getattr(view, "scale", None) is not None
                else None
            )
            if aes in ("x", "y") and view.range is not None:
                entry[aes] = (float(view.range[0]), float(view.range[1]))
        ranges.append(entry)
    return ranges


def describe_plotnine(plot) -> tuple[SpecInfo, Any]:
    """Return the spec description and the figure drawn from a deep copy."""
    built = copy.deepcopy(plot)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        figure = built.draw()
        if not list(getattr(built, "scales", [])) or not getattr(
            getattr(built, "layout", None), "panel_params", None
        ):
            # plotnine < 0.14 draws from its own internal copy, leaving `built` untouched:
            # build a copy ourselves to get trained scales, layer data and panel ranges
            built = copy.deepcopy(plot)
            built._build()

    plot_mapping = _mapping_dict(plot.mapping)
    layers = []
    for i, (layer, blayer) in enumerate(zip(plot.layers, built.layers)):
        mapping = dict(plot_mapping) if getattr(layer, "inherit_aes", True) else {}
        mapping.update(_mapping_dict(layer.mapping))
        own = getattr(layer, "_data", None)
        raw = (
            own
            if isinstance(own, pd.DataFrame)
            else plot.data
            if isinstance(plot.data, pd.DataFrame)
            else None
        )
        built_data = (
            blayer.data
            if isinstance(getattr(blayer, "data", None), pd.DataFrame)
            else None
        )
        layers.append(
            LayerSpec(
                index=i,
                geom=type(layer.geom).__name__,
                stat=type(layer.stat).__name__,
                position=type(layer.position).__name__,
                mapping=mapping,
                geom_params=dict(getattr(layer.geom, "params", {}) or {}),
                stat_params=dict(getattr(layer.stat, "params", {}) or {}),
                aes_params=dict(getattr(layer.geom, "aes_params", {}) or {}),
                raw_data=raw,
                built_data=built_data,
                show_legend=getattr(layer, "show_legend", None),
            )
        )

    coord = plot.coordinates
    limits_ns = getattr(coord, "limits", None)
    coord_limits = {}
    if limits_ns is not None:
        coord_limits = {
            "x": getattr(limits_ns, "x", None),
            "y": getattr(limits_ns, "y", None),
        }

    facet = plot.facet
    free = getattr(facet, "free", None) or {"x": False, "y": False}

    try:
        legend_position = plot.theme.getp("legend_position")
    except PROBE_ERRORS:
        legend_position = None

    final_labels = _labels_dict(built.labels)
    expected_x = _labels_dict(plot.labels).get("x") or plot_mapping.get("x")
    if type(coord).__name__ == "coord_flip" and final_labels.get("x") != expected_x:
        # plotnine >= 0.14 swaps x/y labels to display orientation while drawing;
        # keep them keyed by data aesthetic
        fx, fy = final_labels.get("x"), final_labels.get("y")
        final_labels.pop("x", None), final_labels.pop("y", None)
        if fy is not None:
            final_labels["x"] = fy
        if fx is not None:
            final_labels["y"] = fx

    # plotnine < 0.14 fills plot.labels from the mapping as layers are added, so a label
    # that just repeats its mapping expression is a default, not something the user wrote
    user_labels = {
        k: v
        for k, v in _labels_dict(plot.labels).items()
        if v != plot_mapping.get(k) and not any(v == l.mapping.get(k) for l in layers)
    }

    spec = SpecInfo(
        plot=plot,
        built=built,
        mapping=plot_mapping,
        layers=layers,
        user_labels=user_labels,
        final_labels=final_labels,
        scales=list(built.scales),
        user_scales=list(plot.scales),
        facet_free={"x": bool(free.get("x")), "y": bool(free.get("y"))},
        facet_type=type(facet).__name__,
        coord=type(coord).__name__,
        coord_limits=coord_limits,
        panel_ranges=_panel_ranges(built),
        legend_position=legend_position,
    )
    return spec, figure

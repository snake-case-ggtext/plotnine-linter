"""Facts remembered across the figures of one notebook session.

Rules that compare figures (ST305, ST306) read ``desc.session``; ``lint()``
records each figure's facts after its rules run. The Jupyter hook keeps one
Session per notebook; pass your own to ``lint(..., session=...)`` elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from matplotlib.colors import to_hex
from .describe.model import scale_categories


@dataclass
class ChartFacts:
    label_colors: dict[str, str]  # legend category -> hex color
    theme: str  # plotnine theme class, or a matplotlib style signature
    font_size: float | None  # typical tick-label size, points


@dataclass
class Session:
    charts: list[ChartFacts] = field(default_factory=list)

    def add(self, facts: ChartFacts) -> None:
        self.charts.append(facts)

    def reset(self) -> None:
        self.charts.clear()


def _hex(color) -> str | None:
    try:
        return to_hex(color, keep_alpha=False)
    except (ValueError, TypeError):
        return None


def _legend_colors_mpl(legend) -> dict[str, str]:
    out = {}
    handles = getattr(legend, "legend_handles", None) or getattr(legend, "legendHandles", [])
    for handle, text in zip(handles, legend.get_texts()):
        color = None
        for getter in ("get_color", "get_facecolor"):
            fn = getattr(handle, getter, None)
            if fn is None:
                continue
            try:
                value = fn()
            except Exception:
                continue
            arr = np.asarray(value)
            color = _hex(arr[0] if arr.ndim == 2 and len(arr) else value)
            if color:
                break
        if color and text.get_text().strip():
            out[text.get_text().strip()] = color
    return out


def chart_facts(desc) -> ChartFacts:
    label_colors: dict[str, str] = {}
    theme = ""
    if desc.spec is not None:
        spec = desc.spec
        theme = type(spec.plot.theme).__name__ if getattr(spec.plot, "theme", None) is not None else "theme_gray"
        for aes in ("color", "fill"):
            if not spec.is_discrete(aes) or not any(aes in l.mapping for l in spec.layers):
                continue
            scale = spec.scale_for(aes)
            try:
                limits = scale_categories(scale)
                colors = scale.palette(len(limits))
                if isinstance(colors, dict):
                    colors = [colors.get(l) for l in limits]
                for lim, col in zip(limits, colors):
                    h = _hex(col)
                    if h:
                        label_colors[lim] = h
            except Exception:
                continue
    elif desc.render is not None:
        for p in desc.render.panels:
            if p.legend is not None:
                label_colors.update(_legend_colors_mpl(p.legend))
        ax = desc.render.panels[0].ax if desc.render.panels else None
        if ax is not None:
            grid = any(l.get_visible() for l in ax.get_xgridlines() + ax.get_ygridlines())
            theme = f"face={_hex(ax.get_facecolor())}, grid={'on' if grid else 'off'}"
    sizes = [t.fontsize for t in (desc.render.texts if desc.render else []) if t.role in ("xtick", "ytick")]
    return ChartFacts(label_colors=label_colors, theme=theme, font_size=float(np.median(sizes)) if sizes else None)

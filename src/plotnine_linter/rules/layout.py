"""LY: layout, legends, overlap, text size."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from ..registry import Hit, rule
from ._util import overlaps, quote
from ..describe.model import scale_categories


# ---------------------------------------------------------------- LY101
@rule("LY101")
def ly101(desc, cfg):
    if desc.render is None:
        return
    reported = set()
    for panel in desc.render.panels:
        for which, axis in (("x", panel.x), ("y", panel.y)):
            if which in reported or len(axis.tick_labels) < 2:
                continue
            if any(abs(((t.rotation + 180) % 360) - 180) > 1 for t in axis.tick_labels):
                continue  # rotated labels: AX202 reports them, and their bounding boxes overlap anyway
            key = (lambda t: t.bbox.x0) if which == "x" else (lambda t: t.bbox.y0)
            boxes, seen_spots = [], set()
            for t in sorted(axis.tick_labels, key=key):
                spot = (t.text, round(t.bbox.x0), round(t.bbox.y0))
                if spot not in seen_spots:  # duplicates drawn at the same spot read as one label
                    seen_spots.add(spot)
                    boxes.append(t)
            clashes = [(a, b) for a, b in zip(boxes, boxes[1:]) if overlaps(a.bbox, b.bbox, tol=-2.0, along=which)]
            if clashes:
                reported.add(which)
                a, b = clashes[0]
                if axis.kind == "datetime":
                    fix = (
                        "Use wider `date_breaks` in `scale_x_datetime()` (fewer labels) and a shorter "
                        "`date_labels` format such as `'%Y'` or `\"%b '%y\"`."
                        if desc.source == "plotnine"
                        else "Use `mdates.ConciseDateFormatter` or fewer ticks (`ax.xaxis.set_major_locator(...)`)."
                    )
                else:
                    fix = (
                        "Swap axes with `coord_flip()` so labels read horizontally; otherwise fewer "
                        "breaks or shorter labels. Rotation isn't a fix (see AX202)."
                        if desc.source == "plotnine"
                        else "Swap axes (`barh`, or exchange x and y) so labels read horizontally; "
                        "otherwise fewer ticks or shorter labels. Rotation isn't a fix (see AX202)."
                    )
                yield Hit(
                    f"{len(clashes)} pair(s) of {which}-axis tick labels overlap "
                    f"(e.g. '{quote(a.text, 16)}' and '{quote(b.text, 16)}').",
                    fix=fix,
                    source="render",
                    panel=panel.index,
                )


# ---------------------------------------------------------------- LY102
def _data_points_display(panel) -> np.ndarray:
    ax = panel.ax
    pts = []
    for s in panel.series:
        if s.kind in ("line", "scatter") and s.x is not None and s.y is not None:
            xy = np.column_stack([s.x, s.y])
            pts.append(xy[~np.isnan(xy).any(axis=1)])
        elif s.kind == "bar":
            for rect in s.artist.patches:
                bb = rect.get_bbox()
                corners = np.array([[bb.x0, bb.y0], [bb.x1, bb.y1], [bb.x0, bb.y1], [bb.x1, bb.y0],
                                    [(bb.x0 + bb.x1) / 2, bb.y1]])
                pts.append(corners)
    display = [ax.transData.transform(np.vstack(pts))] if pts else []
    from matplotlib.patches import Wedge

    for patch in ax.patches:
        if isinstance(patch, Wedge) and patch.get_visible():
            verts = patch.get_path().vertices
            display.append(patch.get_transform().transform(verts[:: max(1, len(verts) // 24)]))
    if not display:
        return np.empty((0, 2))
    return np.vstack(display)


@rule("LY102")
def ly102(desc, cfg):
    if desc.render is None:
        return
    renderer = desc.render.renderer
    for panel in desc.render.panels:
        boxes = []
        if panel.legend is not None:
            boxes.append(panel.legend.get_window_extent(renderer))
        boxes += list(desc.render.legend_bboxes)
        if not boxes:
            continue
        pts = _data_points_display(panel)
        if not len(pts):
            continue
        for bb in boxes:
            inside = (pts[:, 0] > bb.x0 + 2) & (pts[:, 0] < bb.x1 - 2) & (pts[:, 1] > bb.y0 + 2) & (pts[:, 1] < bb.y1 - 2)
            if inside.any():
                fix = (
                    "Move it outside: `theme(legend_position='right')`, or label lines directly."
                    if desc.source == "plotnine"
                    else "Move it outside: `ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1))`, "
                    "or label series directly with `ax.annotate`."
                )
                yield Hit(
                    f"The legend sits on top of {int(inside.sum())} data point(s).",
                    fix=fix,
                    source="render",
                    panel=panel.index,
                )
                return


# ---------------------------------------------------------------- LY201
@rule("LY201")
def ly201(desc, cfg):
    if desc.render is None:
        return
    min_pt = float(cfg.t("min_font_pt"))
    small = defaultdict(list)
    for t in desc.render.texts:
        if t.fontsize < min_pt:
            small[t.role].append(t)
    if small:
        smallest = min(t.fontsize for ts in small.values() for t in ts)
        roles = ", ".join(sorted(small))
        fix = (
            "`+ theme(text=element_text(size=11))` or a larger `base_size` in the theme, e.g. `theme_bw(base_size=12)`."
            if desc.source == "plotnine"
            else "`plt.rcParams['font.size'] = 11`, or pass `fontsize=` to the label calls."
        )
        yield Hit(
            f"Some text is {smallest:.1f} pt, below {min_pt:g} pt ({roles}).",
            fix=fix,
            source="render",
        )


# ---------------------------------------------------------------- LY202
def _order_mismatch(legend_order: list[str], end_values: dict[str, float]) -> bool:
    keys = [k for k in legend_order if k in end_values]
    if len(keys) < 3:
        return False
    by_end = sorted(keys, key=lambda k: -end_values[k])
    return keys != by_end


@rule("LY202")
def ly202(desc, cfg):
    if desc.spec is not None:
        spec = desc.spec
        if desc.render is not None and not desc.render.has_legend:
            return
        for layer in spec.layers:
            if layer.geom not in ("geom_line", "geom_path") or "color" not in layer.mapping:
                continue
            col, xcol, ycol = (spec.column(layer, a) for a in ("color", "x", "y"))
            if col is None or xcol is None or ycol is None or not spec.is_discrete("color"):
                continue
            scale = spec.scale_for("color")
            try:
                legend_order = scale_categories(scale)
            except Exception:
                continue
            df = layer.raw_data.assign(_c=col.astype(str))
            last = df.sort_values(layer.mapping["x"]).groupby("_c")[layer.mapping["y"]].last()
            if _order_mismatch(legend_order, last.to_dict()):
                name = layer.mapping["color"]
                yield Hit(
                    f"The legend lists `{name}` as {', '.join(legend_order[:4])}…, but the lines end in "
                    "a different top-to-bottom order.",
                    fix=f"Make `{name}` a Categorical ordered by each line's last value (highest first), "
                    "or label line ends with `geom_text` and drop the legend.",
                )
                return
        return

    for panel in desc.render.panels:
        if panel.legend is None:
            continue
        lines = {s.label: s for s in panel.of_kind("line") if s.x is not None and s.y is not None}
        ends = {}
        for label, s in lines.items():
            ok = ~(np.isnan(s.x) | np.isnan(s.y))
            if ok.any():
                ends[label] = float(s.y[ok][np.argmax(s.x[ok])])
        if _order_mismatch(panel.legend_labels, ends):
            yield Hit(
                "Legend entries are not in the same top-to-bottom order as the line ends.",
                fix="Reorder handles: `h, l = ax.get_legend_handles_labels()` then pass them sorted by "
                "last value to `ax.legend(...)`; or label line ends with `ax.annotate`.",
                source="render",
                panel=panel.index,
            )
            return


# ---------------------------------------------------------------- LY103
def _text_background(desc, box):
    """The color behind a piece of text: a legend frame, the panel it sits in, or the figure."""
    import matplotlib.colors as mcolors

    fig = desc.render.figure
    cx, cy = (box.bbox.x0 + box.bbox.x1) / 2, (box.bbox.y0 + box.bbox.y1) / 2
    if box.role == "legend" and box.panel is not None:
        legend = desc.render.panels[box.panel].legend
        frame = legend.get_frame() if legend is not None else None
        if frame is not None and frame.get_visible() and frame.get_facecolor()[3] >= 0.5:
            return mcolors.to_rgb(frame.get_facecolor())
    for panel in desc.render.panels:
        bb = panel.ax.get_window_extent(desc.render.renderer)
        if bb.x0 <= cx <= bb.x1 and bb.y0 <= cy <= bb.y1:
            fc = panel.ax.get_facecolor()
            if fc[3] >= 0.5:
                return mcolors.to_rgb(fc)
    bbox_patch = box.artist.get_bbox_patch() if box.artist is not None else None
    if bbox_patch is not None and bbox_patch.get_facecolor()[3] >= 0.5:
        return mcolors.to_rgb(bbox_patch.get_facecolor())
    return mcolors.to_rgb(fig.get_facecolor())


def _rendered_background(image, box):
    """Most common pixel color in the text's box on the rendered figure (the background)."""
    if image is None:
        return None
    h, w = image.shape[:2]
    x0, x1 = int(max(box.bbox.x0, 0)), int(min(box.bbox.x1, w))
    y0, y1 = int(max(h - box.bbox.y1, 0)), int(min(h - box.bbox.y0, h))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    patch = image[y0:y1, x0:x1, :3].reshape(-1, 3)
    colors, counts = np.unique(patch, axis=0, return_counts=True)
    text = np.asarray(box.color[:3]) if box.color is not None else None
    for i in np.argsort(-counts):
        c = colors[i] / 255.0
        if text is None or np.abs(c - text).max() > 0.08:  # skip the glyphs themselves
            return tuple(c)
    return None


@rule("LY103")
def ly103(desc, cfg):
    if desc.render is None:
        return
    from ..colors import blend, contrast_ratio

    try:
        image = np.asarray(desc.render.figure.canvas.buffer_rgba())
    except Exception:
        image = None
    min_normal = float(cfg.t("min_text_contrast"))
    worst = None
    for box in desc.render.texts:
        if box.color is None:
            continue
        bg = _rendered_background(image, box) or _text_background(desc, box)
        fg = blend(box.color[:3], bg, box.color[3] if len(box.color) > 3 else 1.0)
        cr = contrast_ratio(fg, bg)
        bold = str(box.weight).lower() in ("bold", "heavy", "black", "semibold", "demibold", "700", "800", "900")
        large = box.fontsize >= 18 or (box.fontsize >= 14 and bold)
        need = 3.0 if large else min_normal
        if cr < need and (worst is None or cr < worst[0]):
            worst = (cr, need, box, bg)
    if worst:
        cr, need, box, bg = worst
        from matplotlib.colors import to_hex

        yield Hit(
            f"Text '{quote(box.text, 24)}' ({box.role}) has a contrast of {cr:.1f}:1 against its background; "
            f"it needs {need:g}:1.",
            fix=(
                "Darken it, e.g. `theme(text=element_text(color='#222222'))`, or lighten what is behind it."
                if desc.source == "plotnine"
                else "Darken it (`color='#222222'`), or lighten what is behind it."
            ),
            source="render",
            panel=box.panel,
            details={"contrast": round(cr, 2), "background": to_hex(bg)},
        )

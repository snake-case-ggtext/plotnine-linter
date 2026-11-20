"""ST: style (tier 3, opt-in). Taste, not correctness."""

from __future__ import annotations

import re

from ..registry import Hit, rule


@rule("ST301")
def st301(desc, cfg):
    if desc.spec is not None:
        if not desc.spec.user_labels.get("title"):
            yield Hit(
                "The plot has no title.",
                fix="`+ labs(title='What the reader should take away')`",
            )
        return
    fig = desc.render.figure
    suptitle = getattr(fig, "_suptitle", None)
    has = (suptitle is not None and suptitle.get_text().strip()) or any(
        p.ax.get_title().strip() for p in desc.render.panels
    )
    if not has:
        yield Hit(
            "The figure has no title.",
            fix="`ax.set_title('...')` or `fig.suptitle('...')`",
            source="render",
        )


@rule("ST303")
def st303(desc, cfg):
    if desc.spec is not None:
        for layer in desc.spec.layers:
            if (
                layer.geom in ("geom_line", "geom_path")
                and "color" in layer.mapping
                and layer.built_data is not None
            ):
                n = (
                    layer.built_data["group"].nunique()
                    if "group" in layer.built_data
                    else 0
                )
                if 2 <= n <= 4 and desc.render.has_legend:
                    yield Hit(
                        f"{n} lines are matched to a legend.",
                        fix="Label line ends with `geom_text` on the last point per group, then "
                        "`+ theme(legend_position='none')`.",
                    )
                    return
        return
    for panel in desc.render.panels:
        if panel.legend is not None and 2 <= len(panel.of_kind("line")) <= 4:
            yield Hit(
                f"{len(panel.of_kind('line'))} lines are matched to a legend.",
                fix="Annotate each line end with `ax.annotate(...)` and remove the legend.",
                source="render",
                panel=panel.index,
            )
            return


_DECIMALS = re.compile(r"\.(\d+)")


@rule("ST307")
def st307(desc, cfg):
    for panel in desc.render.panels:
        for which, axis in (("x", panel.x), ("y", panel.y)):
            decimals = [
                len(m.group(1))
                for t in axis.tick_labels
                for m in [_DECIMALS.search(t.text)]
                if m
            ]
            if decimals and min(decimals) >= 3:
                yield Hit(
                    f"{which}-axis tick labels show {min(decimals)}+ decimal places.",
                    fix="Round tick labels, e.g. `scale_y_continuous(labels=lambda v: [f'{x:.1f}' for x in v])`"
                    if desc.source == "plotnine"
                    else "`ax.yaxis.set_major_formatter('{x:.1f}')`",
                    source="render",
                    panel=panel.index,
                )
                return


@rule("ST305")
def st305(desc, cfg):
    session = getattr(desc, "session", None)
    if session is None or not session.charts:
        return
    from ..session import chart_facts

    current = chart_facts(desc).label_colors
    for label, color in current.items():
        for i, earlier in enumerate(session.charts, start=1):
            before = earlier.label_colors.get(label)
            if before and before != color:
                yield Hit(
                    f"'{label}' is {color} here but was {before} in figure {i} of this notebook.",
                    fix="Make one mapping, e.g. `palette = {'"
                    + label
                    + "': '"
                    + before
                    + "', ...}`, and pass it to "
                    "every plot (`scale_color_manual(values=palette)` / `palette=palette` in seaborn).",
                    source="render",
                )
                return


@rule("ST306")
def st306(desc, cfg):
    session = getattr(desc, "session", None)
    if session is None or not session.charts:
        return
    from ..session import chart_facts

    now, first = chart_facts(desc), session.charts[0]
    if now.theme and first.theme and now.theme != first.theme:
        yield Hit(
            f"This figure's theme ({now.theme}) differs from the first figure's ({first.theme}).",
            fix="Set it once at the top: `theme_set(theme_minimal())` (plotnine) or `sns.set_theme(...)` / "
            "`plt.style.use(...)` (matplotlib).",
            source="render",
        )
    elif (
        now.font_size
        and first.font_size
        and abs(now.font_size - first.font_size) >= 1.5
    ):
        yield Hit(
            f"Tick labels here are {now.font_size:.1f} pt; in the first figure they were {first.font_size:.1f} pt.",
            fix="Set the base font size once, e.g. `theme_set(theme_gray(base_size=12))` or "
            "`plt.rcParams['font.size'] = 12`.",
            source="render",
        )

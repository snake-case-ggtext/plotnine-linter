# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "pandas",
#     "plotnine",
#     "plotnine-linter[plotnine]",
# ]
#
# [tool.uv.sources]
# plotnine-linter = { path = "..", editable = true }
# ///
# marimo ends every cell with a `return`, even an empty one.
# ruff: noqa: PLR1711
"""A two-minute plotnine-linter demo, as a marimo notebook.

Run it from the repository root:

    uvx marimo edit --sandbox examples/demo_marimo.py

The sandbox installs marimo and plotnine-linter from this checkout.
"""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    from plotnine import (
        aes,
        coord_cartesian,
        coord_flip,
        element_text,
        geom_col,
        ggplot,
        labs,
        theme,
    )

    from plotnine_linter import alt_text, audit, lint

    regions = pd.DataFrame(
        {
            "region_name": ["West", "East", "South", "North", "Central"],
            "avg_income_usd": [52, 61, 47, 58, 50],
        }
    )

    def side_by_side(heading, p, report):
        """Show a heading, then the chart with its findings beside it."""
        return mo.vstack(
            [
                mo.md(f"## {heading}"),
                mo.hstack([p, report], widths="equal", align="start"),
            ]
        )

    return (
        aes,
        alt_text,
        audit,
        coord_cartesian,
        coord_flip,
        element_text,
        geom_col,
        ggplot,
        labs,
        lint,
        mo,
        regions,
        side_by_side,
        theme,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # plotnine-linter

    It flags charts that mislead or that readers can't read. Each finding comes with a fix.
    """)
    return


@app.cell
def _(aes, coord_cartesian, geom_col, ggplot, lint, regions, side_by_side):
    draft = (
        ggplot(regions, aes("region_name", "avg_income_usd", fill="region_name"))
        + geom_col()
        + coord_cartesian(ylim=(40, 65))
    )
    side_by_side("A typical first draft", draft, lint(draft))
    return


@app.cell
def _(aes, coord_flip, geom_col, ggplot, labs, lint, regions, side_by_side):
    fixed = (
        ggplot(regions, aes("reorder(region_name, avg_income_usd)", "avg_income_usd"))
        + geom_col(fill="#0072B2")
        + coord_flip()
        + labs(
            x="Region",
            y="Average income (USD, thousands)",
            title="East earns the most; South the least",
        )
    )
    side_by_side("After the fixes", fixed, lint(fixed))
    return (fixed,)


@app.cell
def _(mo):
    rules = mo.ui.dropdown(
        options={
            "Default rules": {},
            "Accessibility profile": {"profile": "accessibility"},
        },
        value="Default rules",
        label="Rules",
    )
    larger_text = mo.ui.switch(label="Text at 11 pt")
    mo.vstack(
        [
            mo.md("## Stricter rules"),
            mo.md("The accessibility profile uses WCAG and Chartability thresholds."),
            mo.hstack([rules, larger_text], justify="start", gap=2),
        ]
    )
    return larger_text, rules


@app.cell
def _(element_text, fixed, larger_text, lint, rules, side_by_side, theme):
    chart = (fixed + theme(text=element_text(size=11))) if larger_text.value else fixed
    side_by_side(rules.selected_key, chart, lint(chart, **rules.value))
    return (chart,)


@app.cell
def _(alt_text, audit, chart, mo):
    mo.vstack(
        [
            mo.md("## Alt text and an accessibility audit"),
            mo.callout(mo.md(f"**Draft alt text:** {alt_text(chart)}"), kind="info"),
            mo.accordion({"Chartability audit": audit(chart)}),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Read more

    - In Jupyter, `%load_ext plotnine_linter` lints every plot as it appears.
    - [Getting started](https://github.com/snake-case-ggtext/plotnine-linter/blob/main/docs/getting-started.md)
    - [Rule catalog](https://github.com/snake-case-ggtext/plotnine-linter/blob/main/docs/rules.md)
    - [Gallery of broken and fixed charts](https://github.com/snake-case-ggtext/plotnine-linter/blob/main/docs/gallery.md)
    """)
    return


if __name__ == "__main__":
    app.run()

# How it works

## One description, two adapters

Every rule reads one shared chart description (`describe/model.py`). Two adapters fill it in:

- **The spec adapter (plotnine).** It reads intent from the `ggplot` object: mappings, geoms, stats, scales, facets and labels. It never changes the user's plot. It draws a deep copy to get the trained scales and the built layer data.
- **The render adapter (any matplotlib figure).** It reads what the reader sees: labels, font sizes, legends, colors and points. plotnine figures pass through it too, so the overlap, text-size, overplotting and legend rules apply to both libraries.

A rule that needs the spec skips plain matplotlib figures. A rule that crashes never breaks the user's plot. The report records the error in `report.internal_errors`.

`describe(obj)` returns the description, which helps when you write or debug a rule.

## The catalog is data

The IDs, tiers, titles, why and fix text, thresholds, profiles and Chartability and WCAG tags live in `src/plotnine_linter/data/rules.json`. An R (ggplot2) implementation could share the same IDs and wording.

IDs are permanent. A rule that changes tier gets a different ID, and the catalog retires the first one. For example, CL103 became CL201, and LB202 became LB301. The third character of an ID is its tier.

## Notebook output

The HTML output reads well in light and dark themes. Text takes the theme's color, and backgrounds are translucent tints. Each severity shows as a solid pill with white text and its name, so color is never the only cue.

## Where things live

```
src/plotnine_linter/
  data/rules.json   the shared catalog
  describe/         model.py (the shared description), spec.py, render.py
  rules/            axes.py, color.py, labels.py, layout.py, marks.py, style.py
  api.py            lint()
  audit.py          audit(), data_table()
  alttext.py        alt_text()
  readability.py    reading grade and abbreviations, for the audit
  catalog.py        show_rules()
  config.py         pyproject.toml settings and profiles
  colors.py         color-vision simulation (Machado 2009), CIEDE2000, WCAG contrast
  jupyter.py        %load_ext and %plotlint
  notebook.py       check_notebook(), behind `plotnine-linter check` and `audit`
  session.py        memory across the figures of a notebook (ST305, ST306)
  suppress.py       # plotlint: ignore[...] comments
```

## Known limits

- The spec adapter reads plotnine internals (`layer._data`, `ggplot.layout`, `_build()`) that aren't public API. Pin plotnine in a course environment.
- plotnine has no `coord_polar` and no secondary axes. So MK201 (pies) and AX102 (dual axes) apply to matplotlib only.
- For plain matplotlib, the linter can't tell nominal categories from ordinal ones. It skips labels that look ordinal (months, weekdays, Likert levels, numeric bins). For other ordered labels, suppress the rule with a reason.
- After a notebook shows a plotnine plot, plotnine leaves matplotlib in non-interactive mode. Later plain matplotlib cells then need `plt.show()` to display. This happens without the linter too, and the linter catches figures shown either way.
- Linting a plotnine plot draws a copy of it, which adds about 0.2 to 0.6 s per plot.
- The linter doesn't check whether the chart type fits the question. It also can't tell whether the data is right or the range is cherry-picked.

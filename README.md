# plotnine-linter

A teaching-first linter for charts made with **plotnine** and **matplotlib** (including pandas and seaborn plots, which draw with matplotlib).

It flags charts that mislead or can't be read, explains why in a sentence, and suggests a fix in the library the student is using. It is strongly opinionated only where a chart is objectively misleading or unreadable; anything about taste is opt-in.

```
AX101 error: `geom_col` draws bars from zero, but the value axis shows 38.8 to 66.2, so bar lengths are not proportional.
    fix: Drop `ylim()`, `coord_cartesian(ylim=...)` or the scale `limits=` so the bars start at zero; if the zoom matters, use `geom_point()` or `geom_line()`.
LB201 warning: The y-axis is labeled `avg_income_usd`, the raw variable name.
    fix: `+ labs(y='Avg income (USD)')`
```

> **Status: prototype (v0.1).** 41 rules. Tested on Python 3.11–3.13 with plotnine 0.13–0.15, matplotlib 3.8–3.11 and seaborn 0.13. Calibrated against public COGS 108 final projects (see [docs/CALIBRATION.md](docs/CALIBRATION.md)).

## Install

From this folder:

```bash
pip install -e ".[plotnine]"      # add ",dev" for pytest, IPython, seaborn and notebook checking
```

## Use it

### In Jupyter

Load once; every plot after that is linted as it appears. Findings show under the plot, with a fix and a collapsible *Why it matters*.

```python
%load_ext plotnine_linter
```

```python
%plotlint summary          # every plot linted so far in this notebook, with its findings
%plotlint rules            # the rule catalog: %plotlint rules 1, %plotlint rules AX
%plotlint profile accessibility   # Chartability/WCAG rules at their published thresholds
%plotlint audit            # Chartability audit of the last plot; add --markdown for a checklist
%plotlint off | on | status | reset
%plotlint select=tier1,tier2,ST301
%plotlint ignore=AX203
```

### In code

```python
from plotnine_linter import lint, alt_text, show_rules

report = lint(p)          # a plotnine ggplot, or a matplotlib Figure / Axes
print(report)
report.ids                # ['AX201', 'LB201', ...]
report.errors()           # error-level findings only
report.to_json()          # for autograders
report.alt_text           # a draft alt text, also available as alt_text(p)

show_rules()              # the catalog, grouped by tier, showing which rules are on
show_rules().to_frame()   # as a pandas DataFrame
```

`alt_text(p)` drafts a description from the chart itself, e.g. *"Bar chart of Average income (USD, thousands) by Region. Highest: East (61); lowest: South (47)."* It's a starting point; the author adds the takeaway.

### Accessibility audit

```python
from plotnine_linter import audit, data_table

audit(p)                     # every Chartability test that applies to a static chart, with a verdict
print(audit(p).to_markdown())  # a checklist to paste into a markdown cell and answer
data_table(p)                # the data behind the chart, as a DataFrame
```

`lint()` reports only problems. `audit()` goes through all 50 [Chartability](https://chartability.github.io/POUR-CAF/) tests and marks each one **pass** or **fail** (decided by the rules), **partly checked** (the linter gathers evidence, such as a draft alt text, the chart's reading grade or undefined abbreviations, and asks the author a question), **your call** (only the author can decide; the audit asks), or **n/a** (interactive and web tests). The markdown checklist pre-checks the automatic passes and pre-fills the draft alt text for the author to edit.

### In an autograder or test suite

```python
from plotnine_linter.testing import assert_clean

assert_clean(student_plot)                     # fails on any error-level finding
assert_clean(student_plot, at_least="warning")
```

### From the command line

Run notebooks or scripts and lint every plot they make (exit code 1 if any error):

```bash
plotnine-linter check project.ipynb                    # cells that fail (e.g. missing data) are skipped
plotnine-linter check projects/*.ipynb --format json --save-images lint_images/
plotnine-linter check analysis.py
plotnine-linter audit project.ipynb                    # a markdown accessibility checklist per plot
plotnine-linter audit projects/*.ipynb --check-answers # graders: checklist items students left open
plotnine-linter rules --markdown > docs/RULES.md
```

`--check-answers` doesn't run the notebook. It reads the checklists pasted into markdown cells and reports unchecked boxes, checked questions with an empty `Answer:` line, and alt text left exactly as drafted (exit code 1 if anything is open).

## Rules

Three tiers, encoded in the ID: `AX101` = axes, tier 1. Tiers 1 and 2 run by default.

| Tier | Severity | Default | Rules |
| --- | --- | --- | --- |
| 1 Errors | error | on | AX101 truncated bars · AX102 dual y-axes · AX103 log scale drops data · CL101 rainbow colormap · CL102 too many colors · LB101 unlabeled numeric axis · LY101 overlapping tick labels · LY102 legend covers data · LY103 low-contrast text · MK101 overplotting · MK102 3D bars · MK103 line through unordered categories |
| 2 Clarity | warning | on | AX201 unsorted bars · AX202 rotated category labels · AX203 free facet scales · AX204 default histogram bins · AX205 months/weekdays/ratings in alphabetical order · AX206 log values on a linear axis *(heuristic)* · AX207 fractional ticks on whole numbers · CL201 colors confusable with color-vision deficiency · CL202 diverging data on a sequential scale · CL203 color that encodes nothing · CL204 low-contrast marks · LB201 raw variable names in labels, titles, facets · LB203 redundant legend · LB205 label doesn't match the values *(heuristic)* · LB206 scientific offset (1e8) · LY201 text too small · LY202 legend order ≠ line order · MK201 pie with many slices · MK202 spaghetti lines · MK203 summary bars without uncertainty · MK204 box plot hiding small groups · MK205 many stacked segments |
| 3 Style | info | opt-in | CL301 color is the only cue (grayscale) · LB301 no units *(heuristic)* · ST301 no title · ST303 direct labels would beat a legend · ST305 same category, different colors across figures · ST306 inconsistent themes across figures · ST307 excess tick precision |

- [docs/RULES.md](docs/RULES.md): the full catalog with the why and fix for each rule.
- [docs/GALLERY.md](docs/GALLERY.md): a before/after example for every rule.
- [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md): how the rules map to Chartability and WCAG, and the accessibility profile.
- [docs/CALIBRATION.md](docs/CALIBRATION.md): how often each rule fired on public COGS 108 projects, and what changed as a result.

Rules that can't be certain (marked *heuristic*) are always reported as **info**, whatever their tier. ST305 and ST306 compare figures within one notebook; the Jupyter hook remembers earlier figures for them. Empty figures (a cell that made axes, then failed before plotting) are skipped.

**Accessibility profile.** `profile = "accessibility"` (or `%plotlint profile accessibility`, or `lint(p, profile="accessibility")`) turns on every rule tied to a Chartability test or WCAG criterion and uses their published thresholds: 3:1 contrast for marks and at least 9 pt text. See [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md).

## Breaking a rule on purpose

Add a comment next to the plot (in a notebook cell or a script) that says why:

```python
# plotlint: ignore[AX201] survey questions are listed in the order they were asked
```

or pass it in code: `lint(p, suppress={"AX201": "order is meaningful"})`. A suppression without a reason still works, but the report adds an info note (`SUP001`) asking for one.

## Configure

Settings come from the nearest `pyproject.toml`, so an instructor can ship one with course materials and every student sees the same rules:

```toml
[tool.plotnine-linter]
select = ["tier1", "tier2", "ST301"]   # tiers, area prefixes (AX, CL, ...) or rule IDs
ignore = ["AX203"]
profile = "accessibility"              # optional preset
severity = { LB301 = "warning" }

[tool.plotnine-linter.thresholds]
max_pie_slices = 4
max_lines = 7
```

All thresholds, with their defaults and the rule each affects, are listed in `src/plotnine_linter/data/rules.json`. The same keywords work in code: `lint(p, select=[...], ignore=[...], severity={...}, thresholds={...})`.

## How it works

Two adapters fill in one shared chart description; every rule reads only that description.

- **Spec adapter (plotnine).** Reads intent from the `ggplot` object: mappings, geoms, stats, scales, facets, labels. It never mutates the user's plot; it builds a deep copy to get trained scales and built layer data.
- **Render adapter (any matplotlib figure).** Reads what the reader sees from the drawn figure: tick-label boxes, font sizes, legends, colors, point positions. plotnine figures pass through it too, so overlap, text-size, overplotting and legend rules apply to both libraries.

Rules that need spec facts skip silently for plain matplotlib. A rule that crashes never breaks the user's plot; the error is recorded in `report.internal_errors`.

**The rule catalog is data.** IDs, tiers, titles, why/fix text and thresholds live in `src/plotnine_linter/data/rules.json`, so a future R (ggplot2) implementation can share the same IDs and wording. IDs are permanent: a rule that changes tier gets a new ID and the old one is retired (CL103 became CL201; LB202 became LB301). Profiles and Chartability/WCAG tags live there too.

**Notebook output works in light and dark themes**: text inherits the theme's color, backgrounds are translucent, and severity is a solid pill with white text plus its name.

```
src/plotnine_linter/
  data/rules.json   the shared catalog
  describe/         model.py (the shared description) · spec.py · render.py
  rules/            axes.py · color.py · labels.py · layout.py · marks.py · style.py
  api.py            lint()              notebook.py   check_notebook() / CLI
  jupyter.py        %load_ext, %plotlint  session.py    memory across figures
  alttext.py        alt_text()          catalog.py    show_rules()
  audit.py          audit(), data_table()  readability.py  reading grade, abbreviations
  config.py         pyproject.toml      colors.py     CVD simulation (Machado 2009) + CIEDE2000
```

Adding a rule: add its entry (ID, tier, title, why, fix) to `rules.json`, then write the check:

```python
@rule("MK206")
def mk206(desc, cfg):
    if desc.spec is None:
        return
    for layer in desc.spec.layers:
        if ...:
            yield Hit("What is wrong, specifically.", fix="Code that fixes it.")
```

…and add a before/after pair to `docs/gallery/make_gallery.py` (the gallery build fails if any rule lacks one).

## Known limits

- The spec adapter reads plotnine internals (`layer._data`, `ggplot.layout`, `_build()`) that aren't public API; pin plotnine versions in a course environment.
- plotnine has no `coord_polar` or secondary axes, so MK201 (pies) and AX102 (dual axes) are matplotlib-only.
- For plain matplotlib, the linter can't tell nominal from ordinal categories. It skips labels that look ordinal (months, weekdays, Likert levels, numeric bins) and otherwise asks for a suppression.
- In Jupyter, after a plotnine plot is displayed, plotnine leaves matplotlib in non-interactive mode, so later plain matplotlib cells need `plt.show()` to display (this happens without the linter too). The linter catches figures shown either way.
- Linting a plotnine plot draws it a second time (from a copy), so it adds about 0.2–0.6 s per plot.
- Not checked: whether the chart type fits the question, whether the data is right, cherry-picked ranges.

## Develop

```bash
pip install -e ".[dev]"
pytest                               # -m "not slow" skips the Jupyter kernel tests
python docs/gallery/make_gallery.py --strict    # rebuild the gallery; fails if any example breaks
```

`.github/workflows/tests.yml` runs the tests on the oldest and newest supported plotnine/matplotlib versions and checks that `docs/RULES.md` is current. `examples/demo.ipynb` walks through the main rules.

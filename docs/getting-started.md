# Getting started

## Install

plotnine-linter isn't on PyPI yet. Install it from GitHub:

```bash
pip install "plotnine-linter[plotnine] @ git+https://github.com/snake-case-ggtext/plotnine-linter"
```

Leave out `[plotnine]` if you only lint matplotlib, pandas and seaborn figures.

## In Jupyter

Load the extension once per notebook:

```python
%load_ext plotnine_linter
```

After that, the linter checks every plot when the notebook shows it. That includes plots shown with `plt.show()` and `p.show()`. The findings appear under the plot, each with a fix and a collapsible *Why it matters*. The output reads well in light and dark themes.

The `%plotlint` magic controls the linter:

```python
%plotlint summary                  # every plot linted since the last reset, with its findings
%plotlint rules                    # the rule catalog; also %plotlint rules 1, %plotlint rules AX, %plotlint rules a11y
%plotlint audit                    # Chartability audit of the last plot
%plotlint audit p --markdown       # the audit of p, as a checklist to paste into a markdown cell
%plotlint profile accessibility    # Chartability and WCAG rules at their published thresholds
%plotlint profile none             # back to the defaults
%plotlint select=tier1,tier2,ST301 # choose rules by tier, area prefix or ID
%plotlint ignore=AX203
%plotlint off                      # pause
%plotlint on                       # resume
%plotlint status                   # show the current options
%plotlint reset                    # clear the options, the summary and the memory of earlier figures
```

ST305 and ST306 compare a figure with the earlier figures in the notebook. The extension remembers those figures for them.

## In code

```python
from plotnine_linter import lint

report = lint(p)  # a plotnine ggplot, or a matplotlib Figure or Axes
print(report)
report.ids  # ['AX201', 'LB201', ...]
report.errors()  # the error-level findings
report.to_json()  # for autograders
report.alt_text  # a draft alt text; also alt_text(p)
```

`lint()` takes the same settings as `pyproject.toml`: `select`, `ignore`, `severity`, `thresholds`, `profile` and `suppress`. See [Configuration](configuration.md).

`show_rules()` shows the catalog in a notebook, and `show_rules().to_frame()` gives it as a DataFrame.

## Accessibility audit

```python
from plotnine_linter import audit, data_table

audit(p)  # a verdict for every Chartability test that applies
print(audit(p).to_markdown())  # a checklist to paste under the chart and answer
data_table(p)  # the data behind the chart, as a DataFrame
```

[Accessibility](accessibility.md) explains the verdicts and the evidence the audit gathers.

## In an autograder or a test suite

```python
from plotnine_linter.testing import assert_clean

assert_clean(student_plot)  # fails on any error-level finding
assert_clean(student_plot, at_least="warning")
```

## From the command line

`plotnine-linter check` runs notebooks or scripts and lints every plot they make. It exits with code 1 if any plot has an error.

```bash
plotnine-linter check project.ipynb
plotnine-linter check projects/*.ipynb --format json --save-images lint_images/
plotnine-linter check analysis.py
```

The notebook runs in a fresh kernel, in its own folder. If a cell fails, for example on a missing data file, the run records the error and continues. The notebook file stays as it was.

`plotnine-linter audit` writes an accessibility checklist for every plot in a notebook. With `--check-answers`, it doesn't run anything. Instead it reads the checklists that students pasted into markdown cells. Then it lists what is still open: unchecked boxes, empty answers, and alt text left exactly as drafted.

```bash
plotnine-linter audit project.ipynb
plotnine-linter audit projects/*.ipynb --check-answers
plotnine-linter rules --markdown
```

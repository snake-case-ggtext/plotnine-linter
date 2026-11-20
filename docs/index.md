# plotnine-linter documentation

plotnine-linter checks **plotnine and matplotlib charts** for problems that mislead readers or make a chart hard to read. Each finding explains the problem and gives a fix in the library you used. pandas and seaborn plots draw with matplotlib, so the linter checks them too.

```python
%load_ext plotnine_linter
```

## Contents

| Page | What's in it |
|---|---|
| [Getting started](getting-started.md) | Jupyter, `lint()` in code, autograders and the command line |
| [Configuration](configuration.md) | `pyproject.toml` settings, severities, thresholds, profiles and suppressions |
| [Rule catalog](rules.md) | Every rule, with why it matters and how to fix it |
| [Gallery](gallery.md) | A broken chart and a fixed chart for every rule |
| [Accessibility](accessibility.md) | The accessibility profile, the Chartability audit and how the rules map to Chartability and WCAG |
| [Calibration](calibration.md) | How often each rule fired on public COGS 108 projects, and what changed as a result |
| [How it works](design.md) | The chart description, the two adapters, the catalog and the known limits |

## Three ideas to keep in mind

1. **Strict only about errors.** Tier 1 rules flag charts that mislead or that readers can't read. Tier 2 rules flag clarity problems. Tier 3 (style) is off until you turn it on.
2. **Every finding teaches.** A finding says what is wrong with this chart, why it matters and what code fixes it.
3. **Breaking a rule is fine with a reason.** An ignore comment keeps the reason next to the plot. There, a reader or a grader sees it.

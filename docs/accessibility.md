# Accessibility

The linter checks the parts of chart accessibility that code can measure on a static plot. This page maps its rules to [Chartability](https://chartability.github.io/POUR-CAF/) and to WCAG, and says plainly what still needs a person.

## The accessibility profile

```python
%plotlint profile accessibility        # in a notebook
lint(p, profile="accessibility")       # in code
```

```toml
[tool.plotnine-linter]                 # in pyproject.toml
profile = "accessibility"
```

The profile turns on every rule tagged with a Chartability test or WCAG criterion, ST301 (no title) too. It uses the published thresholds:

| Setting | Default | Accessibility profile |
| --- | --- | --- |
| Contrast of marks against the background (CL204) | 1.8:1 | 3:1 (WCAG 1.4.11) |
| Contrast of text (LY103) | 4.5:1, or 3:1 for large text | same (WCAG 1.4.3) |
| Smallest text (LY201) | 8 pt | 9 pt (Chartability) |
| Color as the only cue (CL301) | info | warning |
| No title (ST301) | off | warning |

The default for marks is lower than WCAG's 3:1, because most standard palettes fall between 2:1 and 3:1. Examples are matplotlib's default orange (2.5:1) and most of Okabe-Ito. At 3:1, the rule would flag nearly every multi-color chart. Use the profile when accessibility is the point of the assignment.

`show_rules("a11y")` lists the tagged rules, and each rule's Chartability tests and WCAG criteria appear in `show_rules().to_frame()` and in `src/plotnine_linter/data/rules.json`.

## The audit

`audit(p)` (or `%plotlint audit` in a notebook) gives each Chartability test a verdict for this chart:

| Verdict | Meaning |
| --- | --- |
| Pass / Fail | Decided by the rules in the table below. A fail lists the finding and its fix. |
| Partly checked | The linter gathered evidence, and the author answers a question. |
| Your call | Only the author can decide; the audit asks, based on what's in the chart. |
| N/A | About interactive charts or the web page around a chart (30 tests). |

The evidence the audit gathers:

- **Draft alt text** (`alt_text()`), pre-filled in the checklist for the author to edit.
- **Reading grade** (Flesch-Kincaid) of the chart's own text: title, subtitle, caption, axis and legend titles. It also lists words of 4+ syllables. Short chart text (under 10 words) isn't scored.
- **Undefined abbreviations** ("Mean RT (ms)"), unless defined on the chart ("RT = reaction time", "reaction time (RT)"). The audit skips widely known ones (USD, GDP, US).
- **The data as a table** (`data_table(p)`): the plotted columns, or the computed values for histograms, counts and box plots.
- **How to read it**: box plots, violins, log scales, heatmaps, density plots and twin axes each add a prompt.
- **Uncertainty marks** (error bars, confidence bands) prompt the author to say what they show.
- **Extreme values**: one bar 10× the median, or points that stretch an axis 10× past where most values are.

A rule the author suppressed with a reason becomes *partly checked*, and the audit shows the reason. A rule turned off in settings becomes *your call*. "Design is not consistent and familiar" needs the other charts in the notebook. So `%plotlint audit` and `plotnine-linter audit` check it, but `audit(p)` alone doesn't.

**Checklists.** `audit(p).to_markdown()` (or `%plotlint audit --markdown`) gives a checklist to paste into a markdown cell under the chart. Automatic passes are pre-checked; questions get an `Answer:` line. For grading, `plotnine-linter audit project.ipynb --check-answers` reads the pasted checklists back. It lists open boxes, empty answers, and alt text left exactly as drafted.

## Coverage of Chartability's 50 tests

Chartability ([Elavsky, Bennett & Moritz, 2022](https://chartability.github.io/POUR-CAF/)) has 50 tests. It groups them under POUR (WCAG's principles) plus Compromising, Assistive and Flexible. 14 tests are critical (**bold** below). Chartability is CC-BY-SA 3.0; this project uses only its test names.

**Checked automatically** means a rule flags it. **Partly** means a rule catches common cases, but a person still has to judge. **Person** means a linter can't decide it. **Not applicable** means the test is about interactive or web charts, not static plots in a notebook.

| Principle | Test | Status | Rules / helpers |
| --- | --- | --- | --- |
| Perceivable | **Low contrast** | Checked automatically | LY103 text, CL204 marks |
| | **Content is only visual** | Partly | `alt_text()` drafts a description; [maidr](https://pypi.org/project/maidr/) adds screen-reader, sonified and braille access |
| | **Small text size** | Checked automatically | LY201 |
| | **Visual presents seizure risk** | Not applicable | static plots |
| | Color is used alone to communicate meaning | Checked automatically | CL301 |
| | Meaningful elements can be distinguished from each other | Partly | CL102, LY102 |
| | Not CVD-friendly | Checked automatically | CL201, CL101 |
| | Spacing is inappropriate | Partly | LY101 |
| Operable | **Interaction modality only has one input type** · **No interaction cues or instructions** · **Controls override AT controls** · and 5 more | Not applicable | interactive charts only |
| Understandable | **No explanation for purpose or for how to read** | Person | the audit asks, with chart-specific prompts |
| | **No title, summary, or caption** | Partly | ST301 checks the title; a summary or caption needs a person |
| | **Reading level inappropriate** | Partly | the audit scores the chart's text |
| | Information complexity is inappropriate | Partly | MK102 |
| | Metrics and variables are undefined | Partly | LB301; the audit lists undefined abbreviations |
| | Statistical uncertainty isn't clearly communicated | Partly | MK203, MK204 |
| | Axis labels are unclear or missing | Checked automatically | LB101, LB201, LB301, LB205 |
| | Interactive context is not clear · Changes are not easy to follow · Controls are inappropriate | Not applicable | |
| Robust | Does not conform to standards · Semantically invalid · Fragile technology support | Not applicable | about the web page or app around the chart |
| Compromising | **No table** | Person | `data_table(p)` makes one; the audit asks whether to show it |
| | 6 more (single process, history, forgiving interactions, narrative navigation, static data, shareable state) | Not applicable | |
| Assistive | **Data density is inappropriate** | Checked automatically | MK101, MK202, MK205, CL102 |
| | **Navigation and interaction is tedious** | Not applicable | |
| | Visually apparent features and relationships are not described | Partly | `alt_text()` reports extremes, trends and correlation |
| | Data in text is not human-readable | Partly | LB206, ST307, AX207 |
| | Space does not handle extremes | Partly | the audit flags one value that squashes the rest |
| | No default "build-your-own" provided | Not applicable | |
| Flexible | **User style change not respected** | Not applicable | (the linter's own notebook output follows light and dark themes) |
| | Design is not consistent and familiar | Checked automatically | ST305, ST306 |
| | 6 more (animations, scrolling, zoom, text adjustments, contrast/textures, difficult chart types) | Not applicable or person | |

Of the 14 critical tests, the linter checks 3 automatically: low contrast, small text and data density. It checks parts of three more: title, alt text and reading level. Six are not applicable to static plots. Two (how to read, table) need the author; the audit asks about them.

## What else helps

- **Alt text.** `report.alt_text` / `alt_text(p)` drafts a description. Jupyter doesn't attach alt text to plot images. The author has to put it where a reader will find it.
- **maidr.** [maidr](https://pypi.org/project/maidr/) helps readers who are blind or have low vision. They can explore matplotlib, seaborn and plotnine charts by screen reader, sound and braille.
- **Blind and low-vision authors.** The text findings and alt text let someone check a plot they can't see.

# Calibration on COGS 108 final projects

*November 2026.* We tuned the rules against real student work: the public COGS 108 final projects posted with the groups' agreement (the 11 `FinalProjects-<term>` repositories linked from the [course guidelines](https://github.com/COGS108/Projects/blob/fa26/FinalProject_Guidelines.md#previous-cogs-108-final-projects), Spring 2017 to Winter 2025; 584 notebooks). No other repositories were used. Reports refer to plots by term, group and cell only; no student names.

**The population:** every project uses matplotlib, seaborn or pandas. None uses plotnine, so this calibrates the matplotlib side of the linter. The plotnine side is covered by the tests and the gallery.

## Two sources of evidence

1. **Image audit (what students actually do).** The notebooks contain about 8,600 saved plot images. A reviewer judged a stratified random sample of 120 against every rule (yes / no / can't tell / doesn't apply), and noted problems the catalog missed.
2. **Re-running the notebooks (what the linter actually says).** The repos don't include data files, and most data came from sources this environment can't reach, so most cells failed. Of 558 notebooks run, 41 produced real plots. Each flagged finding was then judged by looking at the plot.

## How often problems occur (image audit, 120 plots)

Share of plots with the problem, among plots where the rule applies:

| Rule | Present | | Rule | Present |
| --- | --- | --- | --- | --- |
| MK203 summary bars without uncertainty | 10/11 | | LB101 unlabeled numeric axis | 28/117 |
| AX204 default histogram bins | 12/24 | | ST301 no title | 28/120 |
| AX205 ordered categories out of order | 3/6 | | LB203 redundant legend | 9/46 |
| AX201 unsorted bars | 13/27 | | LB301 no units | 20/117 |
| AX202 rotated category labels | 23/50 | | CL102 too many colors | 6/36 |
| LY202 legend order ≠ line order | 5/14 | | LY102 legend covers data | 7/46 |
| MK101 overplotting | 10/30 | | LY201 text too small | 11/120 |
| LB201 raw variable names | 39/120 | | AX102 dual axes | 4/120 |
| CL201 not CVD-safe | 11/36 | | AX101 truncated bars | 1/64 |

Rarely or never seen: pies (MK201), 3D (MK102), rainbow colormaps (CL101), log scales (AX103), excess decimals (ST307). They stay because they're serious when they do occur.

Common problems the catalog didn't cover, now added as rules:

| Problem | Plots | New rule |
| --- | --- | --- |
| Color that encodes nothing (per-bar hues) | 18 | CL203 |
| Label doesn't match the values ("%" on fractions, "density" on counts) | ~23 | LB205 *(heuristic)* |
| Log-transformed values on a linear axis | 7 | AX206 *(heuristic)* |
| Scientific offset such as "1e8" | 4 | LB206 |
| Single-series default legend (pandas) | 7 of 9 LB203 hits | LB203 extended |

## What the linter said, before and after tuning

On the same 41 notebooks:

| | First run | After tuning |
| --- | --- | --- |
| Figures linted | 322 (128 of them empty axes) | 214 plots with data; 108 empty figures skipped |
| Findings per plot | 1.85 | 1.28 |
| Plots with no findings | 24% | 36% |
| Internal errors | 0 | 0 |

Findings per rule (plots flagged):

| Rule | First run | After | What changed |
| --- | --- | --- | --- |
| LB202 → LB301 no units | 70 | — (opt-in) | Fired on 42% of plots with about 1 in 4 correct; now opt-in Tier 3 with a longer word list |
| LB201 raw variable names | 50 | 58 | "Price($)", "Race/Ethnicity" no longer read as code; `%employed`, `Death_Penalty?` now do; also checks titles |
| AX202 rotated labels | 41 | 33 | Dropped the character-count trigger (wrong in all 4 cases checked); rotation only |
| LB101 unlabeled numeric axis | 34 | 43 | More plots linted (no change to the rule) |
| MK101 overplotting | 21 | 29 | Threshold 0.4 → 0.5 |
| AX204 default bins | 5 | 1 | Histograms are tagged when drawn, so touching bars aren't mistaken for one |
| CL102 / CL201 | 6 / 6 | 1 / 2 | Colors that repeat the axis are exempt; CL201 judges each pair, so a red/green pair with different markers passes |
| LB203 redundant legend | 0 | 25 | Now includes single-entry legends |
| CL204 low-contrast marks | — | 15 | New (e.g. the palest bar of a sequential palette on seaborn's gray) |
| LB206 offset notation | — | 14 | New |
| CL203 color encodes nothing | — | 11 | New |
| AX207 fractional ticks | — | 7 | New (e.g. "9.5 months") |
| LY103 low-contrast text | — | 7 | New (e.g. white annotations on mid-blue heatmap cells) |
| AX206 / LB205 | — | 6 / 4 | New (heuristic, info) |

Precision labels from the first run, and the false-positive patterns behind each fix, are in the calibration working files (not part of this repository).

## Thresholds

| Threshold | Before | After | Evidence |
| --- | --- | --- | --- |
| `overplot_fraction` (MK101) | 0.4 | 0.5 | 29 of 31 fires were at 0.5 or above; the only debatable one was 0.41 |
| `max_category_label_chars` (AX202) | 12 | removed | Most rotated labels were short (years, 3-letter months); length alone missed about 70% and misfired on labels that fit |
| `cvd_min_delta_e` (CL201) | 8 | 8 | The pure red/green pairs it flagged (ΔE 7.5) were true positives |
| `max_pie_slices` (MK201) | 4 | 4 | Kept as decided; only one pie in the data |
| `max_lines` (MK202), `max_categorical_colors` (CL102) | 7, 8 | unchanged | Untested: flagged plots had 10–29 lines or colors; none had 8–9 |

## Limits

- Only 41 notebooks could be re-run, and a few groups contribute many plots (17 of the first run's 42 AX202 hits came from one notebook). Treat per-rule rates as rough.
- The image audit is one reviewer's judgment. The small denominators (AX203, AX205, MK203) are unstable.
- None of this exercises the plotnine adapter. A course that teaches plotnine should spot-check its first assignment.

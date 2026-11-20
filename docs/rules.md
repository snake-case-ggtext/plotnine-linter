# Rule catalog

Every rule, with why it matters and how to fix it. Tiers 1 and 2 run by default. This file comes from `src/plotnine_linter/data/rules.json`: run `make rules` after you change the catalog.

## Tier 1 — Errors (on by default)

| ID | Rule | Why | Fix |
| --- | --- | --- | --- |
| AX101 | Bar or area axis excludes zero | A bar's length encodes its value. When the value axis doesn't start at zero, bar lengths stop being proportional and small differences look large. | Remove the axis limits so the bars start at zero; if the zoomed view matters, show the values as points or a line instead of bars. |
| AX102 | Dual y-axes | Two independent scales on one panel make the crossing points and relative slopes arbitrary: rescale either axis and the story changes. | Use two panels that share the x-axis, or index both series to a common baseline. |
| AX103 | Log scale silently drops data | Zero and negative values have no logarithm. They vanish from a log axis with at most a console warning, so the chart quietly shows less data than the reader assumes. | Use a pseudo-log or symlog transform, or filter the values out and say so in the caption. |
| CL101 | Rainbow colormap for ordered data | Rainbow colormaps aren't perceptually ordered: brightness jumps create false boundaries, and they fail for readers with color-vision deficiency. | Use `viridis` or `cividis` for sequential data; a diverging map such as `RdBu` centered at the midpoint for data with a meaningful center. |
| CL102 | Too many categorical colors | Readers can reliably match only about eight hues to a legend; beyond that, colors repeat or become too similar to tell apart. | Highlight the few categories that matter and gray the rest, facet, or label directly. |
| LB101 | Quantitative axis has no label | Without a label the reader can't tell what is measured or in what units. | Add an axis label with units. |
| LY101 | Overlapping tick labels | Overlapping labels can't be read, so the axis stops doing its job. | Swap axes first (`coord_flip()` / `barh`); then fewer ticks or shorter labels. Rotation isn't a fix (see AX202). |
| LY102 | Legend covers data | A legend drawn over the data hides exactly the marks the reader is trying to see. | Place the legend outside the plotting area, or label the series directly. |
| LY103 | Low-contrast text | Text that is too close in brightness to its background can't be read by people with low vision, on a projector, or in sunlight. WCAG asks for at least 4.5:1 (3:1 for large text). | Darken the text (or lighten the background) until it meets 4.5:1. |
| MK101 | Overplotting | When many points land on top of each other, density becomes invisible: a thousand points in one spot look the same as one. | Add transparency, jitter discrete positions, bin the points (2D histogram / hexbin), or sample. |
| MK102 | 3D for 2D data | Perspective distorts length and area, and bars hide behind each other; the third dimension adds no information. | Use 2D bars, grouped bars, or a heatmap. |
| MK103 | Line connects unordered categories | A line implies continuity and order between neighboring points. Between nominal categories there is none, so the slopes mean nothing. | Use points, bars, or a dot plot; keep lines for ordered or time data. |

## Tier 2 — Clarity (on by default)

| ID | Rule | Why | Fix |
| --- | --- | --- | --- |
| AX201 | Unsorted bars on a nominal axis | With nominal categories, the reader's question is usually 'which is biggest?'. Alphabetical order hides the ranking and makes the reader do the sorting. | Order the bars by value; suppress this rule when the category order is meaningful. |
| AX202 | Rotated or crowded category labels | Tilted text is slow to read, even at 30°. Rotating labels usually means the axes should be swapped so long category names read horizontally. | Swap the axes (`coord_flip()` / `barh`). Time axes stay horizontal: use fewer ticks or a shorter date format. |
| AX203 | Free facet scales | Panels side by side invite comparison. With free scales, the same bar height or slope means different values in different panels. | Use shared scales, or say in the title or caption that each panel has its own scale. |
| AX204 | Default histogram bins | A histogram's shape depends on its bins. The library default is arbitrary, so patterns can appear or vanish depending on a choice nobody made. | Choose a bin width that means something in the data's units. |
| AX205 | Ordered categories in alphabetical order | Months, weekdays and rating scales have a natural order. Stored as plain strings, they sort alphabetically (Apr, Aug, Dec...), which scrambles the pattern the chart should show. | Make the column an ordered Categorical in its natural order. |
| AX206 | Log values on a linear axis *(heuristic, reported as info)* | Plotting log-transformed values on a linear axis makes readers decode logarithms (what is 4.7?). A log-scaled axis keeps the original units on the ticks. | Plot the original values on a log-scaled axis instead. |
| AX207 | Fractional ticks on whole-number data | Ticks like 2017.5 on years, or 2.5 on a count of people, label values the data can't take and make the chart look careless. | Put ticks on whole numbers only. |
| CL201 | Colors indistinguishable with color-vision deficiency | About 1 in 12 men and 1 in 200 women have a color-vision deficiency, most often red-green. Categories that differ only by such colors merge for them. | Use a CVD-safe palette such as Okabe-Ito, or add a second encoding (shape, linetype, direct labels). |
| CL202 | Diverging data on a sequential color scale | When values run from negative to positive (correlations, changes, residuals), zero is the meaningful middle. A sequential scale gives zero no special color, so readers can't tell positive from negative at a glance. | Use a diverging colormap centered at zero, e.g. RdBu with vmin = -vmax. |
| CL203 | Color that encodes nothing | Giving every bar its own color invites readers to look for a meaning that isn't there, and it uses up color you may need for something that matters. | Use one color for all bars, and save color for a variable or a highlight. |
| CL204 | Low-contrast marks | Lines, points and bars that barely differ from the background (pale yellow on white, light gray on gray) disappear for readers with low vision and on projectors. WCAG asks for 3:1 contrast for graphics needed to understand a chart. | Use a darker color for the marks, or give light fills a dark outline. |
| LB201 | Label is a raw variable name | Column names are code: `avg_income_usd` is how a program refers to the data, not how a reader does. plotnine and pandas use the column name as the label unless you change it. | Write a label for people: words, capitalized, with units. |
| LB203 | Redundant legend | When color repeats what an axis already shows, or a legend has a single entry, the legend adds nothing but asks the reader to look it up anyway. | Hide the legend, or drop the redundant color mapping. |
| LB205 | Label doesn't match the values *(heuristic, reported as info)* | A label that promises percentages over values between 0 and 1, or a proportion over raw counts, tells the reader the wrong scale. | Make the label and the values agree: convert the values or reword the label. |
| LB206 | Scientific offset on an axis | An offset like '1e8' in the corner of the axis is easy to miss, so readers misread every tick by orders of magnitude. | Rescale the values (e.g. to millions) and say so in the axis label, or format the ticks in full. |
| LY201 | Text too small at final size | Small text becomes unreadable once the figure lands in slides, a report or a phone screen. | Increase the base font size, or make the figure smaller so text is relatively larger. |
| LY202 | Legend order doesn't match line order | When the top legend entry isn't the top line, readers hunt back and forth between lines and legend to match them up. | Order the legend by each line's last value, or label the line ends directly. |
| MK201 | Pie with many slices | People compare angles and areas poorly; past a few slices, a pie can't show which parts are bigger. | Use a sorted bar chart. |
| MK202 | Spaghetti lines | Past about seven lines, lines tangle and colors can't be matched to the legend. | Highlight the few lines that matter and gray the rest, or facet. |
| MK203 | Summary bars without uncertainty | A bar of means hides spread and sample size: two groups with the same mean can differ wildly in their data. | Add error bars or the raw points, or use a box or strip plot. |
| MK204 | Box plot hides small groups | A box plot summarizes a distribution with five numbers. With only a handful of observations those numbers are unstable, and the box hides how few points there are. | Show the points (jittered) on top of the box, or instead of it, and report n per group. |
| MK205 | Stacked bars with many segments | Only the bottom segment of a stacked bar shares a baseline. With many segments, the middle ones can't be compared across bars. | Use grouped (dodged) bars or small multiples, or keep stacking to the few segments that matter. |

## Tier 3 — Style (opt-in)

| ID | Rule | Why | Fix |
| --- | --- | --- | --- |
| CL301 | Color is the only cue | Charts get printed in grayscale and read by people with low vision. If categories differ only in hue and have the same lightness, they become indistinguishable (WCAG: don't rely on color alone). | Add a second cue: shape or linetype for the same variable, or label the categories directly. |
| LB301 | Quantitative label has no units *(heuristic, reported as info)* | A number without units can't be interpreted: is that dollars or thousands of dollars, seconds or minutes? | Add units in parentheses, e.g. 'Median income (USD)'. |
| ST301 | No title | A figure that travels without its surrounding text (a slide, a report, a screenshot) needs its own context. | Add a title; a takeaway title states what the reader should see. |
| ST303 | Direct labels would beat a legend | With a few lines, labeling each line end removes the back-and-forth between lines and legend. | Label line ends and drop the legend. |
| ST305 | Same category, different colors across figures | Readers carry color meaning from one figure to the next. If 'West' is orange in one chart and blue in the next, they'll misread the second. | Define one palette per variable (a dict of category to color) and reuse it in every figure. |
| ST306 | Inconsistent themes across figures | Figures in one report read as a set. Switching themes or base font sizes between them looks unfinished and makes comparisons harder. | Set the theme and font size once at the top of the notebook. |
| ST307 | Excess precision in tick labels | Extra decimals add clutter without information. | Format ticks to the precision the step needs. |

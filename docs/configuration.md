# Configuration

## pyproject.toml

The linter reads `[tool.plotnine-linter]` from the nearest `pyproject.toml`, searching upward from the working directory. An instructor can ship one with the course materials, so every student sees the same rules.

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

The same keywords work in code:

```python
lint(
    p,
    select=["tier1", "tier2", "ST301"],
    ignore=["AX203"],
    severity={"LB301": "warning"},
)
```

In a notebook, `%plotlint select=...` and `%plotlint ignore=...` change the settings for the rest of the session.

## Choosing rules

| Selector | Selects |
|---|---|
| `tier1`, `tier2`, `tier3` | a whole tier |
| `AX`, `CL`, `LB`, `LY`, `MK`, `ST` | an area: axes, color, labels, layout, marks, style |
| `AX101` | one rule |
| `a11y` | the rules tied to a Chartability test or a WCAG criterion |
| `ALL` | every rule |

By default, tiers 1 and 2 run. Tier 3 holds the style rules, which are matters of taste or polish. Turn them all on with `tier3`, or pick single rules by ID.

## Severity

Tier 1 rules report **error**, tier 2 **warning** and tier 3 **info**. A heuristic rule always reports **info**, because it can't be certain. `severity` overrides the level of any rule.

## Thresholds

Some rules have a number you can change, such as `max_pie_slices` (MK201) or `min_font_pt` (LY201). `src/plotnine_linter/data/rules.json` lists every threshold with its default and the rule it affects.

## Profiles

A profile is a preset of rules, severities and thresholds. The catalog has one, `accessibility`. It turns on every rule tied to Chartability or WCAG. It also uses their published thresholds: 3:1 contrast for marks and at least 9 pt text. Explicit settings override the profile. [Accessibility](accessibility.md) describes it.

```python
%plotlint profile accessibility
lint(p, profile="accessibility")
```

## Breaking a rule on purpose

Put a comment with the rule ID and a reason next to the plot, in the cell or the script:

```python
# plotlint: ignore[AX201] survey questions are in the order we asked them
# plotlint: ignore[AX201, LB301] the reason applies to both
```

In code, pass `suppress`:

```python
lint(p, suppress={"AX201": "the order is meaningful"})
```

A suppression without a reason still works, but the report adds an info note (`SUP001`) that asks for one.

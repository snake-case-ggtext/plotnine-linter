# Changelog

This file lists all notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [semantic versioning](https://semver.org/).

## [0.1.0] - unreleased

First release: a teaching-first linter for plotnine and matplotlib charts.

### Added

- **41 rules in three tiers:** errors and clarity problems (on by default) and style (opt-in). Each rule has a permanent ID, a reason it matters and a fix. The catalog is data (`data/rules.json`), so other implementations can share it.
- **Two adapters:** the spec adapter reads plotnine plots (0.13 to 0.15). The render adapter reads any matplotlib figure, including pandas and seaborn plots and the figures plotnine draws.
- **Jupyter extension:** `%load_ext plotnine_linter` lints every plot when the notebook shows it. The `%plotlint` magic has `on`, `off`, `status`, `reset`, `select=`, `ignore=`, `rules`, `summary`, `profile` and `audit`.
- **`lint()`** returns a `Report` with findings, suppressions and a draft alt text. `assert_clean()` serves test suites and autograders.
- **Command line:** `plotnine-linter check` runs notebooks and scripts and lints every plot. `plotnine-linter audit` writes accessibility checklists, and `--check-answers` lists the items students left open. `plotnine-linter rules` lists the catalog.
- **Configuration** in `pyproject.toml`: rule selection by tier, area or ID, severities, thresholds and profiles. `# plotlint: ignore[ID] reason` comments suppress a rule with a reason.
- **Accessibility:** color-vision simulation (Machado 2009) with CIEDE2000 distances and WCAG contrast for text and marks. Also a grayscale check, draft alt text and an `accessibility` profile. The rules map to Chartability and WCAG.
- **Chartability audit:** `audit()` gives a verdict for all 50 Chartability tests. It gathers evidence: alt text, reading grade, undefined abbreviations, the data as a table and how-to-read prompts. It asks the author the rest. `data_table()` returns the data behind a chart.
- **Docs:** a rule catalog, a before and after gallery, an accessibility guide and a demo notebook. Also a calibration report on public COGS 108 projects.
- **Tooling** like the sibling projects (ggtext, plotnine-ggdist): uv dependency groups, a Makefile and prek git hooks. Ruff runs with its default rules and formatter. pyrefly runs in strict mode with a baseline, and slop-lint checks the docstrings and comments.

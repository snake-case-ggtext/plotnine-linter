# Contributing to plotnine-linter

Thanks for helping! Bug reports, false alarms, rule ideas, docs fixes and examples are all welcome. For a big change, please open an issue first so we can talk it through.

A false alarm is a bug. Please include the plot code and the finding you think is wrong.

## Development setup

Development dependencies live in [dependency groups](https://packaging.python.org/en/latest/specifications/dependency-groups/) in `pyproject.toml`:

| Group | Contents |
|---|---|
| `test` | pytest, pytest-cov, pytest-randomly, plotnine, seaborn, IPython, ipykernel, nbclient, nbformat |
| `docs` | jupyter, nbconvert |
| `dev` | `test` + `docs` + ruff, prek, pyrefly, pandas-stubs, slop-lint |

slop-lint is not on PyPI. The `dev` group installs it from GitHub, and `uv.lock` pins the commit. It needs Python 3.12 or later, so on Python 3.10 and 3.11 the group skips it.

We use [uv](https://docs.astral.sh/uv/), but plain `pip` + `venv` works too (`--group` needs pip ≥ 25.1).

`.python-version` sets Python 3.13 for development, so uv uses (and if needed downloads) it. pyrefly and slop-lint give the same results as CI only on that version. On older versions, numpy and pandas-stubs differ, and the dev group skips slop-lint.

### With uv

uv creates the environment and installs plotnine-linter (editable) and the `dev` group from `uv.lock`:

```bash
make install                 # uv sync + the prek git hooks
uv run pytest -k audit       # any command, in that environment
```

### With pip

`--group` installs only the group, so also install the package itself with `-e .`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade "pip>=25.1"
pip install -e . --group dev
```

pip ignores `uv.lock`, so it installs the newest versions that `pyproject.toml` allows.

## Make targets

```bash
make install      # uv sync (package + dev tools) and install the prek git hooks
make test         # pytest in random order (pytest-randomly) with coverage
make test-fast    # the tests without the ones that start a Jupyter kernel
make lint         # ruff check + ruff format --check + pyrefly (strict) + slop-lint + docs/rules.md check
make format       # ruff --fix and ruff format
make prose        # slop-lint on the Markdown docs as well (report only)
make rules        # write docs/rules.md from the catalog
make gallery      # draw the before and after gallery
make demo         # run examples/demo.ipynb again and save its output
make pre-commit   # install the prek git hooks and run them on every file
make help         # list the targets
```

Run `make install` once after cloning. The hooks then run ruff, pyrefly and slop-lint on every commit. CI runs `make lint` and `make test` on Python 3.13 for every push to `main` and every pull request. It also runs the tests on older stacks, down to Python 3.10 with plotnine 0.13 and matplotlib 3.8. Run `make test` and `make lint` before you push.

## Linting and formatting

Ruff uses its default rules and formatter settings; don't add per-project rule selections.

The linter reads arbitrary user plots, so some code catches broad exceptions on purpose. The rule runner, the Jupyter hook and the alt text never break a student's notebook. Those lines carry `# noqa: BLE001` and a comment that says why. Code that only reads an attribute of a plot, scale or artist catches `PROBE_ERRORS` (in `describe/model.py`) instead.

## Type checking

pyrefly runs in strict mode on `src`, `tests` and `docs/gallery`, and checks the code against Python 3.10 syntax. Run it on Python 3.13 (`.python-version`), because the numpy and pandas stubs differ between versions. `pyrefly-baseline.json` records the existing errors, so only added errors fail. All of them are missing annotations (`implicit-any`) in internal helpers. When you add types, shrink the baseline with `uv run pyrefly check --update-baseline`.

The rule checks have types: `def ax101(desc: ChartDescription, cfg: Config) -> Iterator[Hit]`. Give each added rule the same signature.

## Prose

[slop-lint](https://github.com/tylerriccio33/slop-lint) checks docstrings, `#` comments and Makefile comments against a subset of ASD-STE100 (Simplified Technical English):

- Sentences have at most 20 words.
- Use the active voice ("the rule flags the chart", not the passive form).
- Avoid the words on slop-lint's banned list.

`make lint` and the git hook run it on every tracked Python file and the Makefile. slop-lint reads a code example in a docstring as part of a sentence. So end the sentence before the example with a period, and put examples last. For a false positive, add `# slop-lint: ignore[rule-name]` to the line.

`make prose` also checks the Markdown files. It does not fail, because slop-lint reads each Markdown table as one long sentence. Fix any finding outside a table.

The finding messages, fixes and the rule catalog's why and fix text are what students read. Keep them short, specific and in plain words.

## Running the tests

Tests run in a random order (pytest-randomly). To reproduce a failure, rerun with the seed printed in the header: `uv run pytest -p randomly --randomly-seed=<seed>`.

```bash
uv run pytest                          # whole suite
uv run pytest tests/test_audit.py      # one file
uv run pytest -k cl201                 # by name
uv run pytest -m "not notebook"        # skip the tests that start a Jupyter kernel
uv run pytest -p no:randomly           # in file order
```

The test files and what they cover:

| File | Covers |
|---|---|
| `test_plotnine_rules.py` | each rule on plotnine plots: one test that fires and one that stays quiet |
| `test_matplotlib_rules.py` | each rule on matplotlib, pandas and seaborn figures |
| `test_review_cases.py` | realistic COGS 108-style charts: regressions for false alarms found in review, and guards |
| `test_api.py` | `lint()`, configuration, profiles, suppressions and the command line |
| `test_audit.py` | the Chartability audit, checklists, `data_table()` and the readability checks |
| `test_jupyter.py` | the Jupyter hook and the `%plotlint` magic (marked `notebook`: starts a kernel) |

Each feature needs tests. A rule needs a test where it fires and a test where it stays quiet.

## Adding a rule

1. Add the rule's entry (ID, tier, title, why, fix, and any Chartability or WCAG tags) to `src/plotnine_linter/data/rules.json`. The third character of the ID is its tier, and IDs are never reused.
2. Write the check in the module for its area (`rules/axes.py`, `rules/color.py`, ...):

   ```python
   @rule("MK206")
   def mk206(desc: ChartDescription, cfg: Config) -> Iterator[Hit]:
       if desc.spec is None:
           return
       for layer in desc.spec.layers:
           if ...:
               yield Hit("What is wrong, specifically.", fix="Code that fixes it.")
   ```

3. Add tests, and a before and after pair to `docs/gallery/make_gallery.py`. The gallery build fails if a rule has no pair.
4. Run `make rules` and `make gallery`, and look at the images before you commit.

## Docs and examples

The docs are Markdown files in `docs/`. Two of them come from code, so don't edit them by hand:

- `docs/rules.md`: run `make rules`.
- `docs/gallery.md` and `docs/gallery/img/`: run `make gallery`.

`examples/demo.ipynb` is the notebook tour. After you change it, run `make demo` to save its output.

## Releasing (maintainers)

1. Update the version in `pyproject.toml` and `src/plotnine_linter/__init__.py`.
2. Move the "unreleased" entries in `CHANGELOG.md` under the release version.
3. Tag the release and build with `uv build`.

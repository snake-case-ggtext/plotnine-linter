"""The Jupyter hook: findings appear under plots, once, without hiding the plot."""

import re

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")
pytest.importorskip("ipykernel")

SETUP = (
    "%load_ext plotnine_linter\n"
    "import pandas as pd\nimport matplotlib.pyplot as plt\nfrom plotnine import *\n"
    "df = pd.DataFrame({'region_name': list('dbca'), 'avg_income_usd': [4, 1, 3, 2]})"
)


def run(*cells):
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell(c) for c in (SETUP, *cells)]
    nbclient.NotebookClient(nb, timeout=180, kernel_name="python3").execute()
    out = []
    for cell in nb.cells[1:]:
        kinds = []
        for o in cell.outputs:
            data = getattr(o, "data", {})
            if "image/png" in data:
                kinds.append("PNG")
            elif "text/html" in data:
                kinds += re.findall(
                    r"<code style='font-weight:600'>(\w+)</code>", data["text/html"]
                )
        out.append(kinds)
    return out


@pytest.mark.notebook
def test_hook_plotnine_matplotlib_and_suppression():
    plotnine_cell, mpl_cell, suppressed_cell, off_cell = run(
        "ggplot(df, aes('region_name', 'avg_income_usd')) + geom_col()",
        "fig, ax = plt.subplots()\nax.bar(['a', 'b'], [5, 6])\nax.set_ylim(4, 7)\nplt.show()",
        "# plotlint: ignore[AX201] fixed order\nggplot(df, aes('region_name', 'avg_income_usd')) + geom_col() + labs(x='Region', y='Income (USD)')",
        "%plotlint off\nggplot(df, aes('region_name', 'avg_income_usd')) + geom_col()",
    )
    assert (
        plotnine_cell[0] == "PNG"
        and "AX201" in plotnine_cell
        and "LB201" in plotnine_cell
    )
    assert plotnine_cell.count("PNG") == 1
    assert mpl_cell[0] == "PNG" and "AX101" in mpl_cell
    assert suppressed_cell == ["PNG"]
    assert off_cell == ["PNG"]


@pytest.mark.notebook
def test_summary_magic():
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_code_cell(c)
        for c in (
            SETUP,
            "ggplot(df, aes('region_name', 'avg_income_usd')) + geom_col()",
            "fig, ax = plt.subplots(); ax.plot([1, 2], [1, 2]); ax.set_xlabel('Time (s)'); ax.set_ylabel('Distance (m)'); plt.show()",
            "%plotlint summary",
        )
    ]
    nbclient.NotebookClient(nb, timeout=180, kernel_name="python3").execute()
    html = next(
        o.data["text/html"]
        for o in nb.cells[-1].outputs
        if "text/html" in getattr(o, "data", {})
    )
    assert "2 plot(s) linted" in html and "AX201" in html and "no issues" in html


@pytest.mark.notebook
def test_audit_magic():
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_code_cell(c)
        for c in (
            SETUP,
            "p = ggplot(df, aes('region_name', 'avg_income_usd')) + geom_col() + labs(x='Region', y='Income (USD)')\np",
            "%plotlint audit",
            "%plotlint audit p --markdown",
        )
    ]
    nbclient.NotebookClient(nb, timeout=180, kernel_name="python3").execute()
    html = next(
        o.data["text/html"]
        for o in nb.cells[2].outputs
        if "text/html" in getattr(o, "data", {})
    )
    assert "Chartability audit" in html and "Your call" in html
    text = "".join(o.get("text", "") for o in nb.cells[3].outputs)
    assert (
        "#### Accessibility checklist" in text
        and "- [x]" in text
        and "> Bar chart" in text
    )

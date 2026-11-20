"""Chartability audit: verdicts, evidence, checklists, and data tables."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from plotnine import aes, geom_boxplot, geom_col, geom_errorbar, geom_histogram, geom_point, ggplot, labs
from plotnine import element_text, scale_fill_manual, scale_y_log10, theme, theme_bw

from plotnine_linter import audit, data_table
from plotnine_linter.audit import ASK, FAIL, NA, PARTLY, PASS, Audit, read_checklists
from plotnine_linter.readability import analyze, syllables, undefined_abbreviations
from plotnine_linter.registry import all_rules, load_catalog

DARK = ["#0072B2", "#D55E00", "#009E73"]  # Okabe-Ito colors with 3:1 contrast on white


@pytest.fixture
def rt():
    return pd.DataFrame({"condition": ["control", "drug A", "drug B"], "rt": [431, 470, 512], "se": [12, 15, 14]})


def rt_plot(rt, **extra):
    return (
        ggplot(rt, aes("condition", "rt", fill="condition"))
        + geom_col()
        + geom_errorbar(aes(ymin="rt-se", ymax="rt+se"), width=0.2)
        + labs(title="Reaction time by condition", x="Condition", y="Mean RT (ms)", **extra)
    )


# ----- the catalog --------------------------------------------------------------
def test_catalog_lists_all_50_tests():
    tests = load_catalog()["chartability"]["tests"]
    assert len(tests) == 50
    assert sum(t["critical"] for t in tests) == 14
    names = {t["name"] for t in tests}
    for r in all_rules():
        assert set(r.chartability) <= names, r.id
    for t in tests:
        assert t["static"] in {"rules", "partly", "ask", "na"}
        if t["static"] in ("partly", "ask"):
            assert t.get("ask"), t["name"]
        if t["static"] == "na":
            assert t.get("na"), t["name"]


# ----- verdicts --------------------------------------------------------------
def test_bar_chart_audit(rt):
    a = audit(rt_plot(rt))
    assert len(a) == 50
    assert a.title == "Reaction time by condition" and a.kind == "bar chart"
    assert a["Low contrast"].status == FAIL  # default hue green is 2.2:1 on the gray panel
    assert a["Small text size"].status == FAIL  # plotnine's 8.8 pt tick labels, under the 9 pt target
    assert a["Metrics and variables are undefined"].status == PARTLY
    assert "RT" in a["Metrics and variables are undefined"].evidence
    assert a["Statistical uncertainty isn't clearly communicated"].status == PARTLY
    assert "error bars" in a["Statistical uncertainty isn't clearly communicated"].evidence
    assert a["No title, summary, or caption"].status == PARTLY
    assert "names what is plotted" in a["No title, summary, or caption"].question
    assert a["No table"].status == ASK and "3 rows" in a["No table"].evidence
    assert a["Not CVD-friendly"].status == PASS
    assert a["Design is not consistent and familiar"].status == NA  # no other charts to compare
    assert a.counts[NA] == 30
    assert a.alt_text.startswith("Reaction time by condition.")


def test_fixing_the_chart_flips_verdicts(rt):
    p = (
        rt_plot(rt, caption="Bars show means; error bars show ±1 standard error. RT = reaction time.")
        + scale_fill_manual(values=DARK)
        + theme_bw()
        + theme(text=element_text(size=11), axis_text=element_text(size=10))
    )
    a = audit(p)
    assert a["Low contrast"].status == PASS
    assert a["Small text size"].status == PASS
    assert "smallest text" in a["Small text size"].evidence
    assert a["Metrics and variables are undefined"].status == PASS  # defined in the caption
    assert "Caption" in a["No title, summary, or caption"].evidence


def test_rules_turned_off_become_questions(rt):
    from plotnine_linter.config import Config

    a = audit(rt_plot(rt), config=Config(ignore=["CL204", "LY103"]))
    assert a["Low contrast"].status == ASK
    assert "turned off" in a["Low contrast"].evidence


def test_suppressed_rule_is_partly_checked(rt):
    a = audit(rt_plot(rt), source="# plotlint: ignore[CL204] brand colors")
    item = a["Low contrast"]
    assert item.status == PARTLY and "brand colors" in item.evidence


def test_boxplot_on_log_scale_gets_how_to_read_nudges():
    df = pd.DataFrame({"g": list("ab") * 50, "income": np.exp(np.random.default_rng(1).normal(10, 1, 100))})
    p = ggplot(df, aes("g", "income")) + geom_boxplot() + scale_y_log10() + labs(x="Group", y="Income (USD)")
    a = audit(p)
    q = a["No explanation for purpose or for how to read"].question
    assert "box" in q and "log scale" in q
    assert a["Difficult chart type has no alternative"].status == PARTLY
    assert a["No title, summary, or caption"].status == FAIL


def test_matplotlib_boxplot_and_errorbars():
    fig, ax = plt.subplots()
    ax.boxplot([np.random.randn(50), np.random.randn(50) + 1])
    assert "box plot" in audit(fig)["Difficult chart type has no alternative"].evidence.lower()
    fig, ax = plt.subplots()
    ax.errorbar([1, 2, 3], [2, 3, 4], yerr=0.5)
    assert audit(fig)["Statistical uncertainty isn't clearly communicated"].status == PARTLY


def test_extreme_bar_is_flagged():
    fig, ax = plt.subplots()
    ax.bar(list("ABCDE"), [1, 2, 3, 2, 80])
    item = audit(fig)["Space does not handle extremes"]
    assert item.status == PARTLY and "40×" in item.evidence


def test_session_enables_consistency_test(rt):
    from plotnine_linter.session import Session

    a = audit(rt_plot(rt), session=Session())
    assert a["Design is not consistent and familiar"].status == PASS


# ----- output --------------------------------------------------------------
def test_markdown_checklist_round_trip(rt):
    a = audit(rt_plot(rt))
    md = a.to_markdown()
    assert md.count("- [x]") == a.counts[PASS]
    assert "> Reaction time by condition." in md  # the draft alt text is pre-filled
    status = read_checklists(md)[0]
    assert status.title == "Reaction time by condition"
    assert "Low contrast" in status.open_items and "No table" in status.open_items
    assert status.alt_text_unchanged and not status.complete

    answered = md.replace("- [ ]", "- [x]").replace("  - Answer: ", "  - Answer: done")
    answered = answered.replace("> Reaction time by condition.", "> Drug B slows responses the most.")
    assert read_checklists(answered)[0].complete

    blank = md.replace("- [ ] **No table**", "- [x] **No table**")
    assert "No table" in read_checklists(blank)[0].blank_answers


def test_dict_round_trip_and_html(rt):
    a = audit(rt_plot(rt))
    b = Audit.from_dict(a.to_dict())
    assert b.counts == a.counts and b.to_markdown() == a.to_markdown()
    html = a._repr_html_()
    assert "Chartability audit" in html and "Partly checked" in html and "30 tests don" in html
    assert "Your call" in str(a) and "CL204" in str(a)


# ----- data_table --------------------------------------------------------------
def test_data_table_identity_stat(rt):
    t = data_table(rt_plot(rt))
    assert list(t.columns[:2]) == ["Condition", "Mean RT (ms)"] and len(t) == 3


def test_data_table_histogram_and_scatter():
    df = pd.DataFrame({"x": np.random.default_rng(0).normal(size=200)})
    t = data_table(ggplot(df, aes("x")) + geom_histogram(bins=10) + labs(x="Score"))
    assert list(t.columns) == ["Score from", "Score to", "count"] and t["count"].sum() == 200
    t = data_table(ggplot(df.assign(y=df.x * 2), aes("x", "y")) + geom_point())
    assert len(t) == 200


def test_data_table_matplotlib_bars():
    fig, ax = plt.subplots()
    ax.bar(["a", "b", "c"], [3, 1, 2])
    ax.set_ylabel("Count")
    t = data_table(fig)
    assert t.iloc[:, 0].tolist() == ["a", "b", "c"] and t["Count"].tolist() == [3, 1, 2]


# ----- readability --------------------------------------------------------------
def test_readability_helpers():
    assert syllables("cat") == 1 and syllables("probability") >= 4
    assert undefined_abbreviations(["Mean RT (ms)"]) == ["RT"]
    assert undefined_abbreviations(["Mean RT (ms)", "Reaction time (RT) by group"]) == []
    assert undefined_abbreviations(["GDP per capita (USD)"]) == []
    r = analyze(["Heteroskedasticity-consistent standard errors of the estimated regression coefficients", "Posterior probability"])
    assert r.scored and r.grade > 10 and r.long_words


def test_check_answers_cli(tmp_path, rt):
    nbformat = pytest.importorskip("nbformat")
    from plotnine_linter.__main__ import main

    md = audit(rt_plot(rt)).to_markdown()
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_markdown_cell(md)]
    path = tmp_path / "a.ipynb"
    nbformat.write(nb, path)
    assert main(["audit", str(path), "--check-answers"]) == 1
    done = md.replace("- [ ]", "- [x]").replace("  - Answer: ", "  - Answer: yes").replace("> Reaction", "> Mine. Reaction")
    nb.cells = [nbformat.v4.new_markdown_cell(done)]
    nbformat.write(nb, path)
    assert main(["audit", str(path), "--check-answers"]) == 0


def test_data_table_with_reorder(rt):
    p = ggplot(rt, aes("reorder(condition, rt)", "rt")) + geom_col() + labs(x="Condition", y="RT (ms)")
    assert list(data_table(p).columns) == ["Condition", "RT (ms)"]

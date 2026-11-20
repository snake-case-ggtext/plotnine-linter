"""Review cases: realistic COGS 108-style charts.

Each test asserts the CORRECT behavior. Tests marked "FAILS TODAY" document a
confirmed false positive / false negative; the comment says expected vs actual.
Tests marked "guard" pass today and protect behavior that is right.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from plotnine import (
    aes,
    element_text,
    geom_bar,
    geom_col,
    geom_density,
    geom_line,
    geom_point,
    ggplot,
    labs,
    scale_color_manual,
    scale_fill_manual,
    scale_x_datetime,
    theme,
)
from plotnine.data import economics, mpg

from plotnine_linter import lint
from plotnine_linter.findings import Severity

from .conftest import ids

sns = pytest.importorskip("seaborn")

CB = None  # seaborn "colorblind" palette, filled lazily


def penguins(n=300, seed=1):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "species": rng.choice(["Adelie", "Chinstrap", "Gentoo"], n),
            "bill_length_mm": rng.normal(44, 5, n),
            "body_mass_g": rng.normal(4200, 800, n),
        }
    )


def findings(report, rule_id):
    return [f for f in report.findings if f.rule_id == rule_id]


# =====================================================================
# MK103 / MK202: box plots and error bars are read as "lines"
# =====================================================================
def test_matplotlib_boxplot_is_not_lines():
    # FAILS TODAY. Expected: no MK103/MK202. Actual: MK103 (error) "line connects
    # categories" + MK202 "18 lines" -- whiskers/caps/medians are 2-point Line2Ds.
    df = penguins()
    fig, ax = plt.subplots()
    ax.boxplot([d.body_mass_g for _, d in df.groupby("species")])
    ax.set_xticks(
        [1, 2, 3], ["Adelie", "Chinstrap", "Gentoo"]
    )  # works on every matplotlib version
    ax.set_ylabel("Body mass (g)")
    got = ids(lint(fig))
    assert "MK103" not in got
    assert "MK202" not in got


def test_seaborn_boxplot_is_not_lines():
    # FAILS TODAY. Expected: no MK103/MK202. Actual: MK103 + MK202 "15 lines".
    ax = sns.boxplot(data=penguins(), x="species", y="body_mass_g")
    ax.set(xlabel="Species", ylabel="Body mass (g)")
    got = ids(lint(ax.figure))
    assert "MK103" not in got
    assert "MK202" not in got


def test_seaborn_barplot_errorbars_do_not_connect_categories():
    # FAILS TODAY. Expected: no MK103. Actual: MK103 (error) from the vertical CI lines.
    ax = sns.barplot(data=penguins(), x="species", y="body_mass_g")
    ax.set(xlabel="Species", ylabel="Body mass (g)")
    assert "MK103" not in ids(lint(ax.figure))


def test_seaborn_barplot_hue_errorbars_are_not_spaghetti():
    # FAILS TODAY. Expected: no MK202. Actual: "This panel draws 8 lines" (8 CI whiskers).
    rng = np.random.default_rng(0)
    tips = pd.DataFrame(
        {
            "day": rng.choice(["Thur", "Fri", "Sat", "Sun"], 244),
            "sex": rng.choice(["Male", "Female"], 244),
            "total_bill": rng.gamma(4, 5, 244),
        }
    )
    ax = sns.barplot(data=tips, x="day", y="total_bill", hue="sex")
    ax.set(xlabel="Day", ylabel="Total bill (USD)")
    assert "MK202" not in ids(lint(ax.figure))


def test_pointplot_still_flags_mk103():
    # guard: sns.pointplot really does join nominal categories with a line.
    ax = sns.pointplot(data=penguins(), x="species", y="body_mass_g")
    ax.set(xlabel="Species", ylabel="Body mass (g)")
    assert "MK103" in ids(lint(ax.figure))


# =====================================================================
# Axis kind: set_xticklabels / set_xticks(pos, labels) -> FuncFormatter
# (pandas .plot.bar(), matplotlib grouped-bar recipe) read as "continuous"
# =====================================================================
INCOME = pd.Series({"West": 52, "East": 61, "South": 47, "North": 58, "Central": 50})


def test_pandas_bar_category_axis_is_not_numeric():
    # FAILS TODAY. Expected: no LB101. Actual: LB101 "The x-axis shows numbers but
    # has no label" on an axis of region names.
    ax = INCOME.plot.bar()
    ax.set_ylabel("Income (USD, thousands)")
    assert "LB101" not in ids(lint(ax.figure))


def test_pandas_bar_unsorted_is_flagged():
    # FAILS TODAY. Expected: AX201 (bars unsorted). Actual: nothing (axis kind 'continuous').
    ax = INCOME.plot.barh()
    ax.set_xlabel("Income (USD, thousands)")
    assert "AX201" in ids(lint(ax.figure))


def test_pandas_bar_default_rot90_is_flagged():
    # FAILS TODAY. Expected: AX202 (pandas rotates category labels 90° by default).
    # Actual: nothing.
    ax = INCOME.sort_values().plot.bar()
    ax.set_ylabel("Income (USD, thousands)")
    assert "AX202" in ids(lint(ax.figure))


def test_grouped_bar_recipe_has_no_lb101():
    # FAILS TODAY. matplotlib gallery grouped bars: ax.set_xticks(x, labels).
    # Expected: no LB101. Actual: LB101 on the category axis.
    fig, ax = plt.subplots()
    x, w = np.arange(4), 0.35
    ax.bar(x - w / 2, [20, 34, 30, 35], w, label="Men")
    ax.bar(x + w / 2, [25, 32, 34, 20], w, label="Women")
    ax.set_xticks(x, ["Group A", "Group B", "Group C", "Group D"])
    ax.set_ylabel("Score (points)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    assert "LB101" not in ids(lint(fig))


# =====================================================================
# LY101: rotated labels compared by axis-aligned boxes
# =====================================================================
MAJORS = [
    "Cognitive Science",
    "Computer Science",
    "Data Science",
    "Psychology",
    "Economics",
    "Biology",
    "Political Science",
    "Mathematics",
]


def test_ly101_rotated_category_labels_do_not_overlap():
    # FAILS TODAY. Labels at 45° (ha='right') are clearly legible; AX202 is the right
    # finding. Expected: AX202 only. Actual: AX202 + LY101 "5 pairs overlap"
    # (rotated text's axis-aligned bboxes overlap even though the glyphs don't).
    fig, ax = plt.subplots()
    ax.bar(MAJORS, np.arange(8, 0, -1) * 30)
    plt.xticks(rotation=45, ha="right")
    ax.set_ylabel("Students (count)")
    fig.tight_layout()
    got = ids(lint(fig))
    assert "AX202" in got
    assert "LY101" not in got


def test_ly101_autofmt_xdate_does_not_overlap():
    # FAILS TODAY. fig.autofmt_xdate() rotates date labels 30° and they no longer
    # touch. Expected: AX202 only. Actual: AX202 + LY101 "7 pairs overlap".
    fig, ax = plt.subplots()
    d = pd.date_range("2024-01-01", periods=60)
    ax.plot(d, np.random.default_rng(1).normal(size=60).cumsum())
    ax.set_ylabel("Cases (count)")
    fig.autofmt_xdate()
    got = ids(lint(fig))
    assert "LY101" not in got


def test_ly101_plotnine_rotated_labels_do_not_overlap():
    # FAILS TODAY. Same AABB issue in plotnine. Expected: AX202 only; actual adds LY101.
    df = mpg.groupby("manufacturer", as_index=False).agg(hwy=("hwy", "mean"))
    p = (
        ggplot(df, aes("reorder(manufacturer, -hwy)", "hwy"))
        + geom_col()
        + theme(axis_text_x=element_text(rotation=45, ha="right"))
        + labs(x="Manufacturer", y="Mean highway mileage (mpg)")
    )
    got = ids(lint(p))
    assert "AX202" in got
    assert "LY101" not in got


def test_ly101_unrotated_daily_dates_overlap():
    # guard: default matplotlib date labels for 60 days really do collide at 6.4in.
    fig, ax = plt.subplots()
    d = pd.date_range("2024-01-01", periods=60)
    ax.plot(d, np.random.default_rng(1).normal(size=60).cumsum())
    ax.set_ylabel("Cases (count)")
    assert "LY101" in ids(lint(fig))


def test_ly101_plotnine_date_fix_does_not_suggest_more_breaks():
    # FAILS TODAY. User already has date_breaks='2 years'; the fix suggests
    # date_breaks='1 year' (twice as many labels). Expected: a coarser suggestion.
    p = (
        ggplot(economics, aes("date", "unemploy"))
        + geom_line()
        + scale_x_datetime(date_breaks="2 years", date_labels="%Y")
        + labs(x="Year", y="Unemployed (thousands)")
    )
    hits = findings(lint(p), "LY101")
    assert hits
    assert "date_breaks='1 year'" not in hits[0].fix


# =====================================================================
# AX102 / LB201: seaborn grids
# =====================================================================
def test_pairplot_diagonal_twins_are_not_dual_axes():
    # FAILS TODAY. pairplot's diagonal KDE axes are twinx() with the y-axis hidden.
    # Expected: no AX102. Actual: AX102 (error) "overlays two axes with independent scales".
    g = sns.pairplot(penguins(), hue="species")
    assert "AX102" not in ids(lint(g.figure))


def test_lb201_ignores_hidden_axis_labels():
    # FAILS TODAY. jointplot marginal axes keep 'bill_length_mm' as an invisible label.
    # Expected: no LB201 once set_axis_labels() is used. Actual: two LB201 warnings.
    g = sns.jointplot(data=penguins(), x="bill_length_mm", y="body_mass_g", alpha=0.4)
    g.set_axis_labels("Bill length (mm)", "Body mass (g)")
    assert "LB201" not in ids(lint(g.figure))


def test_lb201_reports_a_repeated_facet_label_once():
    # FAILS TODAY. One raw column name shared by 3 facets. Expected: one LB201.
    # Actual: three identical findings (one per panel); pairplot gives 17.
    g = sns.FacetGrid(penguins(), col="species")
    g.map(plt.hist, "body_mass_g", bins=np.arange(2000, 7001, 250))
    g.set_ylabels("Count")
    assert len(findings(lint(g.figure), "LB201")) == 1


def test_lb201_fix_keeps_units_from_the_name():
    # guard (fixed in src during this review; the fix used to read
    # 'Bill length mm (units)'). Expected fix like labs(x='Bill length (mm)').
    p = ggplot(penguins(), aes("bill_length_mm", "body_mass_g")) + geom_point(alpha=0.4)
    fixes = [f.fix for f in findings(lint(p), "LB201")]
    assert any("(mm)" in fx for fx in fixes), fixes


# =====================================================================
# CL201: calibration and redundancy
# =====================================================================
def test_cl201_accepts_seaborn_colorblind_palette():
    # FAILS TODAY. Four lines in sns.color_palette('colorblind') (an Okabe-Ito variant).
    # Expected: no CL201. Actual: CL201 error (deuteranopia, ΔE 9.0 < 10).
    pal = sns.color_palette("colorblind")
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    for i, name in enumerate(["A", "B", "C", "D"]):
        ax.plot(
            np.arange(10),
            np.arange(10) * (i + 1) + rng.normal(0, 1, 10),
            color=pal[i],
            label=name,
        )
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.set(xlabel="Week", ylabel="Sales (USD)")
    assert "CL201" not in ids(lint(fig))


def test_cl201_skips_color_redundant_with_axis_plotnine():
    # FAILS TODAY. fill repeats x and the legend is hidden (the fix LB203 suggests);
    # categories are named on the axis, so CVD can't hide them.
    # Expected: no CL201. Actual: CL201 error ('4' vs 'f').
    p = (
        ggplot(mpg, aes("drv", fill="drv"))
        + geom_bar(show_legend=False)
        + labs(x="Drive", y="Count")
    )
    assert "CL201" not in ids(lint(p))


def test_cl201_skips_color_redundant_with_axis_seaborn():
    # FAILS TODAY. seaborn 0.13's recommended idiom hue=x, legend=False.
    # Expected: no CL201. Actual: CL201 error (tab10 orange/green).
    ax = sns.countplot(data=penguins(), x="species", hue="species", legend=False)
    ax.set(xlabel="Species", ylabel="Penguins (count)")
    assert "CL201" not in ids(lint(ax.figure))


def test_cl201_one_finding_when_color_and_fill_map_same_variable():
    # FAILS TODAY. color='drv', fill='drv' on one density layer.
    # Expected: one CL201. Actual: two (one for color, one for fill).
    p = (
        ggplot(mpg, aes("hwy", color="drv", fill="drv"))
        + geom_density(alpha=0.3)
        + labs(x="Highway (mpg)", y="Density", color="Drive", fill="Drive")
        # plotnine's default hue palette changed in 0.14; pin a red-green palette
        + scale_color_manual(values=["#f8766d", "#00ba38", "#619cff"])
        + scale_fill_manual(values=["#f8766d", "#00ba38", "#619cff"])
    )
    assert len(findings(lint(p), "CL201")) == 1


def test_cl201_same_verdict_for_seaborn_scatter_and_scatter_loop():
    # FAILS TODAY. Same three tab10 colors; plt.scatter loop -> CL201, but
    # sns.scatterplot(hue=...) -> nothing (one PathCollection with per-point colors
    # gets color=None in the render adapter). Expected: same verdict.
    df = penguins()
    fig, ax = plt.subplots()
    for sp, d in df.groupby("species"):
        ax.scatter(d.bill_length_mm, d.body_mass_g, label=sp, alpha=0.6)
    ax.set(xlabel="Bill length (mm)", ylabel="Body mass (g)")
    loop = "CL201" in ids(lint(fig))
    _, ax2 = plt.subplots()
    sns.scatterplot(
        data=df, x="bill_length_mm", y="body_mass_g", hue="species", alpha=0.6, ax=ax2
    )
    ax2.set(xlabel="Bill length (mm)", ylabel="Body mass (g)")
    seaborn = "CL201" in ids(lint(ax2.figure))
    assert loop == seaborn


def test_cl201_default_palette_is_not_an_error():
    # Decided: the color-vision rule is Tier 2 (CL201, warning), not Tier 1 (was CL103),
    # because it fires on most library default palettes with 3+ groups.
    fig, ax = plt.subplots()
    x = np.arange(10)
    for k in range(3):
        ax.plot(x, x * (k + 1), label=f"Group {k}")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.set(xlabel="Week", ylabel="Sales (USD)")
    hits = findings(lint(fig), "CL201")
    assert all(f.severity < Severity.ERROR for f in hits)


# =====================================================================
# Other rules
# =====================================================================
def test_ax103_ignores_empty_bins_in_log_histogram():
    # FAILS TODAY. plt.hist(..., log=True) with empty tail bins. Expected: no AX103
    # (no data is dropped; empty bins are just empty). Actual: AX103 error
    # "6 plotted values are at or below zero" with a symlog fix.
    fig, ax = plt.subplots()
    ax.hist(
        np.random.default_rng(1).exponential(1, 500),
        bins=np.arange(0, 10, 0.5).tolist(),
        log=True,
    )
    ax.set(xlabel="Wait time (min)", ylabel="Count")
    assert "AX103" not in ids(lint(fig))


def test_ax201_dodged_bar_count_is_number_of_categories():
    # FAILS TODAY. 7 classes dodged by drv. Expected message "The 7 bars ...".
    # Actual: "The 12 bars for `class`" (counts dodged sub-bars by their shifted x).
    p = (
        ggplot(mpg, aes("class", fill="drv"))
        + geom_bar(position="dodge")
        + labs(x="Vehicle class", y="Count", fill="Drive")
    )
    hits = findings(lint(p), "AX201")
    assert hits and "7 bars" in hits[0].message, [h.message for h in hits]


def test_lint_accepts_array_of_axes():
    # FAILS TODAY. `axes = df.hist()` / plt.subplots(1, 2) return ndarrays of Axes;
    # students will pass them straight in. Expected: lints the figure. Actual: TypeError.
    _fig, axes = plt.subplots(1, 2)
    for a in axes:
        a.plot([1, 2, 3], [1, 4, 9])
        a.set(xlabel="Time (s)", ylabel="Distance (m)")
    lint(axes)


# =====================================================================
# guards: well-made student plots stay clean
# =====================================================================
def test_guard_clean_seaborn_heatmap():
    corr = penguins().select_dtypes("number").corr()
    ax = sns.heatmap(corr, annot=True, cmap="coolwarm", vmin=-1, vmax=1)
    assert lint(ax.figure).findings == []


def test_guard_clean_subplot_grid():
    fig, axes = plt.subplots(2, 2, figsize=(8, 6))
    rng = np.random.default_rng(0)
    for i, ax in enumerate(axes.flat):
        ax.plot(np.arange(20), rng.normal(size=20).cumsum())
        ax.set(xlabel="Day", ylabel="Price (USD)", title=f"Stock {i}")
    fig.tight_layout()
    assert lint(fig).findings == []


def test_guard_legend_over_bar_is_flagged():
    # guard: seaborn puts the hue legend over the tallest bar here; LY102 is right.
    # (legend placed explicitly: loc="best" differs between matplotlib versions)
    rng = np.random.default_rng(1)
    tips = pd.DataFrame(
        {
            "day": rng.choice(
                ["Thur", "Fri", "Sat", "Sun"], 244, p=[0.55, 0.15, 0.15, 0.15]
            ),
            "time": rng.choice(["Lunch", "Dinner"], 244),
        }
    )
    ax = sns.countplot(data=tips, x="day", hue="time")
    sns.move_legend(ax, "upper left")
    ax.set(xlabel="Day", ylabel="Tables (count)")
    assert "LY102" in ids(lint(ax.figure))

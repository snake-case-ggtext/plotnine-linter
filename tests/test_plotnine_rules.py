"""Each rule on plotnine plots: one plot that should trigger it, one that shouldn't."""

import numpy as np
import pandas as pd
import pytest

pn = pytest.importorskip("plotnine")
from plotnine import (
    aes,
    coord_cartesian,
    coord_flip,
    facet_wrap,
    geom_bar,
    geom_col,
    geom_histogram,
    geom_jitter,
    geom_line,
    geom_point,
    ggplot,
    labs,
    scale_color_cmap,
    scale_color_manual,
    scale_y_log10,
    stat_summary,
    theme,
)

from plotnine_linter import lint

from .conftest import ids

OKABE = [
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#F0E442",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#000000",
]


def good_bars(df):
    """A bar chart a careful author would make: sorted, labeled, no redundant legend."""
    return (
        ggplot(df, aes("reorder(region_name, avg_income_usd)", "avg_income_usd"))
        + geom_col()
        + coord_flip()
        + labs(
            x="Region",
            y="Average income (USD, thousands)",
            title="West and North earn the most",
        )
    )


def test_clean_plot_has_no_findings(regions):
    report = lint(good_bars(regions))
    assert report.findings == [], str(report)
    assert report.internal_errors == []


def test_lint_does_not_mutate_plot(regions):
    p = ggplot(regions, aes("region_name", "avg_income_usd")) + geom_col()
    before = (dict(p.mapping), len(p.layers), vars(p.labels).copy())
    lint(p)
    assert (dict(p.mapping), len(p.layers), vars(p.labels)) == before
    lint(p)  # linting twice works


# ---------------------------------------------------------------- tier 1
def test_ax101_bars_truncated(regions):
    p = good_bars(regions) + coord_cartesian(ylim=(40, 65))
    assert "AX101" in ids(lint(p))


def test_ax101_full_bars_ok(regions):
    assert "AX101" not in ids(lint(good_bars(regions)))


def test_ax103_log_drops_values():
    df = pd.DataFrame({"x": [1, 2, 3, 4], "y": [0, 10, 100, 1000]})
    p = ggplot(df, aes("x", "y")) + geom_point() + scale_y_log10()
    assert "AX103" in ids(lint(p))
    df2 = df.assign(y=[1, 10, 100, 1000])
    assert "AX103" not in ids(
        lint(ggplot(df2, aes("x", "y")) + geom_point() + scale_y_log10())
    )


def test_cl101_rainbow():
    df = pd.DataFrame({"x": range(10), "y": range(10), "z": np.linspace(0, 1, 10)})
    assert "CL101" in ids(
        lint(
            ggplot(df, aes("x", "y", color="z"))
            + geom_point()
            + scale_color_cmap(cmap_name="jet")
        )
    )
    assert "CL101" not in ids(
        lint(
            ggplot(df, aes("x", "y", color="z"))
            + geom_point()
            + scale_color_cmap(cmap_name="viridis")
        )
    )


def test_cl102_too_many_colors():
    df = pd.DataFrame({"x": range(12), "y": range(12), "g": list("abcdefghijkl")})
    assert "CL102" in ids(lint(ggplot(df, aes("x", "y", color="g")) + geom_point()))
    df["g"] = list("abcd") * 3
    assert "CL102" not in ids(lint(ggplot(df, aes("x", "y", color="g")) + geom_point()))


def test_cl201_red_green_palette_confusable():
    df = pd.DataFrame({"x": range(9), "y": range(9), "g": list("abc") * 3})
    # plotnine >= 0.14's default hue
    red_green = scale_color_manual(values=["#f8766d", "#00ba38", "#619cff"])
    assert "CL201" in ids(
        lint(ggplot(df, aes("x", "y", color="g")) + geom_point() + red_green)
    )


def test_cl201_okabe_ito_ok_and_redundant_shape_ok():
    df = pd.DataFrame({"x": range(9), "y": range(9), "g": list("abc") * 3})
    assert "CL201" not in ids(
        lint(
            ggplot(df, aes("x", "y", color="g"))
            + geom_point()
            + scale_color_manual(values=OKABE[:3])
        )
    )
    assert "CL201" not in ids(
        lint(ggplot(df, aes("x", "y", color="g", shape="g")) + geom_point())
    )


def test_ly101_overlapping_labels():
    df = pd.DataFrame(
        {
            "name": [f"a very long category name {i}" for i in range(12)],
            "v": range(1, 13),
        }
    )
    p = (
        ggplot(df, aes("name", "v"))
        + geom_col()
        + labs(x="Category", y="Value (count)")
    )
    assert "LY101" in ids(lint(p))
    assert "LY101" not in ids(lint(p + coord_flip()))


def test_mk101_overplotting(cloud):
    assert "MK101" in ids(lint(ggplot(cloud, aes("x", "y")) + geom_point()))
    assert "MK101" not in ids(
        lint(ggplot(cloud, aes("x", "y")) + geom_point(alpha=0.2))
    )


def test_mk101_points_stacked_on_categories():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"grp": np.repeat(list("abc"), 30), "v": rng.normal(size=90)})
    assert "MK101" in ids(lint(ggplot(df, aes("grp", "v")) + geom_point()))
    assert "MK101" not in ids(
        lint(ggplot(df, aes("grp", "v")) + geom_jitter(width=0.2, height=0))
    )


def test_mk103_line_over_nominal():
    df = pd.DataFrame({"fruit": ["apple", "kiwi", "banana", "pear"], "n": [3, 5, 2, 4]})
    p = ggplot(df, aes("fruit", "n", group=1)) + geom_line()
    assert "MK103" in ids(lint(p))
    months = pd.DataFrame({"month": ["Jan", "Feb", "Mar", "Apr"], "n": [3, 5, 2, 4]})
    assert "MK103" not in ids(
        lint(ggplot(months, aes("month", "n", group=1)) + geom_line())
    )


# ---------------------------------------------------------------- tier 2
def test_lb201_raw_names(regions):
    report = lint(ggplot(regions, aes("region_name", "avg_income_usd")) + geom_col())
    msgs = [f.message for f in report if f.rule_id == "LB201"]
    assert len(msgs) == 2
    assert "LB201" not in ids(lint(good_bars(regions)))


def test_lb201_readable_column_name_ok():
    df = pd.DataFrame({"Region": list("abcd"), "Income (USD)": [4, 3, 2, 1]})
    assert "LB201" not in ids(
        lint(ggplot(df, aes("Region", "Income (USD)")) + geom_col())
    )


def test_lb301_units_is_opt_in(regions):
    p = good_bars(regions) + labs(y="Average income")
    assert "LB301" not in ids(lint(p))
    found = [f for f in lint(p, select=["LB301"]) if f.rule_id == "LB301"]
    assert found and found[0].severity.name == "INFO"


def test_lb203_redundant_legend(regions):
    p = (
        ggplot(regions, aes("region_name", "avg_income_usd", fill="region_name"))
        + geom_col()
    )
    assert "LB203" in ids(lint(p))
    assert "LB203" not in ids(lint(p + theme(legend_position="none")))
    assert "LB203" not in ids(
        lint(
            ggplot(regions, aes("region_name", "avg_income_usd", fill="region_name"))
            + geom_col(show_legend=False)
        )
    )


def test_ax201_unsorted(regions):
    assert "AX201" in ids(
        lint(ggplot(regions, aes("region_name", "avg_income_usd")) + geom_col())
    )


def test_ax201_ordinal_and_ordered_ok():
    months = pd.DataFrame(
        {"m": ["Jan", "Feb", "Mar", "Apr", "May"], "v": [3, 1, 4, 1, 5]}
    )
    assert "AX201" not in ids(lint(ggplot(months, aes("m", "v")) + geom_col()))
    df = pd.DataFrame(
        {
            "g": pd.Categorical(list("cabd"), categories=list("dcba"), ordered=True),
            "v": [3, 1, 4, 2],
        }
    )
    assert "AX201" not in ids(lint(ggplot(df, aes("g", "v")) + geom_col()))


def test_ax202_rotated_labels(regions):
    p = (
        ggplot(regions, aes("region_name", "avg_income_usd"))
        + geom_col()
        + theme(axis_text_x=pn.element_text(rotation=45))
    )
    assert "AX202" in ids(lint(p))


def test_ax202_long_horizontal_labels_that_fit_are_fine():
    # calibration: a character count was wrong every time; colliding labels are LY101's job
    df = pd.DataFrame(
        {
            "name": ["an extremely long label", "another long one here", "short"],
            "v": [3, 2, 1],
        }
    )
    p = ggplot(df, aes("name", "v")) + geom_col() + labs(x="Name", y="Value (count)")
    assert "AX202" not in ids(lint(p))


def test_ax203_free_facets():
    df = pd.DataFrame({"x": range(8), "y": range(8), "f": list("ab") * 4})
    assert "AX203" in ids(
        lint(
            ggplot(df, aes("x", "y")) + geom_point() + facet_wrap("f", scales="free_y")
        )
    )
    assert "AX203" not in ids(
        lint(ggplot(df, aes("x", "y")) + geom_point() + facet_wrap("f"))
    )


def test_ax204_default_bins(cloud):
    assert "AX204" in ids(lint(ggplot(cloud, aes("x")) + geom_histogram()))
    assert "AX204" not in ids(
        lint(ggplot(cloud, aes("x")) + geom_histogram(binwidth=0.25))
    )


def test_mk202_spaghetti():
    df = pd.DataFrame(
        {
            "t": np.tile(range(5), 10),
            "v": np.arange(50.0),
            "g": np.repeat(list("abcdefghij"), 5),
        }
    )
    assert "MK202" in ids(lint(ggplot(df, aes("t", "v", color="g")) + geom_line()))
    assert "MK202" not in ids(
        lint(ggplot(df[df.g < "d"], aes("t", "v", color="g")) + geom_line())
    )


def test_mk203_summary_bars():
    df = pd.DataFrame({"g": list("ab") * 10, "v": np.arange(20.0)})
    bars = ggplot(df, aes("g", "v")) + stat_summary(geom="bar", fun_y=np.mean)
    assert "MK203" in ids(lint(bars))
    with_err = bars + stat_summary(
        geom="errorbar", fun_data="mean_cl_normal", width=0.2
    )
    assert "MK203" not in ids(lint(with_err))


def test_ly201_small_text(regions):
    p = good_bars(regions) + theme(axis_text=pn.element_text(size=6))
    assert "LY201" in ids(lint(p))


def test_ly202_legend_order():
    df = pd.DataFrame(
        {
            "t": np.tile(range(4), 3),
            "v": [1, 2, 3, 4, 2, 3, 4, 9, 0, 1, 1, 2],
            "series": np.repeat(["alpha", "beta", "gamma"], 4),
        }
    )
    p = (
        ggplot(df, aes("t", "v", color="series"))
        + geom_line()
        + scale_color_manual(values=OKABE[:3])
    )
    assert "LY202" in ids(lint(p))
    order = pd.Categorical(df.series, categories=["beta", "alpha", "gamma"])
    assert "LY202" not in ids(
        lint(
            ggplot(df.assign(series=order), aes("t", "v", color="series"))
            + geom_line()
            + scale_color_manual(values=OKABE[:3])
        )
    )


def test_geom_bar_count_unsorted():
    df = pd.DataFrame({"pet": ["cat"] * 5 + ["dog"] * 9 + ["fish"] * 2 + ["bird"] * 7})
    assert "AX201" in ids(lint(ggplot(df, aes("pet")) + geom_bar()))


def test_ax205_months_in_alphabetical_order():
    df = pd.DataFrame(
        {"month": ["Jan", "Feb", "Mar", "Apr", "May"], "n": [3, 5, 2, 4, 6]}
    )
    p = (
        ggplot(df, aes("month", "n", group=1))
        + geom_line()
        + labs(x="Month", y="Visits (count)")
    )
    found = [f for f in lint(p) if f.rule_id == "AX205"]
    assert found and "Categorical" in found[0].fix
    df["month"] = pd.Categorical(
        df.month, categories=["Jan", "Feb", "Mar", "Apr", "May"], ordered=True
    )
    assert "AX205" not in ids(
        lint(ggplot(df, aes("month", "n", group=1)) + geom_line())
    )


# ---------------------------------------------------------------- new rules
def test_cl202_diverging_data_sequential_scale():
    rng = np.random.default_rng(3)
    df = pd.DataFrame(
        {
            "x": np.tile(range(5), 5),
            "y": np.repeat(range(5), 5),
            "change": rng.uniform(-1, 1, 25),
        }
    )
    p = ggplot(df, aes("x", "y", fill="change")) + pn.geom_tile()
    assert "CL202" in ids(lint(p))
    centered = p + pn.scale_fill_gradient2(midpoint=0)
    assert "CL202" not in ids(lint(centered))
    positive = df.assign(change=df.change.abs())
    assert "CL202" not in ids(
        lint(ggplot(positive, aes("x", "y", fill="change")) + pn.geom_tile())
    )


def test_mk204_small_groups_in_box_plot():
    rng = np.random.default_rng(4)
    df = pd.DataFrame({"g": ["a"] * 40 + ["b"] * 5, "v": rng.normal(size=45)})
    p = ggplot(df, aes("g", "v")) + pn.geom_boxplot()
    found = [f for f in lint(p) if f.rule_id == "MK204"]
    assert found and "n = 5" in found[0].message
    assert "MK204" not in ids(lint(p + geom_jitter(width=0.1)))


def test_mk205_many_stacked_segments():
    df = pd.DataFrame(
        {"x": np.repeat(list("abc"), 7), "seg": list("ABCDEFG") * 3, "v": 1.0}
    )
    assert "MK205" in ids(lint(ggplot(df, aes("x", "v", fill="seg")) + geom_col()))
    assert "MK205" not in ids(
        lint(ggplot(df, aes("x", "v", fill="seg")) + geom_col(position="dodge"))
    )


def test_lb201_title_and_facet_strips():
    df = pd.DataFrame(
        {"x": range(8), "y": range(8), "org_type": ["non_profit", "for_profit"] * 4}
    )
    p = (
        ggplot(df, aes("x", "y"))
        + geom_point()
        + facet_wrap("org_type")
        + labs(x="X (m)", y="Y (m)", title="org_type_counts")
    )
    msgs = [f.message for f in lint(p) if f.rule_id == "LB201"]
    assert any("title" in m for m in msgs) and any("Facet" in m for m in msgs)


def test_cl203_fill_repeats_axis_without_legend(regions):
    p = (
        ggplot(
            regions,
            aes(
                "reorder(region_name, avg_income_usd)",
                "avg_income_usd",
                fill="reorder(region_name, avg_income_usd)",
            ),
        )
        + geom_col(show_legend=False)
        + coord_flip()
        + labs(x="Region", y="Average income (USD, thousands)")
    )
    assert "CL203" in ids(lint(p))
    assert "CL203" not in ids(lint(good_bars(regions)))

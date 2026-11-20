"""Each rule on plain matplotlib figures."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plotnine_linter import lint

from .conftest import ids

OKABE = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"]


def good_bar():
    fig, ax = plt.subplots()
    s = pd.Series({"West": 52, "North": 58, "East": 61, "Central": 50, "South": 47}).sort_values()
    ax.barh(s.index, s.values, color="#4C72B0")
    ax.set_xlabel("Average income (USD, thousands)")
    ax.set_title("East earns the most")
    return fig


def test_clean_figure_has_no_findings():
    report = lint(good_bar())
    assert report.findings == [], str(report)


def test_axes_argument_works():
    fig = good_bar()
    assert lint(fig.axes[0]).findings == []


# ---------------------------------------------------------------- tier 1
def test_ax101():
    fig, ax = plt.subplots()
    ax.bar(["a", "b", "c"], [50, 55, 60])
    ax.set_ylim(45, 62)
    ax.set_ylabel("Score (points)")
    assert "AX101" in ids(lint(fig))


def test_ax102_twinx():
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.twinx().plot([1, 2, 3], [30, 10, 20])
    assert "AX102" in ids(lint(fig))


def test_ax103_log_with_zero():
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3, 4], [0, 1, 10, 100])
    ax.set_yscale("log")
    assert "AX103" in ids(lint(fig))


def test_cl101_jet():
    fig, ax = plt.subplots()
    ax.imshow(np.random.default_rng(0).random((5, 5)), cmap="jet")
    assert "CL101" in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.imshow(np.random.default_rng(0).random((5, 5)), cmap="viridis")
    assert "CL101" not in ids(lint(fig2))


def test_cl102_many_lines_legend():
    fig, ax = plt.subplots()
    for i in range(10):
        ax.plot([0, 1], [i, i + 1], label=f"Series {i}")
    ax.legend()
    assert "CL102" in ids(lint(fig))


def test_cl201_tab10_orange_green():
    fig, ax = plt.subplots()
    ax.scatter([1, 2], [1, 2], color="#ff7f0e")
    ax.scatter([1, 2], [2, 3], color="#2ca02c")
    assert "CL201" in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.scatter([1, 2], [1, 2], color=OKABE[0])
    ax2.scatter([1, 2], [2, 3], color=OKABE[4])
    assert "CL201" not in ids(lint(fig2))


def test_ly101_overlapping_ticks():
    fig, ax = plt.subplots(figsize=(4, 3))
    names = [f"category number {i}" for i in range(10)]
    ax.bar(names, range(1, 11))
    assert "LY101" in ids(lint(fig))


def test_ly102_legend_over_points():
    fig, ax = plt.subplots()
    x = np.linspace(0, 1, 200)
    ax.plot(x, np.ones_like(x), label="flat line at top")
    ax.plot(x, x, label="diagonal")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right")
    assert "LY102" in ids(lint(fig))


def test_lb101_missing_label_and_shared_ok():
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [4, 5, 6])
    report = lint(fig)
    assert [f.rule_id for f in report].count("LB101") == 2
    fig, axes = plt.subplots(1, 2, sharey=True)
    for a in axes:
        a.plot([1, 2], [1, 2])
        a.set_xlabel("Time (s)")
    axes[0].set_ylabel("Distance (m)")
    assert "LB101" not in ids(lint(fig))


def test_mk101_scatter_density():
    rng = np.random.default_rng(0)
    fig, ax = plt.subplots()
    ax.scatter(rng.normal(size=5000), rng.normal(size=5000))
    assert "MK101" in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.scatter(rng.normal(size=5000), rng.normal(size=5000), alpha=0.1)
    assert "MK101" not in ids(lint(fig2))


def test_mk102_bar3d():
    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")
    ax.bar3d([0, 1, 2], [0, 0, 0], [0, 0, 0], 0.5, 0.5, [1, 2, 3])
    assert "MK102" in ids(lint(fig))


def test_mk102_surface_ok():
    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")
    X, Y = np.meshgrid(np.linspace(-1, 1, 7), np.linspace(-1, 1, 7))
    ax.plot_surface(X, Y, X**2 + Y**2)
    assert "MK102" not in ids(lint(fig))


def test_mk103_line_over_categories():
    fig, ax = plt.subplots()
    ax.plot(["apple", "kiwi", "pear"], [3, 1, 2])
    assert "MK103" in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.plot(["Jan", "Feb", "Mar"], [3, 1, 2])
    assert "MK103" not in ids(lint(fig2))


# ---------------------------------------------------------------- tier 2
def test_lb201_pandas_plot_labels():
    df = pd.DataFrame({"year": [2020, 2021, 2022], "total_sales": [3, 4, 5]}).set_index("year")
    ax = df.plot()
    report = lint(ax.figure)
    assert "LB201" in ids(report)  # legend entry "total_sales"


def test_lb203_legend_repeats_categories():
    fig, ax = plt.subplots()
    for name, v in zip(["a", "b", "c"], [1, 2, 3]):
        ax.bar(name, v, label=name)
    ax.legend()
    assert "LB203" in ids(lint(fig))


def test_ax201_unsorted_bars():
    fig, ax = plt.subplots()
    ax.bar(["dog", "cat", "fish", "bird"], [5, 9, 2, 7])
    assert "AX201" in ids(lint(fig))


def test_ax202_rotated_category_labels():
    fig, ax = plt.subplots()
    ax.bar(["dog", "cat", "fish"], [9, 5, 2])
    ax.tick_params(axis="x", labelrotation=45)
    assert "AX202" in ids(lint(fig))


def test_ax202_rotated_dates_gets_date_fix():
    fig, ax = plt.subplots()
    dates = pd.date_range("2024-01-01", periods=12, freq="MS")
    ax.plot(dates, range(12))
    ax.tick_params(axis="x", labelrotation=45)
    found = [f for f in lint(fig) if f.rule_id == "AX202"]
    assert found and "Date" in found[0].message


def test_ax204_default_hist_is_info():
    fig, ax = plt.subplots()
    ax.hist(np.random.default_rng(0).normal(size=500))
    found = [f for f in lint(fig) if f.rule_id == "AX204"]
    assert found and found[0].severity.name == "INFO"


def test_mk201_pie():
    fig, ax = plt.subplots()
    ax.pie([1, 2, 3, 4, 5, 6])
    assert "MK201" in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.pie([1, 2, 3])
    assert "MK201" not in ids(lint(fig2))


def test_mk202_spaghetti():
    fig, ax = plt.subplots()
    for i in range(9):
        ax.plot([0, 1, 2], [i, i + 1, i])
    assert "MK202" in ids(lint(fig))


def test_ly201_small_text():
    fig, ax = plt.subplots()
    ax.plot([1, 2], [1, 2])
    ax.set_xlabel("Time (s)", fontsize=6)
    assert "LY201" in ids(lint(fig))


def test_ly202_legend_order():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], label="low end")
    ax.plot([0, 1], [0, 5], label="high end")
    ax.plot([0, 1], [0, 3], label="middle")
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
    assert "LY202" in ids(lint(fig))


def test_ax205_months_out_of_order():
    fig, ax = plt.subplots()
    ax.bar(["Mar", "Jan", "Feb"], [3, 1, 2])
    ax.set_ylabel("Visits (count)")
    assert "AX205" in ids(lint(fig))


def test_lb101_skips_polar_axes():
    fig = plt.figure()
    ax = fig.add_subplot(projection="polar")
    ax.plot(np.linspace(0, 6, 50), np.linspace(0, 1, 50))
    assert "LB101" not in ids(lint(fig))


def test_cl202_correlation_heatmap_sequential():
    rng = np.random.default_rng(5)
    corr = np.corrcoef(rng.normal(size=(4, 50)))
    corr[0, 1] = corr[1, 0] = -0.8
    fig, ax = plt.subplots()
    ax.imshow(corr, cmap="viridis")
    assert "CL202" in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    assert "CL202" not in ids(lint(fig2))
    fig4, ax4 = plt.subplots()  # diverging, but its limits follow lopsided data
    ax4.imshow(np.array([[-0.2, 1.0], [0.5, 0.9]]), cmap="RdBu_r")
    assert "CL202" in ids(lint(fig4))


def test_mk205_pandas_stacked_bars():
    df = pd.DataFrame(np.ones((3, 7)), columns=list("ABCDEFG"), index=list("xyz"))
    ax = df.plot.bar(stacked=True)
    assert "MK205" in ids(lint(ax.figure))
    ax2 = df.iloc[:, :3].plot.bar(stacked=True)
    assert "MK205" not in ids(lint(ax2.figure))


# ---------------------------------------------------------------- from the COGS 108 image audit
def test_cl203_each_bar_its_own_color():
    fig, ax = plt.subplots()
    ax.bar(["dog", "cat", "fish", "bird"], [9, 7, 5, 2], color=["C0", "C1", "C2", "C3"])
    ax.set_ylabel("Pets (count)")
    assert "CL203" in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.bar(["dog", "cat", "fish", "bird"], [9, 7, 5, 2], color="#4C72B0")
    ax2.set_ylabel("Pets (count)")
    assert "CL203" not in ids(lint(fig2))


def test_lb203_single_entry_legend():
    s = pd.Series([3, 4, 5], index=pd.Index([2020, 2021, 2022], name="Year"), name="Sales")
    ax = s.plot(legend=True)
    assert "LB203" in ids(lint(ax.figure))


def test_lb205_percent_label_on_fractions():
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0.1, 0.4, 0.8])
    ax.set_xlabel("Week")
    ax.set_ylabel("Students passing (%)")
    found = [f for f in lint(fig) if f.rule_id == "LB205"]
    assert found and found[0].severity.name == "INFO"


def test_lb205_density_label_on_counts():
    fig, ax = plt.subplots()
    ax.hist(np.random.default_rng(0).normal(size=300), bins=np.arange(-4, 4.5, 0.5))
    ax.set_xlabel("Score (z)")
    ax.set_ylabel("Density")
    assert "LB205" in ids(lint(fig))


def test_lb206_offset_notation():
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1.1e8, 1.5e8, 1.3e8])
    ax.set_xlabel("Year")
    ax.set_ylabel("Revenue (USD)")
    assert "LB206" in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.plot([1, 2, 3], [110, 150, 130])
    ax2.set_xlabel("Year")
    ax2.set_ylabel("Revenue (millions USD)")
    assert "LB206" not in ids(lint(fig2))


def test_ax206_log_values_on_linear_axis():
    fig, ax = plt.subplots()
    ax.scatter([1, 2, 3, 4], np.log10([10, 100, 1000, 10000]))
    ax.set_xlabel("Year")
    ax.set_ylabel("log10(population)")
    found = [f for f in lint(fig) if f.rule_id == "AX206"]
    assert found and found[0].severity.name == "INFO"


def test_ax207_fractional_year_ticks():
    fig, ax = plt.subplots()
    ax.plot([2017, 2018, 2019, 2020], [3, 5, 4, 6])
    ax.set_xlabel("Year")
    ax.set_ylabel("Visitors (millions)")
    assert "AX207" in ids(lint(fig))
    from matplotlib.ticker import MaxNLocator

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    assert "AX207" not in ids(lint(fig))
    fig2, ax2 = plt.subplots()  # two measurements at 1 s and 2 s: fractional ticks are fine
    ax2.plot([1, 2], [1, 2])
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Distance (m)")
    assert "AX207" not in ids(lint(fig2))


# ---------------------------------------------------------------- accessibility
def test_ly103_low_contrast_text():
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 3, 2])
    ax.set_xlabel("Time (s)", color="#cccccc")
    ax.set_ylabel("Distance (m)")
    found = [f for f in lint(fig) if f.rule_id == "LY103"]
    assert found and found[0].severity.name == "ERROR"
    ax.set_xlabel("Time (s)", color="#333333")
    assert "LY103" not in ids(lint(fig))


def test_ly103_heatmap_annotations_use_cell_color():
    fig, ax = plt.subplots()
    ax.imshow([[0.0, 1.0]], cmap="Greys", vmin=0, vmax=1)
    ax.text(0, 0, "dark", ha="center", va="center", color="black", fontsize=14)
    ax.text(1, 0, "light", ha="center", va="center", color="white", fontsize=14)
    assert "LY103" not in ids(lint(fig))


def test_cl204_low_contrast_marks():
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 3, 2], color="#F0E442", label="Yellow")
    ax.plot([1, 2, 3], [2, 1, 3], color="#0072B2", label="Blue")
    ax.legend()
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Distance (m)")
    assert "CL204" in ids(lint(fig))


def test_cl204_gray_context_and_outlines_are_fine():
    fig, ax = plt.subplots()
    for i in range(6):
        ax.plot([0, 1, 2], [i, i + 1, i], color="#d9d9d9")
    ax.plot([0, 1, 2], [2, 5, 1], color="#D55E00")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Distance (m)")
    assert "CL204" not in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.bar(["a", "b"], [2, 1], color="#ffff99", edgecolor="#333333")
    assert "CL204" not in ids(lint(fig2))


def test_cl301_color_only_in_grayscale_opt_in():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], color="#E69F00", label="A")  # Okabe orange and sky blue: same gray
    ax.plot([0, 1], [1, 0], color="#56B4E9", label="B")
    ax.legend()
    assert "CL301" not in ids(lint(fig))  # tier 3: off by default
    found = [f for f in lint(fig, profile="accessibility") if f.rule_id == "CL301"]
    assert found and found[0].severity.name == "WARNING"
    fig2, ax2 = plt.subplots()
    ax2.plot([0, 1], [0, 1], color="#E69F00", label="A")
    ax2.plot([0, 1], [1, 0], color="#56B4E9", linestyle="--", label="B")
    ax2.legend()
    assert "CL301" not in ids(lint(fig2, profile="accessibility"))


# ---------------------------------------------------------------- calibration regressions (COGS 108 run)
def test_empty_figure_is_not_linted():
    fig, ax = plt.subplots()  # a cell that failed before plotting
    report = lint(fig)
    assert report.empty and report.findings == []


def test_touching_bars_are_not_a_histogram_once_tagged():
    from plotnine_linter.describe.render import tag_histograms

    tag_histograms()
    fig, ax = plt.subplots()
    ax.bar(range(10), [3, 5, 2, 6, 4, 7, 1, 8, 5, 3], width=1)
    ax.set_xlabel("Rating (1-10)")
    ax.set_ylabel("Reviews (count)")
    assert "AX204" not in ids(lint(fig))
    fig2, ax2 = plt.subplots()
    ax2.hist(np.random.default_rng(0).normal(size=300))
    assert "AX204" in ids(lint(fig2))


def test_ly102_legend_over_pie():
    fig, ax = plt.subplots()
    ax.pie([5, 4, 3], labels=None)
    ax.legend(["A", "B", "C"], loc="center")
    assert "LY102" in ids(lint(fig))


def test_cl201_pair_differing_in_marker_is_fine():
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0, 1, 2], color="red", marker="o", label="A")
    ax.plot([0, 1, 2], [2, 1, 0], color="green", marker="s", label="B")
    ax.legend()
    assert "CL201" not in ids(lint(fig))


def test_lb201_human_labels_are_not_code():
    fig, ax = plt.subplots()
    ax.scatter([1, 2, 3, 4], [4, 3, 2, 1])
    ax.set_xlabel("Price($)")
    ax.set_ylabel("Temperature/Humidity")
    assert "LB201" not in ids(lint(fig))
    ax.set_ylabel("Death_Penalty?")
    assert "LB201" in ids(lint(fig))


def test_ax205_reversed_natural_order_is_fine():
    fig, ax = plt.subplots()
    ax.bar(["Large", "Medium", "Small"], [3, 2, 1])
    ax.set_ylabel("Orders (count)")
    assert "AX205" not in ids(lint(fig))

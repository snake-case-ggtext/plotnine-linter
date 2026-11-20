"""Build the before/after gallery: docs/GALLERY.md and docs/gallery/img/.

Each rule in the catalog has a BEFORE snippet that breaks the rule. It also
has an AFTER snippet that follows the rule's fix. The script lints both with
all three tiers. It fails unless the rule flags BEFORE and not AFTER.

AFTER plots are model answers. The script prints any finding left on one. With
``--strict``, those findings also make it exit with an error.

GALLERY.md shows the snippets below as diffs. Run it from the package root:

    python docs/gallery/make_gallery.py --strict
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import tempfile
import textwrap
import warnings
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from plotnine import ggplot, theme_gray, theme_set

from plotnine_linter import lint
from plotnine_linter.config import Config
from plotnine_linter.registry import load_catalog
from plotnine_linter.session import Session

HERE = Path(__file__).resolve().parent
IMG = HERE / "img"
GALLERY_MD = HERE.parent / "GALLERY.md"

SELECT = [
    "tier1",
    "tier2",
]  # the default rules, plus each example's own rule (for opt-in tier 3)
SIZE = (5.0, 3.5)  # inches, one figure
SMALL = (3.6, 2.7)  # inches, each figure of a two-figure (session) example
DPI = 90

# Every snippet runs in a fresh copy of this namespace.
PRELUDE = """\
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from plotnine import *
from mizani.labels import label_percent

def plain(breaks):  # tick labels like 0.1, 10, 1,000 instead of 1e-1, 1e1, 1e3
    return [f"{b:,g}" for b in breaks]

OKABE = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"]
rng = np.random.default_rng(2026)
"""


def code(s: str) -> str:
    return textwrap.dedent(s).strip("\n") + "\n"


def join(*parts: str) -> str:
    return "".join(code(p) for p in parts)


@dataclass
class Example:
    rule: str
    data: str  # shared setup, shown collapsed
    before: str  # must leave `p` (one plot) or `figs` (a list, for session rules)
    after: str
    note: str = ""  # extra explanation shown under the images

    def __post_init__(self):
        self.data, self.before, self.after = (
            code(self.data),
            code(self.before),
            code(self.after),
        )

    @property
    def multi(self) -> bool:
        return "figs =" in self.before


# --------------------------------------------------------------------------- data shared by several examples
INCOME = """
income = pd.DataFrame({
    "region": ["West", "East", "South", "North", "Central"],
    "income": [52, 61, 47, 58, 50],
})
"""

YEARS = """
years = np.arange(2015, 2025)
cafes = np.array([12, 14, 15, 18, 17, 21, 24, 26, 29, 31])
rent = np.array([1450, 1500, 1580, 1610, 1700, 1690, 1820, 1950, 2040, 2100])
"""

# --------------------------------------------------------------------------- examples
EXAMPLES = [
    # ------------------------------------------------------------------ tier 1
    Example(
        "AX101",
        INCOME,
        before="""
        p = (ggplot(income, aes("reorder(region, income)", "income"))
             + geom_col()
             + coord_cartesian(ylim=(45, 62))
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most, by a modest margin"))
        """,
        after="""
        p = (ggplot(income, aes("reorder(region, income)", "income"))
             + geom_col()
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most, by a modest margin"))
        """,
        note="Zoomed in, East's bar is several times South's; from zero, the bars show it is about 30% more.",
    ),
    Example(
        "AX102",
        YEARS,
        before="""
        fig, ax = plt.subplots()
        ax.plot(years, cafes, color=OKABE[4])
        ax.set_ylabel("Coffee shops (count)")
        ax2 = ax.twinx()
        ax2.plot(years, rent, color=OKABE[5])
        ax2.set_ylabel("Median rent (USD)")
        ax.set_xlabel("Year")
        ax.set_title("Coffee shops and rent rise in lockstep")
        p = fig
        """,
        after="""
        fig, (ax, ax2) = plt.subplots(2, 1, sharex=True)
        ax.plot(years, cafes, color=OKABE[4])
        ax.set_ylabel("Coffee shops\\n(count)")
        ax2.plot(years, rent, color=OKABE[4])
        ax2.set_ylabel("Median rent\\n(USD)")
        ax2.set_xlabel("Year")
        ax.set_title("Coffee shops and rent both rose, 2015-2024")
        p = fig
        """,
        note="With two y-axes the lines can be made to cross anywhere by rescaling one axis; "
        "stacked panels with a shared x-axis show each trend on its own honest scale.",
    ),
    Example(
        "AX103",
        """
        pkg = pd.DataFrame({
            "week": range(1, 13),
            "downloads": [0, 3, 0, 12, 40, 95, 0, 310, 820, 1500, 4100, 9800],
        })
        """,
        before="""
        p = (ggplot(pkg, aes("week", "downloads"))
             + geom_point()
             + scale_x_continuous(breaks=range(2, 13, 2))
             + scale_y_log10()
             + labs(x="Week since release", y="Downloads (count)",
                    title="Downloads grew every week"))
        """,
        after="""
        p = (ggplot(pkg[pkg["downloads"] > 0], aes("week", "downloads"))
             + geom_point()
             + scale_x_continuous(breaks=range(2, 13, 2))
             + scale_y_log10(labels=plain)
             + labs(x="Week since release", y="Downloads (count)",
                    title="Downloads grew about tenfold a month",
                    caption="Weeks 1, 3 and 7 had zero downloads (server outages) and are not shown."))
        """,
        note="The log axis silently drops weeks 1, 3 and 7 (zero downloads), so the before title is wrong. "
        "The after plot drops them on purpose and says so in a caption.",
    ),
    Example(
        "CL101",
        """
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        trips = pd.DataFrame([(d, h) for d in days for h in range(6, 23)], columns=["day", "hour"])
        weekday = trips["day"].isin(days[:5])
        trips["trips"] = np.where(
            weekday,
            40 + 220 * np.exp(-(trips.hour - 8) ** 2 / 2) + 240 * np.exp(-(trips.hour - 17.5) ** 2 / 3),
            60 + 130 * np.exp(-(trips.hour - 14) ** 2 / 12)).round()
        trips["day"] = pd.Categorical(trips["day"], categories=days[::-1], ordered=True)
        """,
        before="""
        p = (ggplot(trips, aes("hour", "day", fill="trips"))
             + geom_tile()
             + scale_fill_cmap("jet")
             + labs(x="Hour of day", y="Day", fill="Trips\\n(count)",
                    title="Weekday rush hours drive bike trips"))
        """,
        after="""
        p = (ggplot(trips, aes("hour", "day", fill="trips"))
             + geom_tile()
             + scale_fill_cmap("viridis")
             + labs(x="Hour of day", y="Day", fill="Trips\\n(count)",
                    title="Weekday rush hours drive bike trips"))
        """,
        note="In `jet`, the bright yellow-cyan band looks like a sharp boundary that isn't in the data; "
        "`viridis` gets steadily lighter as trips increase.",
    ),
    Example(
        "CL102",
        """
        cities = pd.DataFrame({
            "city": ["Oslo", "Lisbon", "Cairo", "Lagos", "Mumbai", "Tokyo",
                     "Sydney", "Lima", "Montreal", "Denver", "Miami", "Seattle"],
            "jan_temp": [-4, 11, 14, 27, 24, 5, 23, 19, -10, -1, 20, 5],
            "rain": [760, 730, 25, 1500, 2200, 1530, 1200, 15, 1000, 400, 1570, 950],
        })
        """,
        before="""
        p = (ggplot(cities, aes("jan_temp", "rain", color="city"))
             + geom_point(size=3)
             + labs(x="Average January temperature (°C)", y="Annual rainfall (mm)",
                    color="City", title="Warm cities are not always wet"))
        """,
        after="""
        p = (ggplot(cities, aes("jan_temp", "rain"))
             + geom_point(size=2, color=OKABE[4])
             + geom_text(aes(label="city"), nudge_y=150, size=9)
             + expand_limits(x=(-14, 31))
             + labs(x="Average January temperature (°C)", y="Annual rainfall (mm)",
                    title="Warm cities are not always wet"))
        """,
        note="Twelve hues can't be matched back to a legend; with one point per city, labeling the points does the job.",
    ),
    Example(
        "LB101",
        """
        years = np.arange(2016, 2025)
        students = [180, 210, 260, 300, 340, 390, 420, 455, 480]
        """,
        before="""
        fig, ax = plt.subplots()
        ax.plot(years, students, marker="o", color=OKABE[4])
        ax.set_title("Intro data science enrollment more than doubled")
        p = fig
        """,
        after="""
        fig, ax = plt.subplots()
        ax.plot(years, students, marker="o", color=OKABE[4])
        ax.set_xlabel("Year")
        ax.set_ylabel("Students enrolled (count)")
        ax.set_title("Intro data science enrollment more than doubled")
        p = fig
        """,
    ),
    Example(
        "LY101",
        """
        majors = pd.DataFrame({
            "major": ["Cognitive Science", "Computer Engineering", "Data Science",
                      "Political Science", "Human Biology", "Mechanical Engineering",
                      "International Studies", "Mathematics-Computer Science"],
            "students": [1450, 1320, 1180, 760, 980, 890, 540, 610],
        })
        """,
        before="""
        p = (ggplot(majors, aes("reorder(major, students)", "students"))
             + geom_col()
             + labs(x="Major", y="Declared students (count)",
                    title="Cognitive Science leads"))
        """,
        after="""
        p = (ggplot(majors, aes("reorder(major, students)", "students"))
             + geom_col()
             + coord_flip()
             + labs(x="Major", y="Declared students (count)",
                    title="Cognitive Science leads"))
        """,
    ),
    Example(
        "LY102",
        """
        n = 60
        birds = pd.DataFrame({
            "Species": np.repeat(["Adelie", "Chinstrap", "Gentoo"], n),
            "Bill length (mm)": np.concatenate([rng.normal(m, 2.5, n) for m in (38.5, 49, 47.5)]),
            "Flipper length (mm)": np.concatenate([rng.normal(m, 6, n) for m in (190, 196, 217)]),
        })
        """,
        before="""
        fig, ax = plt.subplots()
        sns.scatterplot(birds, x="Bill length (mm)", y="Flipper length (mm)",
                        hue="Species", palette=OKABE[:3], ax=ax)
        sns.move_legend(ax, "lower right")
        ax.set_title("Gentoo penguins have the longest flippers")
        p = fig
        """,
        after="""
        fig, ax = plt.subplots()
        sns.scatterplot(birds, x="Bill length (mm)", y="Flipper length (mm)",
                        hue="Species", palette=OKABE[:3], ax=ax)
        sns.move_legend(ax, "upper left", bbox_to_anchor=(1, 1), frameon=False)
        ax.set_title("Gentoo penguins have the longest flippers")
        p = fig
        """,
        note="Naming the columns the way the axis labels should read saves a `set_xlabel` call in seaborn.",
    ),
    Example(
        "MK101",
        """
        n = 3000
        height = rng.normal(170, 9, n)
        people = pd.DataFrame({"height": height, "weight": 0.9 * height - 85 + rng.normal(0, 9, n)})
        """,
        before="""
        p = (ggplot(people, aes("height", "weight"))
             + geom_point()
             + labs(x="Height (cm)", y="Weight (kg)",
                    title="Taller adults tend to weigh more"))
        """,
        after="""
        p = (ggplot(people, aes("height", "weight"))
             + geom_point(alpha=0.15, stroke=0)
             + labs(x="Height (cm)", y="Weight (kg)",
                    title="Taller adults tend to weigh more"))
        """,
        note="At full opacity the center is a solid blob; with transparency the dense core is visible.",
    ),
    Example(
        "MK102",
        """
        sales = pd.Series({"North": 42, "South": 35, "East": 58, "West": 49, "Central": 27})
        """,
        before="""
        fig = plt.figure()
        ax = fig.add_subplot(projection="3d")
        ax.bar3d(range(5), 0, 0, 0.6, 0.6, sales.values, color=OKABE[4])
        ax.set_xticks(range(5), sales.index)
        ax.set_zlabel("Sales (USD, thousands)")
        ax.set_title("East leads regional sales")
        p = fig
        """,
        after="""
        s = sales.sort_values()
        fig, ax = plt.subplots()
        ax.barh(s.index, s.values, color=OKABE[4])
        ax.set_xlabel("Sales (USD, thousands)")
        ax.set_title("East leads regional sales")
        p = fig
        """,
    ),
    Example(
        "MK103",
        """
        drinks = pd.DataFrame({
            "drink": ["Latte", "Mocha", "Espresso", "Cold brew", "Chai"],
            "orders": [140, 55, 80, 120, 45],
        })
        """,
        before="""
        p = (ggplot(drinks, aes("drink", "orders", group=1))
             + geom_line()
             + geom_point()
             + labs(x="Drink", y="Orders per day (count)",
                    title="Lattes and cold brew sell best"))
        """,
        after="""
        p = (ggplot(drinks, aes("reorder(drink, orders)", "orders"))
             + geom_col()
             + coord_flip()
             + labs(x="Drink", y="Orders per day (count)",
                    title="Lattes and cold brew sell best"))
        """,
        note="The line's ups and downs only reflect alphabetical order; drinks have no order between them.",
    ),
    # ------------------------------------------------------------------ tier 2
    Example(
        "AX201",
        INCOME,
        before="""
        p = (ggplot(income, aes("region", "income"))
             + geom_col()
             + coord_flip()
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most, South the least"))
        """,
        after="""
        p = (ggplot(income, aes("reorder(region, income)", "income"))
             + geom_col()
             + coord_flip()
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most, South the least"))
        """,
    ),
    Example(
        "AX202",
        """
        coffee = pd.DataFrame({
            "country": ["Finland", "Norway", "Netherlands", "Germany", "United States", "United Kingdom"],
            "kg": [12.0, 9.9, 8.4, 5.5, 4.4, 2.8],
        })
        """,
        before="""
        p = (ggplot(coffee, aes("reorder(country, -kg)", "kg"))
             + geom_col()
             + theme(axis_text_x=element_text(rotation=45, ha="right"))
             + labs(x="Country", y="Coffee per person (kg per year)",
                    title="Finland drinks the most coffee"))
        """,
        after="""
        p = (ggplot(coffee, aes("reorder(country, kg)", "kg"))
             + geom_col()
             + coord_flip()
             + labs(x="Country", y="Coffee per person (kg per year)",
                    title="Finland drinks the most coffee"))
        """,
    ),
    Example(
        "AX203",
        """
        parks = pd.DataFrame({
            "year": np.tile(np.arange(2016, 2024), 3),
            "park": np.repeat(["Yosemite", "Joshua Tree", "Pinnacles"], 8),
            "visitors": [5.0, 4.3, 4.0, 4.4, 2.3, 3.3, 3.7, 3.9,
                         2.5, 2.9, 2.9, 3.0, 2.4, 3.1, 3.1, 2.9,
                         0.33, 0.22, 0.18, 0.18, 0.14, 0.35, 0.35, 0.28],
        })
        """,
        before="""
        p = (ggplot(parks, aes("year", "visitors"))
             + geom_line()
             + facet_wrap("park", scales="free_y")
             + scale_x_continuous(breaks=[2016, 2019, 2022])
             + labs(x="Year", y="Visitors (millions)",
                    title="Visits to three California parks"))
        """,
        after="""
        p = (ggplot(parks, aes("year", "visitors"))
             + geom_line()
             + facet_wrap("park")
             + scale_x_continuous(breaks=[2016, 2019, 2022])
             + labs(x="Year", y="Visitors (millions)",
                    title="Yosemite draws ten times Pinnacles' visitors"))
        """,
        note="With free scales, Pinnacles' line looks as big as Yosemite's; on a shared scale the gap is clear.",
    ),
    Example(
        "AX204",
        """
        commute = pd.DataFrame({"minutes": rng.gamma(4, 7, 500)})
        """,
        before="""
        p = (ggplot(commute, aes("minutes"))
             + geom_histogram()
             + labs(x="Commute time (minutes)", y="Commuters (count)",
                    title="Most commutes take 15-35 minutes"))
        """,
        after="""
        p = (ggplot(commute, aes("minutes"))
             + geom_histogram(binwidth=5, boundary=0, color="white")
             + labs(x="Commute time (minutes)", y="Commuters (count)",
                    title="Most commutes take 15-35 minutes"))
        """,
        note="Five-minute bins starting at zero mean something to a reader; plotnine's default 30 bins don't.",
    ),
    Example(
        "AX205",
        """
        MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        rain = pd.DataFrame({"month": MONTHS,
                             "mm": [50, 58, 45, 20, 5, 2, 1, 1, 4, 15, 25, 40]})
        """,
        before="""
        p = (ggplot(rain, aes("month", "mm", group=1))
             + geom_line()
             + geom_point()
             + labs(x="Month", y="Average rainfall (mm)",
                    title="San Diego's rain falls in winter"))
        """,
        after="""
        rain["month"] = pd.Categorical(rain["month"], categories=MONTHS, ordered=True)
        p = (ggplot(rain, aes("month", "mm", group=1))
             + geom_line()
             + geom_point()
             + labs(x="Month", y="Average rainfall (mm)",
                    title="San Diego's rain falls in winter"))
        """,
    ),
    Example(
        "AX206",
        """
        mammals = pd.DataFrame({
            "animal": ["Mouse", "Mole", "Rat", "Rabbit", "Cat", "Dog", "Goat",
                       "Chimpanzee", "Human", "Pig", "Cow", "Horse", "Elephant"],
            "body_kg": [0.023, 0.12, 0.28, 2.5, 3.3, 10, 27.7, 52, 62, 192, 465, 521, 6654],
            "brain_g": [0.4, 1.2, 1.9, 12.1, 25.6, 72, 115, 440, 1320, 180, 423, 655, 5712],
        })
        """,
        before="""
        p = (ggplot(mammals, aes("np.log10(body_kg)", "np.log10(brain_g)"))
             + geom_point()
             + labs(x="log10 body mass (kg)", y="log10 brain mass (g)",
                    title="Bigger mammals have bigger brains"))
        """,
        after="""
        p = (ggplot(mammals, aes("body_kg", "brain_g"))
             + geom_point()
             + scale_x_log10(labels=plain)
             + scale_y_log10(labels=plain)
             + labs(x="Body mass (kg)", y="Brain mass (g)",
                    title="Bigger mammals have bigger brains (log-log)"))
        """,
        note="Is a brain at 2.5 big? On a log-scaled axis the ticks read 1, 10, 100 g instead.",
    ),
    Example(
        "AX207",
        """
        enrollment = pd.DataFrame({"year": [2019, 2020, 2021, 2022, 2023],
                                   "students": [612, 655, 701, 690, 748]})
        """,
        before="""
        fig, ax = plt.subplots()
        ax.plot(enrollment.year, enrollment.students, marker="o")
        ax.set(xlabel="Year", ylabel="Students enrolled (count)",
               title="Enrollment grew by about 130 students")
        p = fig
        """,
        after="""
        from matplotlib.ticker import MaxNLocator
        fig, ax = plt.subplots()
        ax.plot(enrollment.year, enrollment.students, marker="o")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set(xlabel="Year", ylabel="Students enrolled (count)",
               title="Enrollment grew by about 130 students")
        p = fig
        """,
        note="Matplotlib picks ticks like 2019.5 for a handful of years; there is no half-year in the data.",
    ),
    Example(
        "LY103",
        """
        scores = pd.DataFrame({"week": range(1, 9), "score": [61, 64, 63, 68, 71, 70, 74, 77]})
        """,
        before="""
        fig, ax = plt.subplots()
        ax.plot(scores.week, scores.score, color=OKABE[4], marker="o")
        ax.set_xlabel("Week", color="#bbbbbb")
        ax.set_ylabel("Average quiz score (points)", color="#bbbbbb")
        ax.tick_params(colors="#bbbbbb")
        ax.set_title("Quiz scores rose most weeks", color="#bbbbbb")
        p = fig
        """,
        after="""
        fig, ax = plt.subplots()
        ax.plot(scores.week, scores.score, color=OKABE[4], marker="o")
        ax.set_xlabel("Week")
        ax.set_ylabel("Average quiz score (points)")
        ax.set_title("Quiz scores rose most weeks")
        p = fig
        """,
        note="Light gray text on white is about 1.9:1; WCAG asks 4.5:1 for normal text.",
    ),
    Example(
        "CL204",
        """
        sales = pd.DataFrame({"month": range(1, 13),
                              "online": [12, 14, 15, 17, 18, 21, 23, 22, 25, 27, 30, 33],
                              "store": [30, 29, 29, 28, 27, 27, 26, 25, 25, 24, 23, 22]})
        """,
        before="""
        fig, ax = plt.subplots()
        ax.plot(sales.month, sales.online, color="#F0E442", linewidth=2)
        ax.plot(sales.month, sales.store, color=OKABE[4], linewidth=2)
        ax.text(12.2, 33, "Online", va="center")
        ax.text(12.2, 22, "In store", va="center")
        ax.set(xlabel="Month", ylabel="Sales (thousands USD)", xlim=(1, 14),
               title="Online sales passed in-store sales in August")
        p = fig
        """,
        after="""
        fig, ax = plt.subplots()
        ax.plot(sales.month, sales.online, color=OKABE[5], linewidth=2)
        ax.plot(sales.month, sales.store, color=OKABE[4], linewidth=2)
        ax.text(12.2, 33, "Online", va="center")
        ax.text(12.2, 22, "In store", va="center")
        ax.set(xlabel="Month", ylabel="Sales (thousands USD)", xlim=(1, 14),
               title="Online sales passed in-store sales in August")
        p = fig
        """,
        note="Okabe-Ito yellow is only 1.3:1 against white; the vermillion is 3.9:1.",
    ),
    Example(
        "CL301",
        """
        t = np.arange(0, 10)
        growth = pd.DataFrame({"day": np.tile(t, 2),
                               "height": np.r_[2 + 1.1 * t, 2 + 0.6 * t],
                               "light": np.repeat(["Full sun", "Shade"], len(t))})
        """,
        before="""
        p = (ggplot(growth, aes("day", "height", color="light"))
             + geom_line(size=1)
             + scale_color_manual(values=[OKABE[0], OKABE[1]])
             + scale_x_continuous(breaks=range(0, 10, 3))
             + labs(x="Day", y="Seedling height (cm)", color="Light",
                    title="Seedlings in full sun grew almost twice as fast"))
        """,
        after="""
        last = growth[growth["day"] == 9]
        p = (ggplot(growth, aes("day", "height", color="light", linetype="light"))
             + geom_line(size=1)
             + geom_text(aes(label="light"), data=last, ha="left", nudge_x=0.2, color="#222222")
             + scale_color_manual(values=[OKABE[0], OKABE[1]])
             + scale_x_continuous(breaks=range(0, 10, 3), limits=(0, 11.5))
             + theme(legend_position="none")
             + labs(x="Day", y="Seedling height (cm)",
                    title="Seedlings in full sun grew almost twice as fast"))
        """,
        note="Okabe-Ito orange and sky blue are CVD-safe but print as the same gray; a linetype keeps them apart.",
    ),
    Example(
        "CL201",
        """
        n = 25
        hours = rng.uniform(1, 12, 3 * n)
        study = pd.DataFrame({
            "format": np.repeat(["Lecture", "Flipped", "Hybrid"], n),
            "hours": hours,
            "score": np.clip(55 + 3 * hours + np.repeat([0, 6, 3], n) + rng.normal(0, 5, 3 * n), 0, 100),
        })
        """,
        before="""
        p = (ggplot(study, aes("hours", "score", color="format"))
             + geom_point(size=2)
             + labs(x="Study time (hours per week)", y="Exam score (points)",
                    color="Course format", title="More study time, higher scores"))
        """,
        after="""
        p = (ggplot(study, aes("hours", "score", color="format"))
             + geom_point(size=2)
             + scale_color_manual(values=OKABE[:3])
             + labs(x="Study time (hours per week)", y="Exam score (points)",
                    color="Course format", title="More study time, higher scores"))
        """,
        note="plotnine's default hues for three groups are hard to tell apart under deuteranopia; "
        "the Okabe-Ito palette was designed to stay distinct.",
    ),
    Example(
        "CL202",
        """
        cities = ["Phoenix", "Denver", "Chicago", "Boston", "Seattle"]
        temps = pd.DataFrame([(c, y) for c in cities for y in range(2017, 2025)], columns=["city", "year"])
        temps["change"] = np.round(rng.normal(0.6, 0.7, len(temps)), 1)
        """,
        before="""
        p = (ggplot(temps, aes("year", "city", fill="change"))
             + geom_tile()
             + labs(x="Year", y="City", fill="Change vs.\\n1990s (°C)",
                    title="Most years ran warmer than the 1990s"))
        """,
        after="""
        p = (ggplot(temps, aes("year", "city", fill="change"))
             + geom_tile()
             + scale_fill_gradient2(low="#2166AC", mid="#F7F7F7", high="#B2182B",
                                    midpoint=0, limits=(-2, 2))
             + labs(x="Year", y="City", fill="Change vs.\\n1990s (°C)",
                    title="Most years ran warmer than the 1990s"))
        """,
        note="On the sequential scale, a cooler-than-usual year (negative change) is just 'darker blue'; "
        "centered at zero, warm and cool years are red and blue.",
    ),
    Example(
        "CL203",
        """
        income = pd.DataFrame({
            "region": ["West", "East", "South", "North", "Central"],
            "income": [52, 61, 47, 58, 50],
        })
        income["region"] = pd.Categorical(income["region"],
                                          categories=income.sort_values("income")["region"])
        """,
        before="""
        p = (ggplot(income, aes("region", "income", fill="region"))
             + geom_col(show_legend=False)
             + coord_flip()
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most"))
        """,
        after="""
        p = (ggplot(income, aes("region", "income", fill="region == 'East'"))
             + geom_col(show_legend=False)
             + coord_flip()
             + scale_fill_manual(values=["#BBBBBB", OKABE[5]])
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most"))
        """,
        note="Five colors that mean nothing make readers look for a meaning. Spend color on the one bar the title is about.",
    ),
    Example(
        "LB201",
        """
        n = 40
        study_hrs = rng.uniform(1, 12, n)
        grades = pd.DataFrame({"study_hrs": study_hrs,
                               "exam_pct": np.clip(55 + 3 * study_hrs + rng.normal(0, 6, n), 0, 100)})
        """,
        before="""
        p = (ggplot(grades, aes("study_hrs", "exam_pct"))
             + geom_point()
             + labs(title="More study time, higher scores"))
        """,
        after="""
        p = (ggplot(grades, aes("study_hrs", "exam_pct"))
             + geom_point()
             + labs(x="Study time (hours per week)", y="Exam score (%)",
                    title="More study time, higher scores"))
        """,
    ),
    Example(
        "LB301",
        INCOME,
        before="""
        p = (ggplot(income, aes("reorder(region, income)", "income"))
             + geom_col()
             + coord_flip()
             + labs(x="Region", y="Average income",
                    title="East earns the most, South the least"))
        """,
        after="""
        p = (ggplot(income, aes("reorder(region, income)", "income"))
             + geom_col()
             + coord_flip()
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most, South the least"))
        """,
        note="Is 61 dollars, thousands of dollars, or an index? This rule is a heuristic, so it is reported as info.",
    ),
    Example(
        "LB203",
        join(
            INCOME,
            """
        income["region"] = pd.Categorical(income["region"],
                                          categories=income.sort_values("income")["region"])
        """,
        ),
        before="""
        p = (ggplot(income, aes("region", "income", fill="region"))
             + geom_col()
             + coord_flip()
             + labs(x="Region", y="Average income (USD, thousands)", fill="Region",
                    title="East earns the most, South the least"))
        """,
        after="""
        p = (ggplot(income, aes("region", "income"))
             + geom_col()
             + coord_flip()
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most, South the least"))
        """,
        note="Five colors that repeat the axis labels send the reader to a legend for nothing.",
    ),
    Example(
        "LB205",
        """
        exams = pd.DataFrame({
            "year": range(2016, 2025),
            "rate": [0.62, 0.64, 0.63, 0.68, 0.71, 0.70, 0.74, 0.78, 0.81],
        })
        """,
        before="""
        p = (ggplot(exams, aes("year", "rate"))
             + geom_line()
             + geom_point()
             + labs(x="Year", y="Pass rate (%)",
                    title="Pass rates climbed after the redesign"))
        """,
        after="""
        p = (ggplot(exams, aes("year", "rate * 100"))
             + geom_line()
             + geom_point()
             + labs(x="Year", y="Pass rate (%)",
                    title="Pass rates climbed after the redesign"))
        """,
        note="The label promises percent but the ticks say 0.65 to 0.80; was the pass rate under 1%?",
    ),
    Example(
        "LB206",
        """
        years = np.arange(2016, 2025)
        revenue = np.array([118, 131, 150, 162, 140, 185, 230, 268, 310]) * 1_000_000
        """,
        before="""
        fig, ax = plt.subplots()
        ax.plot(years, revenue, marker="o", color=OKABE[4])
        ax.set_xlabel("Year")
        ax.set_ylabel("Revenue (USD)")
        ax.set_title("Revenue more than doubled since 2016")
        p = fig
        """,
        after="""
        fig, ax = plt.subplots()
        ax.plot(years, revenue / 1e6, marker="o", color=OKABE[4])
        ax.set_xlabel("Year")
        ax.set_ylabel("Revenue (USD, millions)")
        ax.set_title("Revenue more than doubled since 2016")
        p = fig
        """,
        note="The '1e8' at the top of the axis is easy to miss, and without it a reader sees revenue of 3 dollars.",
    ),
    Example(
        "LY201",
        INCOME,
        before="""
        p = (ggplot(income, aes("reorder(region, income)", "income"))
             + geom_col()
             + coord_flip()
             + theme_gray(base_size=6)
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most, South the least"))
        """,
        after="""
        p = (ggplot(income, aes("reorder(region, income)", "income"))
             + geom_col()
             + coord_flip()
             + theme_gray(base_size=11)
             + labs(x="Region", y="Average income (USD, thousands)",
                    title="East earns the most, South the least"))
        """,
    ),
    Example(
        "LY202",
        """
        langs = pd.DataFrame({
            "year": np.tile(np.arange(2016, 2025), 5),
            "language": np.repeat(["C++", "Java", "JavaScript", "Python", "R"], 9),
            "share": [12, 11, 11, 10, 10, 9, 9, 8, 8,
                      26, 25, 23, 21, 19, 18, 16, 15, 14,
                      20, 21, 21, 22, 22, 21, 21, 20, 20,
                      10, 13, 16, 19, 22, 25, 27, 29, 31,
                      5, 5, 6, 6, 6, 6, 5, 5, 5],
        })
        """,
        before="""
        p = (ggplot(langs, aes("year", "share", color="language"))
             + geom_line(size=1)
             + scale_color_manual(values=[OKABE[i] for i in (0, 1, 2, 4, 5)])
             + labs(x="Year", y="Share of job ads (%)", color="Language",
                    title="Python overtook Java in 2020"))
        """,
        after="""
        by_last = ["Python", "JavaScript", "Java", "C++", "R"]
        langs["language"] = pd.Categorical(langs["language"], categories=by_last)
        p = (ggplot(langs, aes("year", "share", color="language"))
             + geom_line(size=1)
             + scale_color_manual(values=[OKABE[i] for i in (0, 1, 2, 4, 5)])
             + labs(x="Year", y="Share of job ads (%)", color="Language",
                    title="Python overtook Java in 2020"))
        """,
        note="Ordering the categories by each line's final value makes the legend read top to bottom like the lines.",
    ),
    Example(
        "MK201",
        """
        budget = pd.Series({"Rent": 1600, "Food": 650, "Transport": 300, "Utilities": 180,
                            "Health": 220, "Fun": 250, "Savings": 400})
        """,
        before="""
        fig, ax = plt.subplots()
        ax.pie(budget, labels=budget.index)
        ax.set_title("Where a monthly budget goes")
        p = fig
        """,
        after="""
        s = budget.sort_values()
        fig, ax = plt.subplots()
        ax.barh(s.index, s.values, color=OKABE[4])
        ax.set_xlabel("Monthly spending (USD)")
        ax.set_title("Rent costs more than food, transport and fun combined")
        p = fig
        """,
        note="Is Transport bigger than Fun? The pie can't say; the sorted bars can.",
    ),
    Example(
        "MK202",
        """
        states = ["CA", "TX", "NV", "AZ", "NC", "FL", "NY", "MA", "CO", "UT"]
        solar = pd.DataFrame({
            "year": np.tile(np.arange(2015, 2025), 10),
            "state": np.repeat(states, 10),
            "share": np.concatenate([np.linspace(a, b, 10) + rng.normal(0, 0.4, 10)
                                     for a, b in zip([8, 1, 5, 4, 2, 1, 1, 2, 2, 2],
                                                     [28, 7, 26, 16, 9, 7, 5, 9, 9, 10])]).round(1),
        })
        """,
        before="""
        p = (ggplot(solar, aes("year", "share", color="state"))
             + geom_line()
             + labs(x="Year", y="Solar share of electricity (%)", color="State",
                    title="Solar grew everywhere, fastest in CA and NV"))
        """,
        after="""
        p = (ggplot(solar, aes("year", "share"))
             + geom_line(color=OKABE[4])
             + facet_wrap("state", ncol=5)
             + scale_x_continuous(breaks=[2016, 2023], labels=["'16", "'23"])
             + labs(x="Year", y="Solar share of electricity (%)",
                    title="Solar grew everywhere, fastest in CA and NV"))
        """,
        note="Ten colors can't be matched to a legend. Small multiples on a shared scale give each state its own panel.",
    ),
    Example(
        "MK203",
        """
        n = 15
        conditions = ["Rested", "Sleep-deprived", "Sleep-deprived + caffeine"]
        rt = pd.DataFrame({
            "condition": pd.Categorical(np.repeat(conditions, n), categories=conditions, ordered=True),
            "ms": np.concatenate([rng.normal(m, s, n) for m, s in ((310, 25), (380, 60), (360, 45))]),
        })
        """,
        before="""
        p = (ggplot(rt, aes("condition", "ms"))
             + stat_summary(geom="bar", fun_y=np.mean)
             + coord_flip()
             + labs(x="Condition", y="Mean reaction time (ms)",
                    title="Sleep loss slows reactions"))
        """,
        after="""
        p = (ggplot(rt, aes("condition", "ms"))
             + geom_jitter(width=0.15, height=0, alpha=0.5)
             + stat_summary(fun_data="mean_cl_normal", color=OKABE[5])
             + coord_flip()
             + labs(x="Condition", y="Reaction time (ms)",
                    title="Sleep loss slows reactions",
                    caption="Points: participants. Orange: mean and 95% CI."))
        """,
        note="The bars hide that the sleep-deprived group is far more variable; "
        "the points and confidence intervals show it.",
    ),
    Example(
        "MK204",
        """
        sessions = pd.DataFrame({
            "device": ["Desktop"] * 40 + ["Phone"] * 40 + ["Tablet"] * 6,
            "minutes": np.concatenate([rng.gamma(5, 4, 40), rng.gamma(3, 3, 40), rng.gamma(4, 4, 6)]),
        })
        """,
        before="""
        p = (ggplot(sessions, aes("device", "minutes"))
             + geom_boxplot()
             + labs(x="Device", y="Session length (minutes)",
                    title="Desktop sessions run longest"))
        """,
        after="""
        p = (ggplot(sessions, aes("device", "minutes"))
             + geom_boxplot(outlier_shape="")
             + geom_jitter(width=0.15, height=0, alpha=0.5)
             + labs(x="Device", y="Session length (minutes)",
                    title="Desktop sessions run longest",
                    caption="Only 6 tablet sessions were recorded."))
        """,
        note="The tablet box looks as solid as the others but summarizes six sessions.",
    ),
    Example(
        "MK205",
        """
        modes = ["Car", "Bus", "Rail", "Bike", "Walk", "Scooter", "Other"]
        commute = pd.DataFrame({
            "city": np.repeat(["Austin", "Chicago", "Portland"], 7),
            "mode": modes * 3,
            "share": [72, 4, 1, 2, 3, 1, 17,  48, 13, 15, 2, 7, 1, 14,  58, 9, 3, 6, 6, 1, 17],
        })
        """,
        before="""
        p = (ggplot(commute, aes("city", "share", fill="mode"))
             + geom_col()
             + labs(x="City", y="Share of commuters (%)", fill="Mode",
                    title="Chicago relies least on cars"))
        """,
        after="""
        p = (ggplot(commute, aes("reorder(mode, share)", "share"))
             + geom_col()
             + coord_flip()
             + facet_wrap("city")
             + labs(x="Mode", y="Share of commuters (%)",
                    title="Chicago relies least on cars"))
        """,
        note="In the stack, only Car shares a baseline; compare Rail across cities and you are comparing floating segments.",
    ),
    # ------------------------------------------------------------------ tier 3
    Example(
        "ST301",
        """
        n = 40
        temp = rng.uniform(2, 32, n)
        bikes = pd.DataFrame({"temp": temp, "rentals": (800 + 120 * temp + rng.normal(0, 400, n)).round()})
        """,
        before="""
        p = (ggplot(bikes, aes("temp", "rentals"))
             + geom_point()
             + labs(x="Temperature (°C)", y="Daily bike rentals (count)"))
        """,
        after="""
        p = (ggplot(bikes, aes("temp", "rentals"))
             + geom_point()
             + labs(x="Temperature (°C)", y="Daily bike rentals (count)",
                    title="Rentals climb as days warm up"))
        """,
    ),
    Example(
        "ST303",
        """
        homes = pd.DataFrame({
            "year": np.tile(np.arange(2015, 2025), 3),
            "city": pd.Categorical(np.repeat(["San Diego", "Denver", "Phoenix"], 10),
                                   categories=["San Diego", "Denver", "Phoenix"]),
            "price": [480, 510, 545, 570, 600, 650, 760, 850, 880, 930,
                      380, 410, 440, 460, 480, 510, 600, 650, 620, 610,
                      210, 230, 250, 270, 290, 320, 410, 460, 430, 440],
        })
        """,
        before="""
        p = (ggplot(homes, aes("year", "price", color="city"))
             + geom_line(size=1)
             + scale_color_manual(values=OKABE[:3])
             + labs(x="Year", y="Median home price (USD, thousands)", color="City",
                    title="San Diego prices pulled away after 2020"))
        """,
        after="""
        last = homes[homes["year"] == 2024]
        p = (ggplot(homes, aes("year", "price", color="city"))
             + geom_line(size=1)
             + geom_text(aes(label="city"), data=last, ha="left", nudge_x=0.2, size=10,
                         color="#222222")  # dark text: colored labels can fail text contrast
             + scale_color_manual(values=OKABE[:3])
             + scale_x_continuous(limits=(2015, 2026.5), breaks=range(2015, 2025, 3))
             + theme(legend_position="none")
             + labs(x="Year", y="Median home price (USD, thousands)",
                    title="San Diego prices pulled away after 2020"))
        """,
    ),
    Example(
        "ST305",
        """
        n = 15
        stores = pd.DataFrame({
            "region": np.repeat(["East", "North", "South", "West"], n),
            "ads": rng.uniform(5, 40, 4 * n),
        })
        stores["revenue"] = (60 + 4 * stores["ads"] + rng.normal(0, 20, 4 * n)).round()
        south_west = stores[stores["region"].isin(["South", "West"])]

        def scatter(df, title):
            return (ggplot(df, aes("ads", "revenue", color="region")) + geom_point()
                    + labs(x="Ad spend (USD, k)", y="Revenue (USD, k)", color="Region", title=title))
        """,
        before="""
        PAL = [OKABE[i] for i in (0, 1, 2, 4)]
        figs = [scatter(stores, "Ads pay off in every region") + scale_color_manual(values=PAL),
                scatter(south_west, "South and West stores") + scale_color_manual(values=PAL)]
        """,
        after="""
        PAL = dict(zip(["East", "North", "South", "West"], [OKABE[i] for i in (0, 1, 2, 4)]))
        figs = [scatter(stores, "Ads pay off in every region") + scale_color_manual(values=PAL),
                scatter(south_west, "South and West stores") + scale_color_manual(values=PAL)]
        """,
        note="Two figures from one notebook, linted with a shared `Session` "
        "(`lint(fig, session=session)`; the Jupyter hook does this for you). "
        "A list of colors is handed out in order, so when the second figure keeps only South and West, "
        "South turns orange and West sky blue. A dict ties each region to one color in every figure.",
    ),
    Example(
        "ST306",
        join(
            INCOME,
            """
        trend = pd.DataFrame({"year": range(2015, 2025),
                              "income": [44, 45, 47, 48, 50, 49, 51, 53, 55, 56]})
        """,
        ),
        before="""
        figs = [ggplot(income, aes("reorder(region, income)", "income")) + geom_col() + coord_flip()
                + theme_minimal()
                + labs(x="Region", y="Income (USD, k)", title="East earns the most"),
                ggplot(trend, aes("year", "income")) + geom_line()
                + scale_x_continuous(breaks=range(2015, 2025, 3))
                + labs(x="Year", y="Income (USD, k)", title="Incomes rose 27% since 2015")]
        """,
        after="""
        theme_set(theme_minimal())
        figs = [ggplot(income, aes("reorder(region, income)", "income")) + geom_col() + coord_flip()
                + labs(x="Region", y="Income (USD, k)", title="East earns the most"),
                ggplot(trend, aes("year", "income")) + geom_line()
                + scale_x_continuous(breaks=range(2015, 2025, 3))
                + labs(x="Year", y="Income (USD, k)", title="Incomes rose 27% since 2015")]
        """,
        note="Two figures from one notebook, linted with a shared `Session`. The first got `theme_minimal()`, "
        "the second was left on the default gray theme, so the pair looks unfinished. "
        "`theme_set()` once at the top of the notebook styles every figure the same way.",
    ),
    Example(
        "ST307",
        """
        jobs = pd.DataFrame({
            "year": range(2015, 2025),
            "rate": [0.046, 0.043, 0.041, 0.038, 0.035, 0.037, 0.039, 0.036, 0.034, 0.033],
        })
        """,
        before="""
        p = (ggplot(jobs, aes("year", "rate"))
             + geom_line()
             + scale_x_continuous(breaks=range(2015, 2025, 3))
             + labs(x="Year", y="Unemployment rate (share of workers)",
                    title="Unemployment drifted down"))
        """,
        after="""
        p = (ggplot(jobs, aes("year", "rate"))
             + geom_line()
             + scale_x_continuous(breaks=range(2015, 2025, 3))
             + scale_y_continuous(labels=label_percent())
             + labs(x="Year", y="Unemployment rate (%)",
                    title="Unemployment drifted down"))
        """,
        note="`0.035, 0.040, 0.045` makes the reader do arithmetic; `3.5%, 4.0%, 4.5%` says the same with fewer digits.",
    ),
]


# --------------------------------------------------------------------------- running
@dataclass
class Result:
    example: Example
    before_reports: list
    after_reports: list


class GalleryError(AssertionError):
    pass


def _run(snippet: str, data: str):
    ns: dict = {}
    # The gallery runs its own snippets, so exec is the point here.
    exec(PRELUDE, ns)  # noqa: S102
    exec(data, ns)  # noqa: S102
    exec(snippet, ns)  # noqa: S102
    if "figs" in ns:
        return list(ns["figs"])
    return [ns["p"]]


def _lint_all(objs, multi: bool, rule_id: str):
    session = Session() if multi else None
    return [
        lint(o, select=[*SELECT, rule_id], config=Config(), session=session)
        for o in objs
    ]


def _save(obj, path: Path, size) -> None:
    if isinstance(obj, ggplot):
        obj.save(path, width=size[0], height=size[1], dpi=DPI, verbose=False)
    else:
        obj.savefig(
            path, dpi=DPI, bbox_inches="tight", pad_inches=0.08, facecolor="white"
        )
        plt.close(obj)


def _save_side_by_side(objs, path: Path, size) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        imgs = []
        for i, o in enumerate(objs):
            f = Path(tmp) / f"{i}.png"
            _save(o, f, size)
            im = plt.imread(f)[..., :3]
            imgs.append(im)
    h = max(im.shape[0] for im in imgs)
    gap = np.ones((h, 16, 3))
    padded = [
        np.vstack([im, np.ones((h - im.shape[0], im.shape[1], 3))]) for im in imgs
    ]
    row = [padded[0]]
    for im in padded[1:]:
        row += [gap, im]
    plt.imsave(path, np.hstack(row))


def _configure(size) -> None:
    import plotnine.options

    plotnine.options.figure_size = size
    plotnine.options.dpi = DPI
    plt.rcParams.update(
        {
            "figure.figsize": size,
            "figure.dpi": DPI,
            "figure.constrained_layout.use": True,
        }
    )


def run_example(ex: Example) -> Result:
    size = SMALL if ex.multi else SIZE
    _configure(size)
    out = {}
    for which, snippet in (("before", ex.before), ("after", ex.after)):
        theme_set(theme_gray())
        plt.close("all")
        try:
            objs = _run(snippet, ex.data)
            reports = _lint_all(objs, ex.multi, ex.rule)
        except Exception as e:
            raise GalleryError(
                f"{ex.rule} {which}: snippet failed: {type(e).__name__}: {e}"
            ) from e
        for r in reports:
            if r.internal_errors:
                raise GalleryError(
                    f"{ex.rule} {which}: linter internal errors: {r.internal_errors}"
                )
        path = IMG / f"{ex.rule}_{which}.png"
        if ex.multi:
            _save_side_by_side(objs, path, size)
        else:
            _save(objs[0], path, size)
        out[which] = reports
    theme_set(theme_gray())

    target = out["before"][-1]
    if ex.rule not in target.ids:
        raise GalleryError(
            f"{ex.rule}: BEFORE was not flagged with {ex.rule}; got {target.ids}"
        )
    flagged_after = [r for r in out["after"] if ex.rule in r.ids]
    if flagged_after:
        msgs = [str(f) for r in flagged_after for f in r if f.rule_id == ex.rule]
        raise GalleryError(
            f"{ex.rule}: AFTER is still flagged:\n  " + "\n  ".join(msgs)
        )
    return Result(ex, out["before"], out["after"])


# --------------------------------------------------------------------------- markdown
def _first_sentence(text: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text.strip())
    return m.group(1) if m else text.strip()


def _diff(before: str, after: str) -> str:
    a, b = before.rstrip("\n").splitlines(), after.rstrip("\n").splitlines()
    lines = []
    for line in difflib.ndiff(a, b):
        tag = line[:2]
        if tag == "? ":
            continue
        lines.append({"- ": "-", "+ ": "+", "  ": " "}[tag] + " " + line[2:])
    return "\n".join(lines)


def _md_inline(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown(results: list[Result], catalog: dict) -> str:
    tiers = catalog["tiers"]
    shown = {res.example.rule for res in results}
    out = [
        "# Before / after gallery",
        "",
        (
            "One broken chart and one fixed chart for every rule in the catalog. Each *before* plot is "
            "flagged by `plotnine_linter.lint()` for its rule; each *after* plot follows the rule's fix and "
            "lints clean with the default rules (tiers 1 and 2) plus the example's own rule selected."
        ),
        "",
        (
            "Generated by [`docs/gallery/make_gallery.py`](gallery/make_gallery.py), which runs every snippet "
            "below and fails if a before plot isn't flagged or an after plot is. Don't edit this file by hand: "
            "change the script and rerun `python docs/gallery/make_gallery.py`."
        ),
        "",
        "Every snippet starts from:",
        "",
        "```python",
        PRELUDE.rstrip(),
        "```",
        "",
        (
            f"Figures are {SIZE[0]:g} x {SIZE[1]:g} in (`plotnine.options.figure_size`, or `figure.figsize` "
            "with constrained layout for matplotlib)."
        ),
        "",
    ]
    # table of contents
    for tier_key, tier in tiers.items():
        ids = [
            r["id"]
            for r in catalog["rules"]
            if str(r["tier"]) == tier_key and r["id"] in shown
        ]
        links = " · ".join(f"[{i}](#{i.lower()})" for i in ids)
        out.append(
            f"- **Tier {tier_key}, {tier['name']}** ({tier['severity']}): {links}"
        )
    out.append("")

    res_by_id = {res.example.rule: res for res in results}
    for tier_key, tier in tiers.items():
        default = "on by default" if tier["default"] else "opt-in"
        out += [
            f"## Tier {tier_key}: {tier['name']} ({tier['severity']}, {default})",
            "",
        ]
        for rule in catalog["rules"]:
            if str(rule["tier"]) != tier_key or rule["id"] not in res_by_id:
                continue
            res = res_by_id[rule["id"]]
            ex = res.example
            rid = rule["id"]
            out += [
                f'<a id="{rid.lower()}"></a>',
                "",
                f"### {rid} — {rule['title']}",
                "",
            ]
            out += [_first_sentence(rule["why"]), ""]
            label_b = "Before (two figures in one notebook)" if ex.multi else "Before"
            label_a = "After (two figures in one notebook)" if ex.multi else "After"
            out += [
                f"| {label_b} | {label_a} |",
                "| --- | --- |",
                f"| ![{rid} before](gallery/img/{rid}_before.png) | ![{rid} after](gallery/img/{rid}_after.png) |",
                "",
            ]
            if ex.note:
                out += [ex.note, ""]
            target = [f for f in res.before_reports[-1] if f.rule_id == rid]
            out += ["**What the linter says about the before plot:**", "", "```text"]
            for f in target:
                out.append(str(f))
            out += ["```", ""]
            others = sorted(
                {f.rule_id for r in res.before_reports for f in r if f.rule_id != rid}
            )
            if others:
                links = ", ".join(
                    f"[{o}](#{o.lower()})" if o in shown else o for o in others
                )
                out += [f"The before plot also trips {links}.", ""]
            leftover = sorted({f.rule_id for r in res.after_reports for f in r})
            if leftover:
                out += [f"*Note: the after plot still gets {', '.join(leftover)}.*", ""]
            out += [
                "**The fix:**",
                "",
                "```diff",
                _diff(ex.before, ex.after),
                "```",
                "",
                "<details><summary>Data for this example</summary>",
                "",
                "```python",
                ex.data.rstrip(),
                "```",
                "",
                "</details>",
                "",
            ]
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--strict", action="store_true", help="fail if any AFTER plot has any finding"
    )
    ap.add_argument(
        "--only",
        nargs="*",
        help="run only these rule IDs (GALLERY.md is not rewritten)",
    )
    args = ap.parse_args(argv)

    warnings.filterwarnings("ignore")
    IMG.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    catalog_ids = [r["id"] for r in catalog["rules"]]
    example_ids = [e.rule for e in EXAMPLES]

    missing = [i for i in catalog_ids if i not in example_ids]
    extra = [i for i in example_ids if i not in catalog_ids]
    dupes = sorted({i for i in example_ids if example_ids.count(i) > 1})
    if (missing or extra or dupes) and not args.only:
        raise GalleryError(
            f"catalog/example mismatch: missing={missing} unknown={extra} duplicated={dupes}"
        )

    todo = [
        e for e in EXAMPLES if not args.only or e.rule in {s.upper() for s in args.only}
    ]
    results, failures = [], []
    for ex in todo:
        try:
            res = run_example(ex)
        except GalleryError as e:
            failures.append(str(e))
            print(f"FAIL {e}", file=sys.stderr)
            continue
        results.append(res)
        leftover = [f"{f.rule_id}: {f.message}" for r in res.after_reports for f in r]
        status = (
            "ok"
            if not leftover
            else "ok (after not clean: " + "; ".join(leftover) + ")"
        )
        print(f"{ex.rule:6} before={','.join(res.before_reports[-1].ids)}  {status}")

    if failures:
        print(f"\n{len(failures)} example(s) failed:", file=sys.stderr)
        for f in failures:
            print(" -", f.splitlines()[0], file=sys.stderr)
        return 1

    unclean = {
        r.example.rule: sorted({f.rule_id for rep in r.after_reports for f in rep})
        for r in results
    }
    unclean = {k: v for k, v in unclean.items() if v}
    if not args.only:
        GALLERY_MD.write_text(render_markdown(results, catalog), encoding="utf-8")
        print(f"\nwrote {GALLERY_MD} and {len(results) * 2} images in {IMG}")
    if unclean:
        print(f"AFTER plots with findings: {unclean}", file=sys.stderr)
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

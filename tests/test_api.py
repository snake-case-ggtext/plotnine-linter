"""Configuration, suppression, severities, reports, CLI."""

import json
import subprocess
import sys

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from plotnine_linter import Config, all_rules, lint, load_config
from plotnine_linter.findings import Severity
from plotnine_linter.suppress import parse_suppressions
from plotnine_linter.testing import assert_clean

from .conftest import ids


def unsorted_bars():
    fig, ax = plt.subplots()
    ax.bar(["dog", "cat", "fish", "bird"], [5, 9, 2, 7])
    ax.set_ylabel("Pets (count)")
    return fig


def test_rule_ids_are_well_formed_and_unique():
    rules = all_rules()
    assert len({r.id for r in rules}) == len(rules)
    for r in rules:
        assert r.id[:2] in {"AX", "CL", "LB", "LY", "MK", "ST"}
        assert int(r.id[2]) == r.tier
        assert r.why and r.fix and r.title


def test_tier3_is_opt_in():
    fig = unsorted_bars()
    assert "ST301" not in ids(lint(fig))
    assert "ST301" in ids(lint(fig, select=["tier1", "tier2", "tier3"]))
    assert "ST301" in ids(lint(fig, select=["ST"]))


def test_ignore_and_select():
    fig = unsorted_bars()
    assert "AX201" not in ids(lint(fig, ignore=["AX201"]))
    assert ids(lint(fig, select=["AX"])) <= {
        "AX101",
        "AX102",
        "AX103",
        "AX201",
        "AX202",
        "AX203",
        "AX204",
    }


def test_severity_override():
    report = lint(unsorted_bars(), severity={"AX201": "error"})
    assert [f.severity for f in report if f.rule_id == "AX201"] == [Severity.ERROR]


def test_threshold_override():
    fig, ax = plt.subplots()
    ax.pie([1, 2, 3])
    assert "MK201" not in ids(lint(fig))
    assert "MK201" in ids(lint(fig, thresholds={"max_pie_slices": 2}))


def test_parse_suppressions():
    src = "x = 1\n# plotlint: ignore[AX201, lb301] months are ordinal\n#plotlint:ignore[MK101]\n"
    assert parse_suppressions(src) == {
        "AX201": "months are ordinal",
        "LB301": "months are ordinal",
        "MK101": "",
    }


def test_suppression_with_reason_moves_finding():
    report = lint(
        unsorted_bars(), source="# plotlint: ignore[AX201] order is by survey question"
    )
    assert "AX201" not in ids(report)
    assert [(f.rule_id, why) for f, why in report.suppressed] == [
        ("AX201", "order is by survey question")
    ]


def test_suppression_without_reason_is_noted():
    report = lint(unsorted_bars(), suppress=["AX201"])
    assert "AX201" not in ids(report)
    assert "SUP001" in ids(report)


def test_pyproject_config(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.plotnine-linter]\nselect = ["tier1", "tier2", "ST301"]\nignore = ["AX201"]\n'
        'severity = { LB301 = "warning" }\n[tool.plotnine-linter.thresholds]\nmax_pie_slices = 2\n'
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.is_selected("ST301", 3) and not cfg.is_selected("ST303", 3)
    assert not cfg.is_selected("AX201", 2)
    assert cfg.severity["LB301"] == Severity.WARNING
    assert cfg.t("max_pie_slices") == 2
    assert "AX201" not in ids(lint(unsorted_bars()))


def test_report_outputs():
    report = lint(unsorted_bars())
    data = json.loads(report.to_json())
    assert data["source"] == "matplotlib"
    assert {f["rule_id"] for f in data["findings"]} == set(report.ids)
    html = report._repr_html_()
    assert "AX201" in html and "<code>" in html
    assert "AX201" in str(report)


def test_assert_clean():
    with pytest.raises(AssertionError, match="AX101"):
        fig, ax = plt.subplots()
        ax.bar(["a", "b"], [5, 6])
        ax.set_ylim(4, 7)
        assert_clean(fig)
    assert_clean(unsorted_bars())  # only a warning


def test_rejects_unknown_objects():
    with pytest.raises(TypeError):
        lint("not a plot")


def test_broken_rule_does_not_crash(monkeypatch):
    from plotnine_linter import registry

    def boom(desc, cfg):
        raise RuntimeError("bug")
        yield  # pragma: no cover

    rule = registry.RULES["MK201"]
    monkeypatch.setattr(rule, "check", boom)
    report = lint(unsorted_bars())
    assert any("MK201" in e for e in report.internal_errors)


def test_cli_rules_and_check(tmp_path):
    out = subprocess.run(
        [sys.executable, "-m", "plotnine_linter", "rules"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "AX101" in out.stdout
    script = tmp_path / "plot.py"
    script.write_text(
        "import matplotlib.pyplot as plt\n"
        "fig, ax = plt.subplots()\n"
        "ax.bar(['a', 'b'], [5, 6]); ax.set_ylim(4, 7)\n"
        "plt.show()\n"
    )
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "plotnine_linter",
            "check",
            str(script),
            "--format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert "AX101" in {f["rule_id"] for f in data[0]["findings"]}


def test_config_merged_skips_none():
    cfg = Config().merged(select=None, ignore="AX203")
    assert cfg.select == ("tier1", "tier2") and cfg.ignore == ("AX203",)


def test_rule_catalog():
    from plotnine_linter import show_rules

    cat = show_rules()
    assert len(cat) == len(all_rules())
    html = cat._repr_html_()
    assert "Tier 1" in html and "AX101" in html and "ST301" in html
    frame = cat.to_frame()
    assert frame.loc["AX101", "enabled"] and not frame.loc["ST301", "enabled"]
    assert frame.loc["CL201", "tier"] == 2
    assert {r.id[:2] for r in show_rules("AX").rules} == {"AX"}
    assert {r.tier for r in show_rules(1).rules} == {1}
    on = show_rules(
        config=Config().merged(select=["tier1", "tier2", "tier3"])
    ).to_frame()
    assert on["enabled"].all()
    assert "AX101" in str(cat)


def test_session_rules_compare_figures():
    from plotnine_linter.session import Session

    session = Session()
    opts = {"select": ["ST305", "ST306"], "session": session}
    fig1, ax1 = plt.subplots()
    ax1.plot([0, 1], [0, 1], color="#E69F00", label="West")
    ax1.legend()
    assert lint(fig1, **opts).ids == []
    fig2, ax2 = plt.subplots()
    ax2.plot([0, 1], [1, 0], color="#0072B2", label="West")
    ax2.legend()
    ax2.tick_params(labelsize=16)
    report = lint(fig2, **opts)
    assert "ST305" in report.ids and "ST306" in report.ids
    assert len(session.charts) == 2


def test_alt_text():
    from plotnine_linter import alt_text

    fig, ax = plt.subplots()
    s = pd.Series({"West": 52, "East": 61, "South": 47})
    ax.bar(s.index, s.values)
    ax.set_xlabel("Region")
    ax.set_ylabel("Income (USD k)")
    text = alt_text(fig)
    assert (
        text.startswith("Bar chart of Income (USD k) by Region")
        and "Highest: East (61)" in text
    )
    assert lint(fig).alt_text == text


def test_accessibility_profile():
    from plotnine_linter import show_rules

    cfg = Config().merged(profile="accessibility")
    assert cfg.t("min_mark_contrast") == 3.0 and cfg.t("min_font_pt") == 9.0
    assert cfg.is_selected("ST301", 3) and not cfg.is_selected("ST303", 3)
    assert cfg.severity["CL301"] == Severity.WARNING and cfg.is_selected("CL301", 3)
    fig, ax = plt.subplots()
    ax.plot(
        [1, 2, 3], [1, 3, 2], color="#ff7f0e"
    )  # matplotlib's default orange: 2.5:1 on white
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Distance (m)")
    assert "CL204" not in ids(lint(fig))
    assert "CL204" in ids(lint(fig, profile="accessibility"))
    a11y = show_rules("a11y")
    assert {"LY103", "CL204", "ST301"} <= {r.id for r in a11y.rules}
    assert "Chartability" in a11y._repr_html_()
    with pytest.raises(ValueError):
        Config().merged(profile="nope")

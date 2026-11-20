"""Helpers for autograders and test suites.

from plotnine_linter.testing import assert_clean
assert_clean(student_plot)                    # fail on any error-level finding
assert_clean(student_plot, at_least="warning")
"""

from __future__ import annotations

from typing import Any

from .api import lint
from .findings import Report


def assert_clean(obj: Any, at_least: str = "error", **lint_kwargs) -> Report:
    """Raise AssertionError if ``obj`` has findings at or above ``at_least``."""
    report = lint(obj, **lint_kwargs)
    bad = report.at_least(at_least)
    if bad:
        details = "\n".join(str(f) for f in bad)
        raise AssertionError(f"plotnine-linter found {len(bad)} issue(s):\n{details}")
    return report

"""plotnine-linter: a teaching-first linter for plotnine and matplotlib charts.

``lint()`` checks a plotnine ``ggplot`` or a matplotlib ``Figure`` or ``Axes``.
In Jupyter, ``%load_ext plotnine_linter`` lints every plot as it appears.
``show_rules()`` lists the rule catalog. ``audit()`` runs a Chartability
accessibility audit.

    from plotnine_linter import lint
    lint(p)
"""

from .alttext import alt_text
from .api import lint
from .audit import audit, data_table
from .catalog import show_rules
from .config import Config, load_config
from .describe import describe
from .findings import Finding, Report, Severity
from .jupyter import load_ipython_extension, unload_ipython_extension
from .registry import RULES, all_rules

__version__ = "0.1.0"

__all__ = [
    "RULES",
    "Config",
    "Finding",
    "Report",
    "Severity",
    "all_rules",
    "alt_text",
    "audit",
    "data_table",
    "describe",
    "lint",
    "load_config",
    "load_ipython_extension",
    "show_rules",
    "unload_ipython_extension",
]

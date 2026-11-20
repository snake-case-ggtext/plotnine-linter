"""The public entry point: ``lint()``."""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from .config import Config, load_config
from .describe import ChartDescription, describe
from .findings import Finding, Report, Severity
from .registry import all_rules
from .suppress import parse_suppressions

if TYPE_CHECKING:
    from .session import Session


def lint(
    obj: Any,
    *,
    select: Iterable[str] | str | None = None,
    ignore: Iterable[str] | str | None = None,
    severity: Mapping[str, str] | None = None,
    thresholds: Mapping[str, float] | None = None,
    suppress: Mapping[str, str] | Iterable[str] | None = None,
    source: str | None = None,
    config: Config | None = None,
    session: Session | None = None,
    profile: str | None = None,
) -> Report:
    """Lint a plotnine plot or a matplotlib Figure/Axes and return a :class:`Report`.

    Parameters
    ----------
    obj
        A plotnine ``ggplot``, or a matplotlib ``Figure`` or ``Axes``.
    select, ignore
        Tiers (``"tier1"``), area prefixes (``"AX"``) or rule IDs to run / skip.
        By default tiers 1 and 2 run, plus whatever pyproject.toml selects.
    severity
        Per-rule severity overrides, e.g. ``{"LB202": "warning"}``.
    thresholds
        Overrides for numeric thresholds (see ``config.DEFAULT_THRESHOLDS``).
    suppress
        Rule IDs to suppress, optionally with a reason: ``{"AX201": "months are ordinal"}``.
    source
        Code that made the plot; ``# plotlint: ignore[ID] reason`` comments in it are honored.
    config
        A :class:`Config`; defaults to the nearest pyproject.toml.
    profile
        A preset from the catalog, e.g. ``"accessibility"`` (rules tied to Chartability and
        WCAG, at their published thresholds). Explicit arguments override it.
    session
        A :class:`~plotnine_linter.session.Session` shared across figures, for rules that
        compare figures (ST305, ST306). The Jupyter hook passes one automatically.
    """
    cfg = (config or load_config()).merged(
        profile=profile,
        select=select,
        ignore=ignore,
        severity=severity,
        thresholds=thresholds,
    )
    desc = describe(obj)
    desc.session = session
    try:
        report = lint_description(desc, cfg, suppress=suppress, source=source)
        if session is not None:
            from .session import chart_facts

            session.add(chart_facts(desc))
        return report
    finally:
        if desc.source == "plotnine":
            _close(desc.render.figure)


def lint_description(
    desc: ChartDescription,
    cfg: Config,
    *,
    suppress: Mapping[str, str] | Iterable[str] | None = None,
    source: str | None = None,
) -> Report:
    suppressions = parse_suppressions(source)
    if suppress:
        if isinstance(suppress, Mapping):
            suppressions.update({k.upper(): str(v) for k, v in suppress.items()})
        else:
            suppressions.update({str(k).upper(): "" for k in suppress})

    report = Report(source=desc.source)
    if desc.spec is None:
        data_panels = [p for p in desc.render.panels if p.has_data]
        if not data_panels:
            report.empty = True
            return report
        desc.render.panels = data_panels
    seen = set()
    for rule in all_rules():
        if not cfg.is_selected(rule.id, rule.tier):
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                hits = list(rule.check(desc, cfg) or [])
        except Exception as exc:  # noqa: BLE001  # a broken rule must never break the user's plot
            desc.errors.append(f"{rule.id}: {type(exc).__name__}: {exc}")
            continue
        for hit in hits:
            key = (rule.id, hit.message, hit.panel)
            if key in seen:
                continue
            seen.add(key)
            sev = cfg.severity.get(rule.id)
            if sev is None:
                sev = (
                    Severity.INFO
                    if (hit.heuristic or rule.heuristic)
                    else rule.default_severity
                )
            finding = Finding(
                rule_id=rule.id,
                title=rule.title,
                severity=sev,
                message=hit.message,
                fix=hit.fix if hit.fix is not None else rule.fix,
                why=rule.why,
                source=hit.source,
                heuristic=hit.heuristic or rule.heuristic,
                panel=hit.panel if len(desc.render.panels) > 1 else None,
                details=hit.details,
            )
            if rule.id in suppressions:
                report.suppressed.append((finding, suppressions[rule.id]))
            else:
                report.findings.append(finding)

    for rule_id in sorted({f.rule_id for f, reason in report.suppressed if not reason}):
        report.findings.append(
            Finding(
                rule_id="SUP001",
                title="Suppression without a reason",
                severity=Severity.INFO,
                message=f"{rule_id} is suppressed without a reason.",
                fix=f"Say why next to the plot: `# plotlint: ignore[{rule_id}] <reason>`.",
                why="A one-line reason tells a reader (and a grader) the rule was broken on purpose.",
            )
        )

    report.findings.sort(key=lambda f: (-int(f.severity), f.rule_id))
    report.internal_errors = list(desc.errors)
    from .alttext import describe_alt_text

    report.alt_text = describe_alt_text(desc)
    return report


def _close(fig) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)

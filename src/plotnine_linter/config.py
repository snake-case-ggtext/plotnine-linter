"""Configuration: which rules run, at what severity, with which thresholds.

Settings are read from the nearest ``pyproject.toml`` (searching upward from
the working directory) under ``[tool.plotnine-linter]``::

    [tool.plotnine-linter]
    select = ["tier1", "tier2", "ST301"]   # tiers, area prefixes or rule IDs
    ignore = ["AX203"]
    severity = { LB202 = "warning" }

    [tool.plotnine-linter.thresholds]
    max_pie_slices = 4

An instructor can ship this file with course materials so every student
sees the same rules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from .findings import Severity

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None


def _default_thresholds() -> dict[str, float]:
    from .registry import load_catalog

    return {
        name: spec["default"] for name, spec in load_catalog()["thresholds"].items()
    }


# documented, with the rule each one affects, in data/rules.json
DEFAULT_THRESHOLDS: dict[str, float] = _default_thresholds()


@dataclass(frozen=True)
class Config:
    select: tuple[str, ...] = ("tier1", "tier2")
    ignore: tuple[str, ...] = ()
    severity: dict[str, Severity] = field(default_factory=dict)
    thresholds: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_THRESHOLDS)
    )
    profile: str | None = None

    def is_selected(self, rule_id: str, tier: int) -> bool:
        def matches(selector: str) -> bool:
            s = selector.strip().upper()
            if s in {"ALL", "*"}:
                return True
            if s.startswith("TIER"):
                return s == f"TIER{tier}"
            if s in {"A11Y", "ACCESSIBILITY"}:
                from .registry import RULES

                rule = RULES.get(rule_id)
                return bool(rule and (rule.chartability or rule.wcag))
            return rule_id.upper().startswith(s)

        if any(matches(s) for s in self.ignore):
            return False
        return any(matches(s) for s in self.select)

    def t(self, name: str) -> float:
        return self.thresholds.get(name, DEFAULT_THRESHOLDS[name])

    def merged(self, **overrides) -> Config:
        """Return a copy with keyword overrides applied (None values are skipped).

        ``profile`` (e.g. "accessibility") is applied first; explicit select, severity
        and thresholds then override it. ``profile="none"`` clears a profile.
        """
        profile = overrides.pop("profile", None)
        base = self.with_profile(profile) if profile else self
        kwargs = {}
        for key, value in overrides.items():
            if value is None:
                continue
            if key in {"select", "ignore"}:
                value = tuple([value] if isinstance(value, str) else value)
            elif key == "severity":
                value = {
                    **base.severity,
                    **{k: Severity.parse(v) for k, v in value.items()},
                }
            elif key == "thresholds":
                value = {**base.thresholds, **value}
            kwargs[key] = value
        return replace(base, **kwargs)

    def with_profile(self, name: str) -> Config:
        """Apply a preset from the catalog's "profiles" (e.g. "accessibility"); "none" resets."""
        if str(name).lower() in ("none", "default", ""):
            return Config(severity=dict(self.severity))
        spec = profiles().get(str(name).lower())
        if spec is None:
            raise ValueError(
                f"unknown profile {name!r}; available: {', '.join(profiles())}"
            )
        return replace(
            self,
            select=tuple(spec.get("select", self.select)),
            severity={
                **self.severity,
                **{k: Severity.parse(v) for k, v in spec.get("severity", {}).items()},
            },
            thresholds={**self.thresholds, **spec.get("thresholds", {})},
            profile=str(name).lower(),
        )


def profiles() -> dict:
    from .registry import load_catalog

    return load_catalog().get("profiles", {})


def _find_pyproject(start: Path) -> Path | None:
    for directory in [start, *start.parents]:
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def load_config(path: str | os.PathLike | None = None) -> Config:
    """Load settings from ``path`` or the nearest pyproject.toml; defaults if none."""
    if tomllib is None:
        return Config()
    pyproject = Path(path) if path else _find_pyproject(Path.cwd())
    if pyproject is None or not pyproject.is_file():
        return Config()
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return Config()
    section = data.get("tool", {}).get("plotnine-linter")
    if not section:
        return Config()
    return Config().merged(
        profile=section.get("profile"),
        select=section.get("select"),
        ignore=section.get("ignore"),
        severity=section.get("severity"),
        thresholds=section.get("thresholds"),
    )

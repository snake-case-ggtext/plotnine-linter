"""Rule registry.

A rule's metadata (title, tier, why, fix, heuristic) lives in the shared
catalog ``data/rules.json``, so other implementations (e.g. an R port for
ggplot2) can use the same IDs and wording. The Python check is a function
that receives a :class:`ChartDescription` and a :class:`Config`, and yields
``Hit`` objects; the registry turns hits into findings.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .findings import Severity

TIER_SEVERITY = {1: Severity.ERROR, 2: Severity.WARNING, 3: Severity.INFO}


@dataclass
class Hit:
    """What a rule check yields: a message plus optional specifics."""

    message: str
    fix: str | None = None  # overrides the rule's default fix
    source: str = "spec"  # "spec" or "render"
    heuristic: bool = False
    panel: int | None = None
    details: dict = field(default_factory=dict)


@dataclass
class Rule:
    id: str
    title: str
    tier: int
    why: str
    fix: str
    check: Callable[..., Iterable[Hit]]
    heuristic: bool = False
    chartability: list[str] = field(
        default_factory=list
    )  # Chartability tests this rule checks
    wcag: list[str] = field(default_factory=list)  # WCAG success criteria

    @property
    def default_severity(self) -> Severity:
        return Severity.INFO if self.heuristic else TIER_SEVERITY[self.tier]


RULES: dict[str, Rule] = {}

_CATALOG_PATH = Path(__file__).parent / "data" / "rules.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    """The shared rule catalog (data/rules.json): IDs, titles, tiers, why/fix text, thresholds."""
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def _catalog_entry(rule_id: str) -> dict:
    for entry in load_catalog()["rules"]:
        if entry["id"] == rule_id:
            return entry
    raise KeyError(f"rule {rule_id} has a check but no entry in {_CATALOG_PATH.name}")


def rule(id: str):
    """Register a check for a rule. Its title, tier, why and fix come from the catalog."""
    entry = _catalog_entry(id)
    tier = int(id[2])
    if tier != entry["tier"] or tier not in TIER_SEVERITY:
        raise ValueError(
            f"rule {id}: the third character must match its catalog tier ({entry['tier']})"
        )

    def decorator(fn):
        if id in RULES:
            raise ValueError(f"duplicate rule id {id}")
        RULES[id] = Rule(
            id=id,
            title=entry["title"],
            tier=tier,
            why=entry["why"],
            fix=entry["fix"],
            check=fn,
            heuristic=bool(entry.get("heuristic", False)),
            chartability=list(entry.get("chartability", [])),
            wcag=list(entry.get("wcag", [])),
        )
        return fn

    return decorator


def all_rules() -> list[Rule]:
    from . import rules  # noqa: F401  (import registers rules)

    return sorted(RULES.values(), key=lambda r: (r.tier, r.id))

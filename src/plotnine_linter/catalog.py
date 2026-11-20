"""A readable rule catalog for notebooks.

``show_rules()`` shows every rule, grouped by tier, and marks the rules that
are on. Pass a tier (``1``), an area (``"AX"``) or ``"a11y"`` to show fewer.
``.to_frame()`` gives a pandas DataFrame. In Jupyter, ``%plotlint rules`` does
the same.

    from plotnine_linter import show_rules
    show_rules("AX")
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from .config import Config, load_config
from .findings import _BADGE, _md_code
from .registry import Rule, all_rules

TIER_NAMES = {1: "Tier 1 — Errors", 2: "Tier 2 — Clarity", 3: "Tier 3 — Style (opt-in)"}
AREAS = {
    "AX": "Axes and scales",
    "CL": "Color",
    "LB": "Labels",
    "LY": "Layout",
    "MK": "Marks",
    "ST": "Style",
}


@dataclass
class RuleCatalog:
    rules: list[Rule]
    config: Config

    def _severity(self, r: Rule):
        return self.config.severity.get(r.id, r.default_severity)

    def _enabled(self, r: Rule) -> bool:
        return self.config.is_selected(r.id, r.tier)

    def to_frame(self):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "id": r.id,
                    "tier": r.tier,
                    "area": AREAS.get(r.id[:2], r.id[:2]),
                    "title": r.title,
                    "severity": str(self._severity(r)),
                    "enabled": self._enabled(r),
                    "heuristic": r.heuristic,
                    "chartability": "; ".join(r.chartability),
                    "wcag": "; ".join(r.wcag),
                    "why": r.why,
                    "fix": r.fix,
                }
                for r in self.rules
            ]
        ).set_index("id")

    def __len__(self) -> int:
        return len(self.rules)

    def __str__(self) -> str:
        lines = []
        for tier in sorted({r.tier for r in self.rules}):
            lines.append(TIER_NAMES[tier])
            for r in (r for r in self.rules if r.tier == tier):
                state = "on " if self._enabled(r) else "off"
                lines.append(f"  {r.id}  [{state}] {self._severity(r)!s:<7}  {r.title}")
        return "\n".join(lines)

    __repr__ = __str__

    def _repr_html_(self) -> str:
        from ._html import FONT, MUTED, SEVERITY, pill

        parts = [f'<div style="{FONT};max-width:900px">']
        n_on = sum(self._enabled(r) for r in self.rules)
        parts.append(
            f"<div style='{MUTED};margin-bottom:6px'>{len(self.rules)} rules · {n_on} on with the "
            "current settings · click a rule for why and how to fix</div>"
        )
        for tier in sorted({r.tier for r in self.rules}):
            parts.append(
                f"<div style='font-weight:600;font-size:14px;margin:12px 0 4px'>{TIER_NAMES[tier]}</div>"
            )
            for r in (r for r in self.rules if r.tier == tier):
                kind = _BADGE[self._severity(r)]
                on = self._enabled(r)
                solid, tint = SEVERITY[kind if on else "off"]
                state = pill("on", "ok") if on else pill("off", "off")
                note = (
                    f" <span style='{MUTED}'>(heuristic)</span>" if r.heuristic else ""
                )
                parts.append(
                    f"<details style='border-left:3px solid {solid};padding:3px 10px;margin:2px 0;background:{tint}'>"
                    f"<summary style='cursor:pointer'><code style='font-weight:600'>{r.id}</code> "
                    f"{html.escape(r.title)}{note} {pill(kind, kind)} {state}</summary>"
                    f"<div style='margin:4px 0 2px'><b>Why:</b> {_md_code(r.why)}</div>"
                    f"<div style='margin:2px 0 4px'><b>Fix:</b> {_md_code(r.fix)}</div>"
                    + (
                        f"<div style='margin:0 0 4px;{MUTED};font-size:12px'>"
                        + " &middot; ".join(
                            x
                            for x in (
                                (
                                    "Chartability: "
                                    + html.escape("; ".join(r.chartability))
                                )
                                if r.chartability
                                else "",
                                ("WCAG " + html.escape("; ".join(r.wcag)))
                                if r.wcag
                                else "",
                            )
                            if x
                        )
                        + "</div>"
                        if (r.chartability or r.wcag)
                        else ""
                    )
                    + "</details>"
                )
        parts.append("</div>")
        return "".join(parts)


def show_rules(
    select: str | int | None = None, *, config: Config | None = None
) -> RuleCatalog:
    """The rule catalog, showing which rules are on under the current settings.

    ``select`` shows fewer rules. Give a tier number (``1``), an area prefix (``"AX"``)
    or a rule ID. ``"a11y"`` shows the rules tied to Chartability tests or WCAG criteria.
    """
    cfg = config or _current_config()
    chosen = all_rules()
    if isinstance(select, int):
        chosen = [r for r in chosen if r.tier == select]
    elif select:
        s = str(select).upper()
        if s.startswith("TIER"):
            chosen = [r for r in chosen if f"TIER{r.tier}" == s]
        elif s in ("A11Y", "ACCESSIBILITY", "CHARTABILITY", "WCAG"):
            chosen = [r for r in chosen if r.chartability or r.wcag]
        else:
            chosen = [r for r in chosen if r.id.startswith(s)]
    return RuleCatalog(rules=chosen, config=cfg)


def _current_config() -> Config:
    """pyproject.toml settings plus anything set with %plotlint in this notebook."""
    from .jupyter import _STATE

    cfg = load_config()
    if _STATE.get("loaded") and _STATE["options"]:
        cfg = cfg.merged(**_STATE["options"])
    return cfg

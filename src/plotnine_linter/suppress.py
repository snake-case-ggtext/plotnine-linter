"""Inline suppressions.

A suppression without a reason still works, but the report notes it. That way
the reason for breaking a rule stays next to the plot. To break a rule,
write its ID and a reason:

    # plotlint: ignore[AX201] months are ordinal
"""

from __future__ import annotations

import re

_PATTERN = re.compile(
    r"#\s*(?:plotlint|plotnine-linter)\s*:\s*ignore\[(?P<ids>[A-Za-z0-9_,\s]+)\]\s*(?P<reason>[^\n]*)",
    re.IGNORECASE,
)


def parse_suppressions(source: str | None) -> dict[str, str]:
    """Map rule ID -> reason ("" when none given) from comments in ``source``."""
    found: dict[str, str] = {}
    if not source:
        return found
    for m in _PATTERN.finditer(source):
        reason = m.group("reason").strip()
        for rule_id in m.group("ids").split(","):
            rule_id = rule_id.strip().upper()
            if rule_id:
                found[rule_id] = reason
    return found

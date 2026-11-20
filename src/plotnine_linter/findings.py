"""Findings and reports: what the linter returns."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .audit import Audit


class Severity(IntEnum):
    INFO = 1
    WARNING = 2
    ERROR = 3

    @classmethod
    def parse(cls, value: str | Severity) -> Severity:
        if isinstance(value, Severity):
            return value
        return cls[str(value).upper()]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name.lower()


@dataclass
class Finding:
    """One rule violation on one chart."""

    rule_id: str
    title: str
    severity: Severity
    message: str
    fix: str = ""
    why: str = ""
    source: str = ""  # "spec" or "render"
    heuristic: bool = False
    panel: int | None = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = str(self.severity)
        return d

    def __str__(self) -> str:
        where = f" (panel {self.panel + 1})" if self.panel is not None else ""
        text = f"{self.rule_id} {self.severity!s}{where}: {self.message}"
        if self.fix:
            text += f"\n    fix: {self.fix}"
        return text


_BADGE = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "info",
}


@dataclass
class Report:
    """All findings for one chart, plus the suppressed ones."""

    findings: list[Finding] = field(default_factory=list)
    suppressed: list[tuple[Finding, str]] = field(default_factory=list)
    source: str = ""
    internal_errors: list[str] = field(
        default_factory=list
    )  # rules that crashed (a linter bug)
    image: str | None = None  # path to a saved PNG of the plot, when requested
    alt_text: str = ""  # a draft alt text for the plot (see alttext.py)
    empty: bool = False  # the figure had no plotted data, so no rule ran
    # set by `plotnine-linter audit` and `check_notebook(audit=True)`
    audit: Audit | None = field(default=None, repr=False, compare=False)

    # ----- convenience -------------------------------------------------
    def __iter__(self):
        return iter(self.findings)

    def __len__(self) -> int:
        return len(self.findings)

    def __bool__(self) -> bool:
        return bool(self.findings)

    @property
    def ids(self) -> list[str]:
        return [f.rule_id for f in self.findings]

    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    def at_least(self, severity: str | Severity) -> list[Finding]:
        sev = Severity.parse(severity)
        return [f for f in self.findings if f.severity >= sev]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "findings": [f.to_dict() for f in self.findings],
            "suppressed": [
                {"rule_id": f.rule_id, "reason": reason}
                for f, reason in self.suppressed
            ],
            "internal_errors": list(self.internal_errors),
            "image": self.image,
            "alt_text": self.alt_text,
            "empty": self.empty,
        }

    def to_json(self, **kwargs) -> str:
        return json.dumps(self.to_dict(), **kwargs)

    # ----- display -----------------------------------------------------
    def __str__(self) -> str:
        if not self.findings:
            return "plotnine-linter: no issues found."
        lines = [f"plotnine-linter: {len(self.findings)} issue(s)"]
        lines += [str(f) for f in self.findings]
        if self.suppressed:
            lines.append(f"({len(self.suppressed)} suppressed)")
        return "\n".join(lines)

    __repr__ = __str__

    def _repr_html_(self) -> str:
        from ._html import FONT, MUTED, SEVERITY, pill

        if not self.findings and not self.internal_errors:
            return f'<div style="{FONT}">{pill("ok", "ok")} plotnine-linter: no issues found.</div>'
        rows = []
        for f in self.findings:
            kind = _BADGE[f.severity]
            solid, tint = SEVERITY[kind]
            where = f" &middot; panel {f.panel + 1}" if f.panel is not None else ""
            fix = (
                f"<div style='margin-top:2px'><b>Fix:</b> {_md_code(f.fix)}</div>"
                if f.fix
                else ""
            )
            why = (
                f"<details style='margin-top:2px'><summary style='cursor:pointer;{MUTED}'>Why it matters</summary>"
                f"<div style='{MUTED}'>{html.escape(f.why)}</div></details>"
                if f.why
                else ""
            )
            rows.append(
                f"<div style='border-left:3px solid {solid};background:{tint};padding:6px 10px;margin:4px 0'>"
                f"{pill(kind, kind)} <code style='font-weight:600'>{f.rule_id}</code>"
                f"<span style='{MUTED}'>{where}</span> {_md_code(f.message)}{fix}{why}</div>"
            )
        for err in self.internal_errors:
            rows.append(
                f"<div style='{MUTED};font-size:12px'>linter error (not your plot): {html.escape(err)}</div>"
            )
        sup = (
            f"<div style='{MUTED};font-size:12px'>{len(self.suppressed)} suppressed</div>"
            if self.suppressed
            else ""
        )
        return f'<div style="{FONT};max-width:760px">' + "".join(rows) + sup + "</div>"


def _md_code(text: str) -> str:
    """Escape text and turn `backticks` into <code>."""
    parts = html.escape(text).split("`")
    out = []
    for i, part in enumerate(parts):
        out.append(f"<code>{part}</code>" if i % 2 else part)
    return "".join(out)

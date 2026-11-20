"""Shared HTML styling for notebook output.

The output reads well in light and dark notebook themes. Text takes the
theme's color, and backgrounds are translucent tints. Each severity shows as
a solid pill with white text and its name, so color is never the only cue.
"""

from __future__ import annotations

SEVERITY = {
    # name: (solid color for pills and borders, translucent tint for backgrounds)
    "error": ("#b42318", "rgba(180, 35, 24, 0.10)"),
    "warning": ("#b54708", "rgba(181, 71, 8, 0.10)"),
    "info": ("#175cd3", "rgba(23, 92, 211, 0.10)"),
    "ok": ("#067647", "rgba(6, 118, 71, 0.10)"),
    "off": ("#667085", "rgba(102, 112, 133, 0.08)"),
}

FONT = "font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:13px;color:inherit"
MUTED = "opacity:0.72"
RULE_LINE = "border-bottom:1px solid rgba(127, 127, 127, 0.25)"


def pill(text: str, kind: str) -> str:
    solid = SEVERITY[kind][0]
    return (
        f"<span style='background:{solid};color:#ffffff;border-radius:3px;padding:0 5px;"
        f"font-size:11.5px;font-weight:600'>{text}</span>"
    )

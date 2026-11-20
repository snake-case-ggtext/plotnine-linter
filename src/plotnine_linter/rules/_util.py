"""Small helpers shared by rules."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TypeGuard

import numpy as np
import pandas as pd

_CALL = re.compile(
    r"^[a-z_][\w.]*\([^$%()]*\)$"
)  # factor(cyl), np.log(x): lowercase function names
_IDENT = re.compile(r"^%?[A-Za-z_][\w.]*\??$")  # also %employed, Death_Penalty?
_ARITH = re.compile(r"^[a-z_][\w.]*[-+*/][a-z_][\w.]*$")  # a/b, but not Race/Ethnicity
_CAMEL = re.compile(r"[a-z][A-Z]")


def looks_like_code(label: str | None) -> TypeGuard[str]:
    """True for labels that read as code: snake_case, camelCase, dotted names, calls."""
    if not label:
        return False
    s = str(label).strip()
    if _CALL.match(s):
        return True
    if " " in s:
        return False
    if _ARITH.match(s):
        return True
    if _IDENT.match(s):
        return "_" in s or "." in s or s.startswith("%") or bool(_CAMEL.search(s))
    return False


_UNIT_WORDS = {
    "usd": "USD",
    "eur": "EUR",
    "gbp": "GBP",
    "dollars": "dollars",
    "pct": "%",
    "percent": "%",
    "cm": "cm",
    "mm": "mm",
    "m": "m",
    "km": "km",
    "mi": "miles",
    "ft": "ft",
    "in": "in",
    "kg": "kg",
    "g": "g",
    "mg": "mg",
    "lb": "lb",
    "lbs": "lb",
    "s": "s",
    "sec": "s",
    "secs": "s",
    "ms": "ms",
    "min": "min",
    "mins": "min",
    "hr": "hours",
    "hrs": "hours",
    "hours": "hours",
    "days": "days",
    "yrs": "years",
    "years": "years",
    "c": "°C",
    "f": "°F",
    "mph": "mph",
    "kph": "km/h",
    "kwh": "kWh",
    "bpm": "bpm",
}


def humanize(label: str, add_units: bool = False) -> str:
    """'avg_income_usd' -> 'Avg income (USD)'; 'factor(cyl)' -> 'Cyl'.

    With ``add_units``, a label without a recognizable unit suffix gets a
    '(units)' placeholder for the student to fill in.
    """
    s = str(label).strip()
    m = re.match(r"^[A-Za-z_][\w.]*\((.*)\)$", s)
    if m:
        s = m.group(1).split(",")[0].strip()
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    words = re.sub(r"[_.]+", " ", s).strip().lower().split()
    unit = None
    if len(words) > 1 and words[-1] in _UNIT_WORDS:
        unit = _UNIT_WORDS[words.pop()]
    text = " ".join(words)
    text = text[:1].upper() + text[1:] if text else str(label)
    if unit:
        return f"{text} ({unit})"
    return f"{text} (units)" if add_units else text


_MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_ORDINAL_VOCABS = [
    set(_MONTHS) | {m[:3] for m in _MONTHS} | {"sept"},
    set(_DAYS) | {d[:3] for d in _DAYS} | {"tues", "thur", "thurs"},
    {"q1", "q2", "q3", "q4"},
    {
        "strongly disagree",
        "disagree",
        "somewhat disagree",
        "neutral",
        "neither agree nor disagree",
        "somewhat agree",
        "agree",
        "strongly agree",
    },
    {"very low", "low", "medium", "moderate", "high", "very high"},
    {"never", "rarely", "sometimes", "often", "always"},
    {"xs", "s", "m", "l", "xl", "xxl", "small", "medium", "large", "extra large"},
    {
        "freshman",
        "sophomore",
        "junior",
        "senior",
        "first year",
        "second year",
        "third year",
        "fourth year",
    },
    {"poor", "fair", "good", "very good", "excellent"},
    {"none", "mild", "moderate", "severe"},
]
_NUMERIC_LIKE = re.compile(
    r"^[<>≤≥~]?\s*[-+]?\$?\d[\d,.]*\s*(%|k|m)?\s*(([-–]|to)\s*\$?\d[\d,.]*\s*(%|k|m)?|\+)?$",
    re.IGNORECASE,
)


def ordinal_like(labels: Iterable) -> bool:
    """True when category labels look like an ordered scale (months, Likert, bins...)."""
    labs = [str(x).strip().lower() for x in labels if str(x).strip()]
    if not labs:
        return False
    if all(_NUMERIC_LIKE.match(x) for x in labs):
        return True
    return any(all(x in vocab for x in labs) for vocab in _ORDINAL_VOCABS)


def base_var(expr: str | None) -> str | None:
    """'reorder(region, income)' -> 'region'; 'factor(cyl)' -> 'cyl'; other strings unchanged."""
    if not isinstance(expr, str):
        return expr
    m = re.match(
        r"^\s*(?:reorder|factor|pd\.Categorical|str)\s*\(\s*([A-Za-z_][\w.]*)", expr
    )
    return m.group(1) if m else expr.strip()


def is_unordered_column(col: pd.Series | None) -> TypeGuard[pd.Series]:
    """A nominal column: strings/objects, or an unordered Categorical in default (sorted) order."""
    if col is None:
        return False
    dtype = col.dtype
    if isinstance(dtype, pd.CategoricalDtype):
        if dtype.ordered:
            return False
        cats = [str(c) for c in dtype.categories]
        return cats == sorted(cats)  # the user did not choose an order
    if pd.api.types.is_bool_dtype(dtype) or pd.api.types.is_numeric_dtype(dtype):
        return False
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return False
    return pd.api.types.is_object_dtype(dtype) or pd.api.types.is_string_dtype(dtype)


def is_discrete_column(col: pd.Series | None) -> bool:
    if col is None:
        return False
    dtype = col.dtype
    return (
        isinstance(dtype, pd.CategoricalDtype)
        or pd.api.types.is_bool_dtype(dtype)
        or pd.api.types.is_object_dtype(dtype)
        or pd.api.types.is_string_dtype(dtype)
    )


def monotone(values) -> bool:
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return True
    d = np.diff(v)
    return bool(np.all(d >= -1e-12) or np.all(d <= 1e-12))


def overlaps(a, b, tol: float = 1.0, along: str | None = None) -> bool:
    """Do two display-space Bboxes overlap by more than ``tol`` pixels each way?

    With ``along`` ("x" or "y") and a negative ``tol``, boxes closer than ``-tol``
    pixels along that direction also count (labels running into each other).
    """
    w = min(a.x1, b.x1) - max(a.x0, b.x0)
    h = min(a.y1, b.y1) - max(a.y0, b.y0)
    if along == "x":
        return w > tol and h > 1.0
    if along == "y":
        return h > tol and w > 1.0
    return w > tol and h > tol


def quote(text: str, n: int = 24) -> str:
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


_ORDERED_VOCABS = [
    _MONTHS,
    [m[:3] for m in _MONTHS],
    _DAYS,
    [d[:3] for d in _DAYS],
    ["q1", "q2", "q3", "q4"],
    [
        "strongly disagree",
        "disagree",
        "somewhat disagree",
        "neutral",
        "neither agree nor disagree",
        "somewhat agree",
        "agree",
        "strongly agree",
    ],
    ["very low", "low", "medium", "moderate", "high", "very high"],
    ["never", "rarely", "sometimes", "often", "always"],
    ["xs", "s", "m", "l", "xl", "xxl"],
    ["small", "medium", "large", "extra large"],
    ["freshman", "sophomore", "junior", "senior"],
    ["first year", "second year", "third year", "fourth year"],
    ["poor", "fair", "good", "very good", "excellent"],
    ["none", "mild", "moderate", "severe"],
]


def natural_order(labels) -> list[str] | None:
    """Labels sorted in their natural order (months, weekdays, Likert...), or None if unknown."""
    labs = [str(x).strip() for x in labels if str(x).strip()]
    if len(labs) < 2:
        return None
    for vocab in _ORDERED_VOCABS:
        lower = [x.lower().rstrip(".") for x in labs]
        if all(x in vocab for x in lower):
            return [
                lab for _, lab in sorted(zip((vocab.index(x) for x in lower), labs))
            ]
    return None

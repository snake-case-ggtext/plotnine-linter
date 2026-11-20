"""Plain-language checks for a chart's own text: reading grade and abbreviations.

These checks read the title, subtitle, caption, axis titles and legend titles.
They skip tick labels and category names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Abbreviations most general readers know, plus common units.
KNOWN_ABBREVIATIONS = {
    "US", "USA", "UK", "EU", "UN", "USD", "EUR", "GBP", "CAD", "AM", "PM", "ID", "OK", "TV",
    "AI", "COVID", "CO2", "GDP", "NYC", "DC", "BC", "AD", "CE", "BCE", "KB", "MB", "GB", "TB",
    "II", "III", "IV", "VI", "Q1", "Q2", "Q3", "Q4", "PhD", "MPH", "KM", "CM", "MM", "HZ", "KG",
}  # fmt: skip

_ABBR = re.compile(r"(?<![\w'])([A-Z][A-Z0-9]{1,5})s?(?![\w'])")
_WORD = re.compile(r"[A-Za-z]+(?:'[a-z]+)?")


def syllables(word: str) -> int:
    """A standard heuristic syllable count (vowel groups, minus a silent final e)."""
    w = word.lower()
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]+", w)))


@dataclass
class Readability:
    words: int = 0
    # Flesch-Kincaid grade, when there is enough text to score
    grade: float | None = None
    long_words: list[str] = field(default_factory=list)  # 4+ syllables
    abbreviations: list[str] = field(default_factory=list)  # undefined ones

    MIN_WORDS = 10

    @property
    def scored(self) -> bool:
        return self.grade is not None


def analyze(texts: list[str]) -> Readability:
    """Score short chart texts; each text counts as one sentence."""
    texts = [" ".join(str(t).split()) for t in texts if t and str(t).strip()]
    result = Readability()
    words = [w for t in texts for w in _WORD.findall(t)]
    result.words = len(words)
    if result.words >= Readability.MIN_WORDS:
        sentences = sum(max(1, len(re.findall(r"[.!?]+(?:\s|$)", t))) for t in texts)
        syl = sum(syllables(w) for w in words)
        grade = 0.39 * (len(words) / sentences) + 11.8 * (syl / len(words)) - 15.59
        result.grade = round(max(grade, 0.0), 1)
    seen = set()
    for w in words:
        if syllables(w) >= 4 and w.lower() not in seen and not w.isupper():
            seen.add(w.lower())
            result.long_words.append(w)
    result.abbreviations = undefined_abbreviations(texts)
    return result


def undefined_abbreviations(texts: list[str]) -> list[str]:
    joined = "  ".join(texts)
    found: list[str] = []
    for t in texts:
        if t.isupper() and len(t.split()) > 2:
            continue  # an all-caps title is shouting, not abbreviating
        for m in _ABBR.finditer(t):
            abbr = m.group(1)
            if abbr in KNOWN_ABBREVIATIONS or abbr in found or abbr.isdigit():
                continue
            if re.search(
                rf"\(\s*{re.escape(abbr)}\s*\)|\b{re.escape(abbr)}\s*[=:]\s*\w", joined
            ):
                continue  # defined on the chart: "reaction time (RT)" or "RT = reaction time"
            found.append(abbr)
    return found

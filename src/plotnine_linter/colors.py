"""Color utilities: color-vision-deficiency simulation and perceptual distance.

CVD simulation uses the Machado, Oliveira & Fernandes (2009) matrices at
severity 1.0, applied in linear RGB. Distance is CIEDE2000 in CIELAB (D65).
No extra dependencies.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
from matplotlib.colors import to_rgb

MACHADO = {
    "protanopia": np.array(
        [
            [0.152286, 1.052583, -0.204868],
            [0.114503, 0.786281, 0.099216],
            [-0.003882, -0.048116, 1.051998],
        ]
    ),
    "deuteranopia": np.array(
        [
            [0.367322, 0.860646, -0.227968],
            [0.280085, 0.672501, 0.047413],
            [-0.011820, 0.042940, 0.968881],
        ]
    ),
    "tritanopia": np.array(
        [
            [1.255528, -0.076749, -0.178779],
            [-0.078411, 0.930809, 0.147602],
            [0.004733, 0.691367, 0.303900],
        ]
    ),
}


def _to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


def simulate(color, kind: str) -> np.ndarray:
    """sRGB (0-1) of ``color`` as seen with the given deficiency, or printed in grayscale."""
    rgb = np.asarray(to_rgb(color), dtype=float)
    if kind == "grayscale":
        y = float(
            np.dot([0.2126, 0.7152, 0.0722], _to_linear(rgb))
        )  # relative luminance
        return _to_srgb(np.array([y, y, y]))
    return _to_srgb(MACHADO[kind] @ _to_linear(rgb))


def relative_luminance(color) -> float:
    """WCAG relative luminance of an sRGB color (0 = black, 1 = white)."""
    return float(
        np.dot(
            [0.2126, 0.7152, 0.0722], _to_linear(np.asarray(to_rgb(color), dtype=float))
        )
    )


def contrast_ratio(a, b) -> float:
    """WCAG contrast ratio between two colors (1 to 21)."""
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def blend(color, background, alpha: float):
    """``color`` drawn at ``alpha`` over ``background`` (both sRGB)."""
    fg, bg = np.asarray(to_rgb(color)), np.asarray(to_rgb(background))
    return tuple(alpha * fg + (1 - alpha) * bg)


def to_lab(color) -> np.ndarray:
    rgb = _to_linear(
        np.asarray(
            to_rgb(color) if not isinstance(color, np.ndarray) else color, dtype=float
        )
    )
    m = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = m @ rgb / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def delta_e2000(lab1: np.ndarray, lab2: np.ndarray) -> float:
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cbar**7 / (Cbar**7 + 25**7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    T = (
        1
        - 0.17 * math.cos(math.radians(hbp - 30))
        + 0.24 * math.cos(math.radians(2 * hbp))
        + 0.32 * math.cos(math.radians(3 * hbp + 6))
        - 0.20 * math.cos(math.radians(4 * hbp - 63))
    )
    dtheta = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp**7 / (Cbp**7 + 25**7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dtheta)) * Rc
    return math.sqrt(
        (dLp / Sl) ** 2
        + (dCp / Sc) ** 2
        + (dHp / Sh) ** 2
        + Rt * (dCp / Sc) * (dHp / Sh)
    )


CVD_KINDS = ("deuteranopia", "protanopia", "tritanopia")


def confusable_pairs(
    colors, min_delta_e: float, kinds=CVD_KINDS
) -> list[tuple[str, str, str, float]]:
    """Pairs that are distinct normally but closer than ``min_delta_e`` under some CVD.

    Returns (color_a, color_b, deficiency, simulated distance), worst first.
    """
    uniq = []
    for c in colors:
        try:
            rgb = tuple(np.round(to_rgb(c), 4))
        except (ValueError, TypeError):
            continue
        if rgb not in uniq:
            uniq.append(rgb)
    out = []
    for a, b in itertools.combinations(uniq, 2):
        normal = delta_e2000(to_lab(np.array(a)), to_lab(np.array(b)))
        if (
            normal < min_delta_e
        ):  # already hard to tell apart; not a CVD problem specifically
            continue
        worst = None
        for kind in kinds:
            d = delta_e2000(to_lab(simulate(a, kind)), to_lab(simulate(b, kind)))
            if d < min_delta_e and (worst is None or d < worst[1]):
                worst = (kind, d)
        if worst:
            out.append((_hex(a), _hex(b), worst[0], round(worst[1], 1)))
    return sorted(out, key=lambda t: t[3])


def _hex(rgb) -> str:
    return "#" + "".join(f"{round(v * 255):02x}" for v in rgb)

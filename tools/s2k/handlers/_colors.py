# tools/s2k/handlers/_colors.py
"""S2K renk string → (R, G, B) 0-1 aralığında.

Desteklenen formatlar:
    - İsimli: "Red", "Cyan", "Gray8Dark", "Gray4", "Gray1Light", ...
    - Windows BGR sayısal: 16711808, 4227200, ...
    - Hex: "#FF0080"
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

DEFAULT_COLOR = (0.8, 0.8, 0.8)

# S2K renk paleti — SAP2000 "OPTIONS - COLORS" tablosundaki isimler
NAMED_COLORS: dict[str, tuple[float, float, float]] = {
    # temel
    "black":       (0.00, 0.00, 0.00),
    "white":       (1.00, 1.00, 1.00),
    "red":         (1.00, 0.00, 0.00),
    "green":       (0.00, 1.00, 0.00),
    "blue":        (0.00, 0.00, 1.00),
    "yellow":      (1.00, 1.00, 0.00),
    "cyan":        (0.00, 1.00, 1.00),
    "magenta":     (1.00, 0.00, 1.00),
    # ara
    "orange":      (1.00, 0.50, 0.00),
    "pink":        (1.00, 0.75, 0.80),
    "purple":      (0.50, 0.00, 0.50),
    "brown":       (0.60, 0.40, 0.20),
    # gri tonları (SAP2000 "GrayN" formatı; N=1 açık, N=8 koyu)
    "gray":        (0.50, 0.50, 0.50),
    "grey":        (0.50, 0.50, 0.50),
    "darkred":     (0.55, 0.00, 0.00),
    "darkgreen":   (0.00, 0.50, 0.00),
    "darkblue":    (0.00, 0.00, 0.55),
    "lightgray":   (0.75, 0.75, 0.75),
    "lightgrey":   (0.75, 0.75, 0.75),
    # SAP2000 "Gray1Light" .. "Gray8Dark"
    "gray1light":  (0.95, 0.95, 0.95),
    "gray2":       (0.85, 0.85, 0.85),
    "gray3":       (0.75, 0.75, 0.75),
    "gray4":       (0.65, 0.65, 0.65),
    "gray5":       (0.55, 0.55, 0.55),
    "gray6":       (0.45, 0.45, 0.45),
    "gray7":       (0.35, 0.35, 0.35),
    "gray8dark":   (0.25, 0.25, 0.25),
}


def color_from_string(s) -> tuple[float, float, float]:
    """S2K Color alanı → (R, G, B). Bilinmeyen → DEFAULT_COLOR."""
    if not s:
        return DEFAULT_COLOR

    text = str(s).strip()
    if not text or text.lower() in ("none", "nan"):
        return DEFAULT_COLOR

    # 1) İsimli renkler (case-insensitive)
    named = NAMED_COLORS.get(text.lower())
    if named is not None:
        return named

    # 2) Windows BGR sayısal (SAP2000: 16711808 → Magenta)
    try:
        value = int(text)
        r = (value & 0xFF) / 255.0
        g = ((value >> 8) & 0xFF) / 255.0
        b = ((value >> 16) & 0xFF) / 255.0
        return (r, g, b)
    except (ValueError, TypeError):
        pass

    # 3) Hex "#FF0080"
    if text.startswith("#") and len(text) == 7:
        try:
            r = int(text[1:3], 16) / 255.0
            g = int(text[3:5], 16) / 255.0
            b = int(text[5:7], 16) / 255.0
            return (r, g, b)
        except ValueError:
            pass

    logger.debug("[Color] Bilinmeyen format: %r → default", text)
    return DEFAULT_COLOR
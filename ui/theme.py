# ui/theme.py
"""
ImGui font + tema.
"""
import os
from typing import Any, Dict, Optional

import imgui
from logging_config import CadLogger
logger = CadLogger.get(__name__)

# Kalıcı referans (pointer silinmesin)
_PERSISTENT_GLYPH_RANGES = None


def _make_glyph_ranges():
    """Türkçe + teknik semboller + UI ikonları için genişletilmiş range."""
    global _PERSISTENT_GLYPH_RANGES
    ranges = [
        0x0020, 0x00FF,  # Latin-1 (Türkçe temel)
        0x0100, 0x017F,  # Latin Extended-A
        0x0180, 0x024F,  # Latin Extended-B
        0x0370, 0x03FF,  # Yunanca (α β γ Δ σ ε)
        0x2000, 0x206F,  # Genel noktalama
        0x2070, 0x209F,  # Üst/alt simgeler (¹²³, ₁₂₃)
        0x20A0, 0x20CF,  # Para birimleri (€ £ ₺)
        0x2100, 0x214F,  # Letterlike (℃ № ℄)
        0x2150, 0x218F,  # Number forms (⅓ ⅔)
        0x2190, 0x21FF,  # Oklar (→ ← ↑ ↓ ↔)
        0x2200, 0x22FF,  # Matematik (≤ ≥ ≠ ≈ ∞ √ ∑ ∫ ∂)
        0x2300, 0x23FF,  # Teknik (⌂ ⌐ ⌘ ⏎)
        0x2500, 0x257F,  # Box drawing (─ │ ┌ ┐ └ ┘)
        0x25A0, 0x25FF,  # Geometrik (▲ ▼ ◀ ▶ ● ○ ◆ ◇ ■ □)
        0x2600, 0x26FF,  # Semboller (⚙ ⚡ ⚠ ☀ ☁)
        0x2700, 0x27BF,  # Dingbats (✓ ✔ ✗ ✘ ✚)
        0x2B00, 0x2BFF,  # Misc arrows
        0,
    ]
    _PERSISTENT_GLYPH_RANGES = imgui.core.GlyphRanges(ranges)
    return _PERSISTENT_GLYPH_RANGES


def load_fonts(font_size: int = 16,
               impl=None) -> Dict[str, Any]:
    """Türkçe + sembolleri destekleyen font yükle."""
    io = imgui.get_io()

    # Font adayları
    win_fonts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    candidates = [
        os.path.join(win_fonts, "segoeui.ttf"),    # ← İyi alternatif
        os.path.join(win_fonts, "tahoma.ttf"),
        os.path.join(win_fonts, "msyh.ttc"),       # ← Testte kullandığın
        os.path.join(win_fonts, "malgun.ttf"),
        "assets/fonts/Roboto-Regular.ttf",         # ← EN SONA koy
    ]

    path = None
    for p in candidates:
        if p and os.path.isfile(p):
            path = os.path.abspath(p)
            break

    if not path:
        io.fonts.add_font_default()
        return {"font": None, "path": None, "size": font_size}

    # Glyph range — global referans
    ranges = _make_glyph_ranges()

    # Font yükle (font_config=None, ranges pozisyonel)
    font_obj = io.fonts.add_font_from_file_ttf(path, font_size, None, ranges)
    w, h = io.fonts.texture_width, io.fonts.texture_height
    logger.warning("[font] atlas boyutu: %dx%d", w, h)
    logger.warning("[font] font yüklendi: %r, impl=%r", font_obj, type(impl).__name__ if impl else None)

    # refresh_font_texture varsa çağır
    if impl is not None:
        if hasattr(impl, "refresh_font_texture"):
            try:
                impl.refresh_font_texture()
                logger.warning("[font] refresh_font_texture OK")
            except Exception as e:
                logger.error("[font] refresh hatası: %s", e)
        else:
            logger.error("[font] impl'de refresh_font_texture YOK! metotlar: %s",
                         [m for m in dir(impl) if "font" in m.lower()])
    else:
        logger.error("[font] impl=None")

    return {"font": font_obj, "path": path, "size": font_size}


def apply_dark_theme():
    """Kivy panelin koyu mavi teması."""
    style = imgui.get_style()
    colors = style.colors

    style.window_rounding        = 6.0
    style.child_rounding         = 4.0
    style.frame_rounding         = 4.0
    style.popup_rounding         = 6.0
    style.scrollbar_rounding     = 6.0
    style.grab_rounding          = 4.0

    style.window_padding         = (10, 10)
    style.frame_padding          = (8, 5)
    style.item_spacing           = (8, 6)
    style.item_inner_spacing     = (6, 4)
    style.indent_spacing         = 18
    style.scrollbar_size         = 12

    style.frame_border_size      = 1.0
    style.window_border_size     = 0.0

    c = colors
    c[imgui.COLOR_TEXT]                     = (0.90, 0.90, 0.90, 1.00)
    c[imgui.COLOR_TEXT_DISABLED]            = (0.50, 0.50, 0.50, 1.00)
    c[imgui.COLOR_WINDOW_BACKGROUND]        = (0.13, 0.15, 0.20, 0.97)
    c[imgui.COLOR_CHILD_BACKGROUND]         = (0.10, 0.12, 0.16, 1.00)
    c[imgui.COLOR_POPUP_BACKGROUND]         = (0.11, 0.13, 0.18, 0.98)
    c[imgui.COLOR_BORDER]                   = (0.30, 0.33, 0.40, 0.60)
    c[imgui.COLOR_BORDER_SHADOW]            = (0.00, 0.00, 0.00, 0.00)
    c[imgui.COLOR_FRAME_BACKGROUND]         = (0.15, 0.18, 0.24, 1.00)
    c[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = (0.20, 0.24, 0.32, 1.00)
    c[imgui.COLOR_FRAME_BACKGROUND_ACTIVE]  = (0.24, 0.30, 0.40, 1.00)
    c[imgui.COLOR_TITLE_BACKGROUND]         = (0.10, 0.13, 0.18, 1.00)
    c[imgui.COLOR_TITLE_BACKGROUND_ACTIVE]  = (0.16, 0.20, 0.28, 1.00)
    c[imgui.COLOR_TITLE_BACKGROUND_COLLAPSED]=(0.10, 0.13, 0.18, 0.70)
    c[imgui.COLOR_SCROLLBAR_BACKGROUND]     = (0.10, 0.12, 0.16, 0.80)
    c[imgui.COLOR_SCROLLBAR_GRAB]           = (0.30, 0.36, 0.46, 1.00)
    c[imgui.COLOR_SCROLLBAR_GRAB_HOVERED]   = (0.40, 0.48, 0.60, 1.00)
    c[imgui.COLOR_SCROLLBAR_GRAB_ACTIVE]    = (0.50, 0.60, 0.75, 1.00)
    c[imgui.COLOR_CHECK_MARK]               = (0.40, 0.90, 0.55, 1.00)
    c[imgui.COLOR_SLIDER_GRAB]              = (0.35, 0.55, 0.85, 1.00)
    c[imgui.COLOR_SLIDER_GRAB_ACTIVE]       = (0.45, 0.65, 0.95, 1.00)
    c[imgui.COLOR_BUTTON]                   = (0.20, 0.26, 0.34, 1.00)
    c[imgui.COLOR_BUTTON_HOVERED]           = (0.28, 0.36, 0.48, 1.00)
    c[imgui.COLOR_BUTTON_ACTIVE]            = (0.35, 0.45, 0.60, 1.00)
    c[imgui.COLOR_HEADER]                   = (0.20, 0.28, 0.40, 1.00)
    c[imgui.COLOR_HEADER_HOVERED]           = (0.28, 0.38, 0.52, 1.00)
    c[imgui.COLOR_HEADER_ACTIVE]            = (0.35, 0.48, 0.65, 1.00)
    c[imgui.COLOR_SEPARATOR]                = (0.30, 0.33, 0.40, 0.60)
    c[imgui.COLOR_RESIZE_GRIP]              = (0.40, 0.48, 0.60, 0.60)
    c[imgui.COLOR_RESIZE_GRIP_HOVERED]      = (0.55, 0.65, 0.80, 0.80)
    c[imgui.COLOR_RESIZE_GRIP_ACTIVE]       = (0.65, 0.78, 0.95, 1.00)
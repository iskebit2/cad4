# assets/themes.py
from __future__ import annotations

import os
from imgui_bundle import imgui

def _load_fonts(font_size: int = 16):
    io = imgui.get_io()
    win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    text_font = os.path.join(win_fonts, "segoeui.ttf")
    symbol_font = os.path.join(win_fonts, "seguisym.ttf")

    if not os.path.isfile(text_font):
        io.fonts.add_font_default()
        return None

    font_obj = io.fonts.add_font_from_file_ttf(text_font, font_size)

    if os.path.isfile(symbol_font):
        cfg = imgui.ImFontConfig()
        cfg.merge_mode = True
        io.fonts.add_font_from_file_ttf(symbol_font, font_size, cfg)

    return font_obj

def _apply_dark_theme() -> None:
    imgui.style_colors_dark()
    s = imgui.get_style()

    # -------------------------------------------------
    # Ölçüler
    # -------------------------------------------------
    s.window_rounding = 4.0
    s.child_rounding = 3.0
    s.frame_rounding = 3.0
    s.popup_rounding = 4.0
    s.scrollbar_rounding = 4.0
    s.grab_rounding = 3.0
    s.tab_rounding = 3.0

    s.window_padding = imgui.ImVec2(9, 8)
    s.frame_padding = imgui.ImVec2(6, 3)
    s.item_spacing = imgui.ImVec2(6, 5)
    s.item_inner_spacing = imgui.ImVec2(5, 4)

    s.indent_spacing = 16.0
    s.scrollbar_size = 11.0
    s.grab_min_size = 10.0

    s.window_border_size = 1.0
    s.child_border_size = 1.0
    s.frame_border_size = 0.0
    s.popup_border_size = 1.0

    # -------------------------------------------------
    # Renk yardımcıları
    # -------------------------------------------------
    def rgb(hex_color, alpha=1.0):
        return imgui.ImVec4(
            ((hex_color >> 16) & 255) / 255.0,
            ((hex_color >> 8) & 255) / 255.0,
            (hex_color & 255) / 255.0,
            alpha
        )

    def set_color(col, hex_color, alpha=1.0):
        s.set_color_(col, rgb(hex_color, alpha))

    # -------------------------------------------------
    # Metin
    # -------------------------------------------------
    set_color(imgui.Col_.text, 0xD8DEE9)
    set_color(imgui.Col_.text_disabled, 0x697586)

    # -------------------------------------------------
    # Ana yüzeyler
    # -------------------------------------------------
    set_color(imgui.Col_.window_bg, 0x20242B)
    set_color(imgui.Col_.child_bg, 0x252A32)
    set_color(imgui.Col_.popup_bg, 0x2B3039, 0.98)

    # -------------------------------------------------
    # Kenarlıklar
    # -------------------------------------------------
    set_color(imgui.Col_.border, 0x414957, 0.65)
    set_color(imgui.Col_.border_shadow, 0x000000, 0.0)

    # -------------------------------------------------
    # Input / Combo
    # -------------------------------------------------
    set_color(imgui.Col_.frame_bg, 0x303741)
    set_color(imgui.Col_.frame_bg_hovered, 0x3A4553)
    set_color(imgui.Col_.frame_bg_active, 0x414F60)

    # -------------------------------------------------
    # Başlıklar
    # -------------------------------------------------
    set_color(imgui.Col_.title_bg, 0x1B1F25)
    set_color(imgui.Col_.title_bg_active, 0x303946)
    set_color(imgui.Col_.title_bg_collapsed, 0x1B1F25)

    set_color(imgui.Col_.menu_bar_bg, 0x252A32)

    # -------------------------------------------------
    # Butonlar
    # -------------------------------------------------
    set_color(imgui.Col_.button, 0x3B526D)
    set_color(imgui.Col_.button_hovered, 0x52769C)
    set_color(imgui.Col_.button_active, 0x304B69)

    # -------------------------------------------------
    # Header / Tree / Selectable
    # -------------------------------------------------
    set_color(imgui.Col_.header, 0x405A78, 0.55)
    set_color(imgui.Col_.header_hovered, 0x52769C, 0.65)
    set_color(imgui.Col_.header_active, 0x52769C, 0.85)

    # -------------------------------------------------
    # Ayraçlar
    # -------------------------------------------------
    set_color(imgui.Col_.separator, 0x46505D)
    set_color(imgui.Col_.separator_hovered, 0x6685A7)
    set_color(imgui.Col_.separator_active, 0x7899BD)

    # -------------------------------------------------
    # Checkbox / Slider
    # -------------------------------------------------
    set_color(imgui.Col_.check_mark, 0x8CB4DC)
    set_color(imgui.Col_.slider_grab, 0x668EB8)
    set_color(imgui.Col_.slider_grab_active, 0x91BCE5)

    # -------------------------------------------------
    # Scrollbar
    # -------------------------------------------------
    set_color(imgui.Col_.scrollbar_bg, 0x1D2229)
    set_color(imgui.Col_.scrollbar_grab, 0x414B58)
    set_color(imgui.Col_.scrollbar_grab_hovered, 0x596779)
    set_color(imgui.Col_.scrollbar_grab_active, 0x71869F)

    # -------------------------------------------------
    # Tab
    # -------------------------------------------------
    set_color(imgui.Col_.tab, 0x292F38)
    set_color(imgui.Col_.tab_hovered, 0x465C74)
    set_color(imgui.Col_.tab_selected, 0x40566F)
    set_color(imgui.Col_.tab_selected_overline, 0x8CB4DC)
    set_color(imgui.Col_.tab_dimmed, 0x222831)
    set_color(imgui.Col_.tab_dimmed_selected, 0x343E4A)
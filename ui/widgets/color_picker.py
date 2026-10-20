# ui/widgets/color_picker.py
"""
Renk editörü widget'ı.
- imgui.color_edit3 ile popup renk seçici
- Hızlı erişim için 12 renkli palet
- Tuple[float, float, float] formatında çalışır
"""
import imgui

# 12 renkli standart palet (yapısal CAD uygulamalarında yaygın)
DEFAULT_PALETTE = [
    (0.90, 0.90, 0.90),   # açık gri (varsayılan)
    (0.55, 0.55, 0.55),   # orta gri
    (0.20, 0.20, 0.20),   # koyu gri
    (0.95, 0.30, 0.25),   # kırmızı
    (0.95, 0.55, 0.20),   # turuncu
    (0.95, 0.85, 0.25),   # sarı
    (0.35, 0.85, 0.40),   # yeşil
    (0.25, 0.75, 0.90),   # camgöbeği
    (0.30, 0.50, 0.95),   # mavi
    (0.60, 0.35, 0.90),   # mor
    (0.90, 0.35, 0.70),   # pembe
    (0.60, 0.40, 0.20),   # kahverengi
]


def color_edit3(label: str, color, palette=DEFAULT_PALETTE, show_popup: bool = True, expanded: bool = False):
    """
    Renk editörü. Palet + popup renk seçici.

    Args:
        label: Görünen isim ("" ise sadece widget)
        color: Tuple[float, float, float] (0..1)
        palette: Hızlı seçim için renk listesi
        show_popup: imgui.color_edit3 açılır pencere göster

    Returns:
        (changed: bool, new_color: Tuple[float, float, float])
    """
    r, g, b = (float(color[0]), float(color[1]), float(color[2])) if color else (0.8, 0.8, 0.8)
    changed = False

    if label:
        imgui.text(label)
        imgui.same_line()

    # 1) imgui.color_edit3 — popup renk seçici
    if show_popup:
        c, new_rgb = imgui.color_edit3(f"##{label}_edit", r, g, b)
        if c:
            r, g, b = new_rgb
            changed = True
        imgui.same_line()
    else:
        # Popup yoksa sadece küçük renk kutusu
        imgui.color_button(f"##{label}_swatch", r, g, b)
        imgui.same_line()

    # 2) Palet açılır panel
    if imgui.button(f"Palet ▾##{label}_pal"):
        imgui.open_popup(f"##{label}_palette_popup")

    if imgui.begin_popup(f"##{label}_palette_popup"):
        cols = 4
        for i, (pr, pg, pb) in enumerate(palette):
            imgui.push_style_color(imgui.COLOR_BUTTON, pr, pg, pb, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, pr * 1.15, pg * 1.15, pb * 1.15, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, pr * 0.85, pg * 0.85, pb * 0.85, 1.0)
            clicked = imgui.button(f"##pal_{label}_{i}", width=28, height=28)
            imgui.pop_style_color(3)
            if clicked:
                r, g, b = pr, pg, pb
                changed = True
                imgui.close_current_popup()
            # 4'lü grid
            if (i + 1) % cols != 0 and i != len(palette) - 1:
                imgui.same_line()
            # Satır aralığı
            if (i + 1) % cols == 0:
                pass
        imgui.end_popup()

    if expanded and imgui.collapsing_header(f"RGB##{label}_rgb")[0]:
        imgui.push_item_width(120)
        c, r = imgui.slider_float(f"R##{label}", r, 0.0, 1.0)
        changed = changed or c
        c, g = imgui.slider_float(f"G##{label}", g, 0.0, 1.0)
        changed = changed or c
        c, b = imgui.slider_float(f"B##{label}", b, 0.0, 1.0)
        changed = changed or c
        imgui.pop_item_width()
        
    return changed, (r, g, b)
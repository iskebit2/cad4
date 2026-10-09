# app/toolbar.py
"""Toolbar — üst araç çubuğu widget'ı ve buton yönetimi."""

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

FONT_DEFAULT = "DejaVuSans"

def build_toolbar(callbacks):
    """
    Toolbar'ı oluştur.
    
    callbacks: dict
        'menu'       : fn
        'open'       : fn
        'save'       : fn
        'draw'       : fn
        'import_sap' : fn
        'visibility' : fn
        'wind'       : fn
    """
    bar = BoxLayout(
        size_hint_y=None,
        height=dp(24),
        pos_hint={'top': 1, 'x': 0},
        spacing=dp(6),
        padding=(dp(6), dp(4)),
    )

    def btn(text, width, color, on_release=None, **kw):
        b = Button(
            text=text,
            size_hint_x=None,
            width=dp(width),
            font_size=dp(kw.pop("font_size", 12)),
            font_name=FONT_DEFAULT,
            background_normal="",
            background_color=color,
            color=(1, 1, 1, 1),
            bold=True,
            **kw,
        )
        if on_release:
            b.bind(on_release=on_release)
        return b

    # Hamburger
    bar.add_widget(btn("☰", 36, (0.15, 0.20, 0.28, 1),
                       callbacks.get("menu"), font_size=16))

    # Aç
    bar.add_widget(btn("open", 65, (0.18, 0.35, 0.55, 1),
                       callbacks.get("open"), font_size=13))

    # Kaydet
    bar.add_widget(btn("save", 75, (0.18, 0.50, 0.32, 1),
                       callbacks.get("save"), font_size=13))

    # Çizim modu
    draw_btn = btn("draw (D)", 95, (0.22, 0.28, 0.38, 1),
                   callbacks.get("draw"), font_size=12)
    bar.add_widget(draw_btn)

    # SAP Import
    bar.add_widget(btn("SAP Import", 95, (0.25, 0.22, 0.38, 1),
                       callbacks.get("import_sap")))

    # Durum bilgisi (ortada esnek boşluk)
    lbl = Label(
        text="MODEL: YENİ SAHNE",
        halign="left",
        valign="middle",
        color=(0.6, 0.65, 0.72, 1),
        font_size=dp(12),
    )
    lbl.bind(size=lbl.setter("text_size"))
    bar.add_widget(lbl)

    # Filtre
    bar.add_widget(btn("VIS", 80, (0.20, 0.40, 0.50, 1),
                       callbacks.get("visibility")))

    # Rüzgar
    bar.add_widget(btn("zones", 105, (0.15, 0.45, 0.60, 1),
                       callbacks.get("wind")))

    return bar, lbl, draw_btn
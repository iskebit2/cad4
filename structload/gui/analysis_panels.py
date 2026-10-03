# gui/analysis_panels.py
"""
Analiz Sekmeleri İçin GUI Panelleri

- AnalysisDataPanel : Wind / Snow / Earthquake config formu
- ResultPanel       : Analiz sonuç metni
"""

import ast
import json
import traceback

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput


# ======================================================================
# AnalysisDataPanel
# ======================================================================

class AnalysisDataPanel(BoxLayout):
    """
    Analiz config formu.

    - Skalar alanlar (int/float/str/bool) düzenlenebilir.
    - dict/list alanlar salt okunur + "Extra" butonu ile popup'ta düzenlenir.
    """

    def __init__(
        self,
        title="",
        panel_key="",
        data=None,
        show_spectrum_button=False,
        **kwargs,
    ):
        super().__init__(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(8),
            **kwargs,
        )
        self.title = title
        self.panel_key = panel_key
        self.data = dict(data or {})
        self.original_data = json.loads(json.dumps(self.data))
        self.inputs = {}

        self.on_calculate = None
        self.on_spectrum = None

        # -------- Form (scrollable) --------
        scroll = ScrollView(do_scroll_x=False)
        self.form = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
            size_hint_y=None,
            padding=[dp(4), dp(4)],
        )
        self.form.bind(minimum_height=self.form.setter("height"))
        scroll.add_widget(self.form)
        self.add_widget(scroll)

        # -------- Spektrum butonu (deprem) --------
        if show_spectrum_button:
            self.spectrum_button = Button(
                text="📈  Spektrum Grafiği",
                background_color=(0.20, 0.75, 0.75, 1),
                background_normal="",
                size_hint_y=None,
                height=dp(48),
            )
            self.spectrum_button.bind(on_press=self._on_spectrum)
            self.spectrum_button.disabled = True
            self.spectrum_button.opacity = 0.5
            self.add_widget(self.spectrum_button)
        else:
            self.spectrum_button = None

        # -------- Aksiyon butonları --------
        btns = BoxLayout(
            size_hint_y=None,
            height=dp(52),
            spacing=dp(6),
        )

        self.reset_btn = Button(
            text="Geri Al",
            background_color=(0.95, 0.65, 0.15, 1),
            background_normal="",
        )
        self.calc_btn = Button(
            text="Hesapla",
            background_color=(0.20, 0.70, 0.35, 1),
            background_normal="",
        )

        btns.add_widget(self.reset_btn)
        btns.add_widget(self.calc_btn)
        self.add_widget(btns)

        self.reset_btn.bind(on_press=self.reset)
        self.calc_btn.bind(on_press=self._calculate)

        # Formu doldur
        self._build()

    # ------------------------------------------------------------------
    def set_extra_enabled(self, enabled: bool):
        """Rüzgâr için points/polygons uygunluğunu gösterir (görsel ipucu)."""
        if enabled:
            self.calc_btn.background_color = (0.20, 0.70, 0.35, 1)
        else:
            self.calc_btn.background_color = (0.55, 0.55, 0.55, 1)

    # ------------------------------------------------------------------
    def _build(self):
        self.form.clear_widgets()
        self.inputs.clear()

        if not self.data:
            self.form.add_widget(Label(
                text="📂 Veri yok",
                color=(0.55, 0.55, 0.60, 1),
                size_hint_y=None,
                height=dp(60),
            ))
            return

        for key, value in self.data.items():
            self.form.add_widget(self._create_row(key, value))

    def _create_row(self, key, value):
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            spacing=dp(6),
            padding=[dp(4), dp(4)],
        )

        lbl = Label(
            text=str(key),
            size_hint_x=0.35,
            halign="left",
            valign="middle",
            font_size=dp(14),
        )
        lbl.bind(size=lbl.setter("text_size"))
        row.add_widget(lbl)

        # bool
        if isinstance(value, bool):
            w = CheckBox(active=value, size_hint_x=0.65)
            self.inputs[key] = w
            row.add_widget(w)
            return row

        # dict / list → salt okunur özet + edit butonu
        if isinstance(value, (dict, list)):
            ozet = TextInput(
                text=json.dumps(value, ensure_ascii=False),
                readonly=True,
                font_size=dp(11),
                size_hint_x=0.55,
            )
            edit_btn = Button(
                text="✎",
                size_hint_x=0.10,
                background_color=(0.4, 0.5, 0.8, 1),
                background_normal="",
            )
            edit_btn.bind(
                on_press=lambda inst, k=key: self._edit_complex(k)
            )
            self.inputs[key] = ozet
            row.add_widget(ozet)
            row.add_widget(edit_btn)
            return row

        # skalar
        w = TextInput(
            text=str(value),
            multiline=False,
            font_size=dp(15),
            size_hint_x=0.65,
        )
        self.inputs[key] = w
        row.add_widget(w)
        return row

    # ------------------------------------------------------------------
    def _edit_complex(self, key):
        """dict/list alanını popup içinde düzenlet."""
        mevcut = self.data.get(key, [] if isinstance(self.data.get(key), list) else {})

        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        editor = TextInput(
            text=json.dumps(mevcut, ensure_ascii=False, indent=2),
            multiline=True,
            font_size=dp(12),
        )
        content.add_widget(editor)

        btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        ok = Button(text="Tamam", background_color=(0.2, 0.7, 0.35, 1),
                    background_normal="")
        iptal = Button(text="İptal", background_color=(0.85, 0.3, 0.3, 1),
                       background_normal="")
        btns.add_widget(ok)
        btns.add_widget(iptal)
        content.add_widget(btns)

        popup = Popup(title=f"Düzenle: {key}", content=content,
                      size_hint=(0.9, 0.8))

        def _kaydet(*_):
            try:
                yeni = json.loads(editor.text)
            except json.JSONDecodeError as e:
                self._popup("JSON Hatası", f"Geçersiz JSON:\n{e}")
                return
            self.data[key] = yeni
            # input'u güncelle
            if key in self.inputs:
                self.inputs[key].text = json.dumps(yeni, ensure_ascii=False)
            popup.dismiss()

        ok.bind(on_press=_kaydet)
        iptal.bind(on_press=popup.dismiss)
        popup.open()

    # ------------------------------------------------------------------
    def _convert(self, key, widget):
        old = self.data.get(key)

        if isinstance(old, bool):
            return widget.active

        if isinstance(old, (dict, list)):
            # salt okunur özet — dokunmuyoruz
            return self.data.get(key, old)

        text = widget.text.strip()
        if text == "":
            raise ValueError(f"'{key}' boş olamaz")

        if isinstance(old, int) and not isinstance(old, bool):
            return int(float(text))
        if isinstance(old, float):
            return float(text)
        return text

    # ------------------------------------------------------------------
    def get_data(self) -> dict:
        try:
            return {
                k: self._convert(k, w)
                for k, w in self.inputs.items()
            }
        except Exception as e:
            self._popup("Geçersiz Değer", str(e))
            return dict(self.data)

    # ------------------------------------------------------------------
    def set_data(self, data: dict):
        self.data = dict(data or {})
        self.original_data = json.loads(json.dumps(self.data))
        self._build()

    # ------------------------------------------------------------------
    def reset(self, *args):
        self.data = json.loads(json.dumps(self.original_data))
        self._build()

    def _calculate(self, *args):
        self.data = self.get_data()
        if self.on_calculate:
            self.on_calculate(self.data)

    def _on_spectrum(self, *args):
        if self.on_spectrum:
            self.on_spectrum()

    def set_spectrum_enabled(self, enabled: bool):
        if self.spectrum_button:
            self.spectrum_button.disabled = not enabled
            self.spectrum_button.opacity = 1.0 if enabled else 0.5

    def _popup(self, title, msg):
        popup = Popup(
            title=title,
            content=Label(text=str(msg)),
            size_hint=(0.7, 0.4),
        )
        popup.open()


# ======================================================================
# ResultPanel
# ======================================================================

class ResultPanel(BoxLayout):
    """Alt kısımda analiz sonuç metni."""

    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical",
            size_hint_y=0.35,
            spacing=dp(4),
            padding=[dp(4), dp(4)],
            **kwargs,
        )
        self.add_widget(Label(
            text="Analiz Sonucu",
            size_hint_y=None,
            height=dp(24),
            bold=True,
            color=(0.2, 0.4, 0.8, 1),
        ))
        self.text = TextInput(
            readonly=True,
            multiline=True,
            font_size=dp(12),
        )
        self.add_widget(self.text)

    def set_text(self, value: str):
        self.text.text = value
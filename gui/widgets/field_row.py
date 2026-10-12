# gui/widgets/field_row.py
from enum import Enum

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
from kivy.metrics import dp


class FieldRow(BoxLayout):
    """
    Tek bir özellik satırı: label + tip duyarlı editör.
      bool  → CheckBox
      enum  → Spinner (combobox)
      float/int → TextInput (numeric)
      color (3 float) → 3 TextInput
      str   → TextInput
    """

    def __init__(self, key, value, *, kind="str", choices=None,
                 editable=True, field_name=None, element=None,
                 on_change=None, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(28))
        kwargs.setdefault('spacing', dp(4))
        super().__init__(**kwargs)

        self._key = key
        self._field_name = field_name if field_name is not None else key
        self._element = element
        self._kind = kind
        self._choices = list(choices) if choices else []
        self._editable = editable
        self._on_change = on_change

        # --- Label ---
        lbl = Label(
            text=str(key),
            size_hint_x=0.45,
            size_hint_y=1,
            halign='left', valign='middle',
            font_size=dp(11), font_name="DejaVuSans.ttf",
            color=(0.85, 0.85, 0.85, 1.0),
        )
        lbl.bind(size=lbl.setter('text_size'))
        self.add_widget(lbl)

        # --- Editor (kalan alanı doldurur) ---
        self.editor = self._make_editor(value)
        self.add_widget(self.editor)

    # ---------------------------------------------------------
    # EDITOR FACTORY
    # ---------------------------------------------------------
    def _make_editor(self, value):
        if self._kind == "bool":
            return self._make_bool(value)
        if self._kind == "enum" or (self._choices and self._kind == "str"):
            return self._make_spinner(value)
        if self._kind == "color":
            return self._make_color(value)
        return self._make_text(value)

    def _make_bool(self, value):
        # CheckBox'ı bir BoxLayout'a sarıp dikey ortalayalım
        wrap = BoxLayout(
            orientation='horizontal',
            size_hint_x=0.55,
            size_hint_y=1,
            padding=(dp(4), 0, 0, 0),
        )
        cb = CheckBox(
            active=bool(value),
            size_hint=(None, None),
            size=(dp(22), dp(22)),
            disabled=not self._editable,
            color=(0.5, 0.9, 0.5, 1.0) if self._editable
                  else (0.6, 0.6, 0.6, 1.0),
        )
        # Dikey ortalama
        cb.pos_hint = {'center_y': 0.5}
        wrap.add_widget(cb)
        wrap.add_widget(BoxLayout())  # sağ boşluk

        cb._kind = "bool"
        wrap._kind = "bool"
        wrap._cb = cb
        if self._on_change:
            cb.bind(active=lambda *_: self._on_change())
        return wrap

    def _make_spinner(self, value):
        values = [str(c) for c in self._choices]
        text = str(value)
        if values and text not in values:
            values = [text] + values
        sp = Spinner(
            text=text,
            values=values,
            size_hint_x=0.55,
            size_hint_y=1,
            font_size=dp(11),
            disabled=not self._editable,
        )
        sp._kind = "enum"
        if self._on_change:
            sp.bind(text=lambda *_: self._on_change())
        return sp

    def _make_text(self, value):
        if isinstance(value, bool):
            value = "true" if value else "false"
        ti = TextInput(
            text=str(value),
            size_hint_x=0.55,
            size_hint_y=1,
            multiline=False,
            readonly=not self._editable,
            font_size=dp(11),
            background_color=(0.10, 0.12, 0.16, 1.0) if not self._editable
                             else (0.15, 0.18, 0.24, 1.0),
            foreground_color=(0.9, 0.9, 0.9, 1.0),
            padding=(dp(4), dp(2), dp(4), dp(2)),
        )
        ti._kind = self._kind
        if self._on_change:
            ti.bind(text=lambda *_: self._on_change())
        return ti

    def _make_color(self, value):
        try:
            vals = [float(v) for v in (value or [0.7, 0.7, 0.7])[:3]]
        except Exception:
            vals = [0.7, 0.7, 0.7]
        while len(vals) < 3:
            vals.append(0.7)

        row = BoxLayout(size_hint_x=0.55, size_hint_y=1, spacing=dp(2))
        inputs = []
        for v in vals:
            ti = TextInput(
                text=f"{v:.2f}",
                multiline=False,
                readonly=not self._editable,
                font_size=dp(10),
                background_color=(0.15, 0.18, 0.24, 1.0),
                foreground_color=(0.9, 0.9, 0.9, 1.0),
                padding=(dp(2), dp(2), dp(2), dp(2)),
            )
            row.add_widget(ti)
            inputs.append(ti)
        row._kind = "color"
        row._inputs = inputs
        if self._on_change:
            for ti in inputs:
                ti.bind(text=lambda *_: self._on_change())
        return row

    # ---------------------------------------------------------
    # OKUMA
    # ---------------------------------------------------------
    def get_value(self):
        ed = self.editor
        k = getattr(ed, '_kind', self._kind)

        if k == "bool":
            return bool(ed._cb.active)

        if k == "enum":
            return self._coerce_enum(ed.text)

        if k == "color":
            out = []
            for ti in ed._inputs:
                try:
                    out.append(float(ti.text.replace(",", ".")))
                except ValueError:
                    out.append(0.0)
            return out

        text = (ed.text or "").strip()
        if self._kind == "float":
            if text == "":
                return 0.0
            try:
                return float(text.replace(",", "."))
            except ValueError:
                raise ValueError(f"{self._key}: geçersiz sayı '{text}'")
        if self._kind == "int":
            if text == "":
                return 0
            try:
                return int(float(text))
            except ValueError:
                raise ValueError(f"{self._key}: geçersiz tamsayı '{text}'")
        return text

    def _coerce_enum(self, text):
        if not self._choices:
            return text
        for c in self._choices:
            if str(c) == text:
                return c
        first = self._choices[0]
        if isinstance(first, Enum):
            try:
                return type(first)[text]
            except KeyError:
                pass
        try:
            return int(text)
        except ValueError:
            return text

    def set_value(self, value):
        ed = self.editor
        k = getattr(ed, '_kind', self._kind)
        if k == "bool":
            ed._cb.active = bool(value)
        elif k == "enum":
            ed.text = str(value)
        elif k == "color":
            vals = [float(v) for v in (value or [0.7, 0.7, 0.7])[:3]]
            for ti, v in zip(ed._inputs, vals):
                ti.text = f"{v:.2f}"
        else:
            ed.text = str(value)
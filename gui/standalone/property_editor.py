# gui/standalone/property_editor.py
"""
Bağımsız Property Editor.

Kimseye bağımlı değil. Sadece:
    editor = PropertyEditor(schema, values, title="...")
    editor.on_apply = callback
    editor.open()

Kivy penceresi olarak açar. on_apply(values) çağrılır.
"""
from enum import Enum

from kivy.config import Config
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.popup import Popup
from kivy.metrics import dp
from kivy.properties import BooleanProperty


# ============================================================
# YARDIMCI: değer okuma / yazma (noktalı yol)
# ============================================================

def get_path(data: dict, path: str):
    parts = path.split(".")
    cur = data
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, (list, tuple)) and p.isdigit():
            cur = cur[int(p)]
        else:
            return None
    return cur


def set_path(data: dict, path: str, value):
    parts = path.split(".")
    cur = data
    for p in parts[:-1]:
        if p not in cur or cur[p] is None:
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


# ============================================================
# FIELD ROW (tipe duyarlı)
# ============================================================

class _GroupHeader(ButtonBehavior, Label):
    expanded = BooleanProperty(True)

    def __init__(self, **kw):
        kw.setdefault('markup', True)
        kw.setdefault('size_hint_y', None)
        kw.setdefault('height', dp(28))
        kw.setdefault('halign', 'left')
        kw.setdefault('valign', 'middle')
        kw.setdefault('font_size', dp(13))
        kw.setdefault('color', (0.5, 0.8, 1.0, 1.0))
        super().__init__(**kw)
        self.bind(size=self.setter('text_size'))


class FieldRow(BoxLayout):
    """label + tip duyarlı editör."""

    def __init__(self, key, value, *, kind="str", choices=None,
                 editable=True, label=None, **kw):
        kw.setdefault('orientation', 'horizontal')
        kw.setdefault('size_hint_y', None)
        kw.setdefault('height', dp(30))
        kw.setdefault('spacing', dp(4))
        super().__init__(**kw)

        self.field_key = key
        self.kind = kind
        self.choices = list(choices) if choices else []
        self.editable = editable

        lbl = Label(
            text=str(label if label is not None else key),
            size_hint_x=0.42,
            halign='left', valign='middle',
            font_size=dp(11),
        )
        lbl.bind(size=lbl.setter('text_size'))
        self.add_widget(lbl)

        self.editor = self._make(value)
        self.add_widget(self.editor)

    def _make(self, value):
        if self.kind == "bool":
            return self._make_bool(value)
        if self.kind == "enum":
            return self._make_spinner(value)
        if self.kind == "color":
            return self._make_color(value)
        return self._make_text(value)

    # --- bool ---
    def _make_bool(self, value):
        # CheckBox tek başına, ortalanmış
        row = BoxLayout(size_hint_x=0.58, orientation='horizontal')
        row.add_widget(Widget())  # sol boşluk
        cb = CheckBox(
            active=bool(value),
            size_hint=(None, None),
            size=(dp(26), dp(26)),
            disabled=not self.editable,
        )
        cb.pos_hint = {'center_y': 0.5}
        row.add_widget(cb)
        row.add_widget(Widget())  # sağ boşluk
        row._cb = cb
        return row

    # --- enum ---
    def _make_spinner(self, value):
        values = [str(c) for c in self.choices]
        text = str(value)
        if values and text not in values:
            values.insert(0, text)
        sp = Spinner(
            text=text, values=values,
            size_hint_x=0.58,
            font_size=dp(11),
            disabled=not self.editable,
        )
        return sp

    # --- text ---
    def _make_text(self, value):
        ti = TextInput(
            text="" if value is None else str(value),
            size_hint_x=0.58,
            multiline=False,
            readonly=not self.editable,
            font_size=dp(11),
            background_color=(0.10, 0.12, 0.16, 1.0) if not self.editable
                             else (0.15, 0.18, 0.24, 1.0),
            foreground_color=(0.9, 0.9, 0.9, 1.0),
            padding=(dp(4), dp(2), dp(4), dp(2)),
        )
        return ti

    # --- color ---
    def _make_color(self, value):
        try:
            vals = [float(v) for v in (value or [0.7, 0.7, 0.7])[:3]]
        except Exception:
            vals = [0.7, 0.7, 0.7]
        while len(vals) < 3:
            vals.append(0.7)

        row = BoxLayout(size_hint_x=0.58, spacing=dp(2))
        inputs = []
        for v in vals:
            ti = TextInput(
                text=f"{v:.2f}",
                multiline=False,
                readonly=not self.editable,
                font_size=dp(10),
                padding=(dp(2), dp(2), dp(2), dp(2)),
            )
            row.add_widget(ti)
            inputs.append(ti)
        row._inputs = inputs
        return row

    # ---------------------------------------------------------
    def get_value(self):
        ed = self.editor
        if self.kind == "bool":
            return bool(ed._cb.active)
        if self.kind == "enum":
            return self._coerce_enum(ed.text)
        if self.kind == "color":
            out = []
            for ti in ed._inputs:
                try:
                    out.append(float((ti.text or "0").replace(",", ".")))
                except ValueError:
                    out.append(0.0)
            return out
        text = (ed.text or "").strip()
        if self.kind == "float":
            if text == "":
                return 0.0
            try:
                return float(text.replace(",", "."))
            except ValueError:
                raise ValueError(f"{self.field_key}: geçersiz sayı")
        if self.kind == "int":
            if text == "":
                return 0
            try:
                return int(float(text))
            except ValueError:
                raise ValueError(f"{self.field_key}: geçersiz tamsayı")
        return text

    def _coerce_enum(self, text):
        if not self.choices:
            return text
        for c in self.choices:
            if str(c) == text:
                return c
        first = self.choices[0]
        if isinstance(first, Enum):
            try:
                return type(first)[text]
            except KeyError:
                pass
        try:
            return int(text)
        except ValueError:
            return text


# ============================================================
# COLLAPSIBLE GROUP
# ============================================================

class CollapsibleGroup(BoxLayout):
    def __init__(self, title, **kw):
        kw.setdefault('orientation', 'vertical')
        kw.setdefault('size_hint_y', None)
        kw.setdefault('spacing', 0)
        super().__init__(**kw)

        self.title_text = title
        self.expanded = True
        self.fields = []

        self.header = _GroupHeader(text=f"[b]▼  {title}[/b]")
        self.header.bind(on_release=self._toggle)
        self.add_widget(self.header)

        self.content = GridLayout(
            cols=1, size_hint_y=None, spacing=dp(2),
            padding=(dp(8), dp(4), dp(4), dp(4)),
        )
        self.content.bind(minimum_height=self.content.setter('height'))
        self.add_widget(self.content)
        self.bind(minimum_height=self.setter('height'))

    def _toggle(self, *_):
        self.expanded = not self.expanded
        self.header.text = f"[b]{'▼' if self.expanded else '▶'}  {self.title_text}[/b]"
        if self.expanded:
            self.content.opacity = 1
            self.content.disabled = False
            self.content.height = self.content.minimum_height
        else:
            self.content.opacity = 0
            self.content.disabled = True
            self.content.height = 0

    def add_field(self, key, value, *, kind="str", choices=None,
                  label=None, editable=True):
        row = FieldRow(key, value, kind=kind, choices=choices,
                       label=label, editable=editable)
        self.content.add_widget(row)
        self.fields.append(row)


# ============================================================
# PROPERTY EDITOR — Bağımsız pencere
# ============================================================

class PropertyEditor(Popup):
    """
    Bağımsız property editör penceresi (Kivy Popup).

    Kullanım:
        editor = PropertyEditor(schema, values, title="Node N1")
        editor.on_apply = lambda new_values: print(new_values)
        editor.open()
    """

    def __init__(self, schema, values, *, title="Özellikler", **kw):
        kw.setdefault('title', title)
        kw.setdefault('size_hint', (0.6, 0.8))
        kw.setdefault('auto_dismiss', False)
        super().__init__(**kw)

        self.schema = schema
        self.values = dict(values or {})
        self.groups = []
        self.on_apply = None   # dışarıdan set edilir
        self.on_cancel = None

        self._build()

    # ---------------------------------------------------------
    def _build(self):
        root = BoxLayout(orientation='vertical', spacing=dp(4),
                         padding=dp(6))

        # Scrollable içerik
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        box = BoxLayout(orientation='vertical', size_hint_y=None,
                        spacing=dp(2))
        box.bind(minimum_height=box.setter('height'))

        for group_def in self.schema:
            g = CollapsibleGroup(group_def.get("group", "Genel"))
            for f in group_def.get("fields", []):
                key = f["key"]
                kind = f.get("kind", "str")
                cur_val = get_path(self.values, key)
                g.add_field(
                    key=key,
                    value=cur_val,
                    kind=kind,
                    choices=f.get("choices"),
                    label=f.get("label"),
                    editable=f.get("editable", True),
                )
            box.add_widget(g)
            self.groups.append(g)

        scroll.add_widget(box)
        root.add_widget(scroll)

        # Buton çubuğu
        bar = BoxLayout(orientation='horizontal', size_hint_y=None,
                        height=dp(38), spacing=dp(4))

        cancel = Button(text="Cancel", background_normal='',
                        background_color=(0.45, 0.20, 0.20, 1.0),
                        font_size=dp(12))
        cancel.bind(on_release=self._do_cancel)

        apply_btn = Button(text="Apply", background_normal='',
                           background_color=(0.20, 0.55, 0.30, 1.0),
                           font_size=dp(12), bold=True)
        apply_btn.bind(on_release=self._do_apply)

        bar.add_widget(cancel)
        bar.add_widget(apply_btn)
        root.add_widget(bar)

        self.content = root

    # ---------------------------------------------------------
    def _collect(self):
        out = {}
        for g in self.groups:
            for row in g.fields:
                out[row.field_key] = row.get_value()
        return out

    def _do_apply(self, *_):
        try:
            new_values = self._collect()
        except ValueError as e:
            # basit hata göster
            self.title = f"HATA: {e}"
            return
        if callable(self.on_apply):
            self.on_apply(new_values)
        self.dismiss()

    def _do_cancel(self, *_):
        if callable(self.on_cancel):
            self.on_cancel()
        self.dismiss()
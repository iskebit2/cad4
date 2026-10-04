# gui/property_editor.py
"""
Dataclass alanlarını Kivy widget'larına çevirir.
"""
import dataclasses
from enum import Enum
from typing import Any, Callable, Dict, Tuple

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch


# (kind, widget, python_type) üçlüsü döner
FieldWidget = Tuple[str, Any, type]


def make_field_widget(name: str, value: Any) -> Tuple[BoxLayout, FieldWidget]:
    """Bir alan için (row_layout, (kind, widget, type)) üretir."""
    row = BoxLayout(size_hint_y=None, height=40, spacing=6)
    row.add_widget(Label(text=name, size_hint_x=0.35))

    if isinstance(value, Enum):
        sp = Spinner(
            text=str(value.value),
            values=[str(m.value) for m in type(value)],
            size_hint_x=0.65,
        )
        row.add_widget(sp)
        return row, ("enum", sp, type(value))

    if isinstance(value, bool):
        sw = Switch(active=value, size_hint_x=0.65)
        row.add_widget(sw)
        return row, ("bool", sw, bool)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        ti = TextInput(text=str(value), input_filter="float",
                       size_hint_x=0.65)
        row.add_widget(ti)
        py = float if isinstance(value, float) else int
        return row, ("number", ti, py)

    if isinstance(value, tuple):
        ti = TextInput(text=", ".join(map(str, value)),
                       size_hint_x=0.65)
        row.add_widget(ti)
        return row, ("tuple", ti, tuple)

    if isinstance(value, list):
        lbl = Label(text=f"[{len(value)} öğe]", size_hint_x=0.65,
                    color=(0.6, 0.6, 0.6, 1))
        row.add_widget(lbl)
        return row, ("list", lbl, list)

    if isinstance(value, dict):
        lbl = Label(text=f"{{{len(value)} anahtar}}", size_hint_x=0.65,
                    color=(0.6, 0.6, 0.6, 1))
        row.add_widget(lbl)
        return row, ("dict", lbl, dict)

    ti = TextInput(text="" if value is None else str(value),
                   size_hint_x=0.65)
    row.add_widget(ti)
    return row, ("str", ti, str)


def extract_value(field_widget: FieldWidget) -> Any:
    """Widget'tan güncel değeri okur. list/dict için None döner (dokunulmaz)."""
    kind, widget, py = field_widget
    if kind == "enum":
        return py(widget.text)
    if kind == "bool":
        return bool(widget.active)
    if kind == "number":
        try:
            return py(widget.text)
        except ValueError:
            return None
    if kind == "tuple":
        parts = [p.strip() for p in widget.text.split(",") if p.strip()]
        return tuple(
            float(p) if ("." in p or "e" in p.lower()) else int(p)
            for p in parts
        )
    if kind in ("list", "dict"):
        return None
    return widget.text


def iter_fields(obj) -> list:
    """dataclass veya __dict__'li nesne için alan listesi."""
    if dataclasses.is_dataclass(obj):
        return [(f.name, getattr(obj, f.name)) for f in dataclasses.fields(obj)]
    if hasattr(obj, "__dict__"):
        return [(k, v) for k, v in obj.__dict__.items()
                if not k.startswith("_")]
    return []
# gui/definition_editor.py
"""
Seçili definition nesnesini düzenleyen Popup.
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from gui.property_editor import make_field_widget, extract_value, iter_fields


class DefinitionEditor(BoxLayout):
    """
    obj: düzenlenecek nesne
    on_save: (obj, {field: value}) callback
    """
    def __init__(self, obj, on_save, **kw):
        super().__init__(orientation="vertical", padding=10, spacing=6, **kw)
        self.obj = obj
        self.on_save = on_save
        self.popup = None
        self.fields = {}

        scroll = ScrollView()
        form = BoxLayout(orientation="vertical", size_hint_y=None, spacing=4)
        form.bind(minimum_height=form.setter("height"))

        for name, value in iter_fields(obj):
            row, fw = make_field_widget(name, value)
            self.fields[name] = fw
            form.add_widget(row)

        scroll.add_widget(form)
        self.add_widget(scroll)

        # Alt butonlar
        btn_row = BoxLayout(size_hint_y=None, height=50, spacing=6)
        save_btn = Button(text="💾 Kaydet")
        cancel_btn = Button(text="İptal")
        save_btn.bind(on_release=self._do_save)
        cancel_btn.bind(on_release=self._do_cancel)
        btn_row.add_widget(save_btn)
        btn_row.add_widget(cancel_btn)
        self.add_widget(btn_row)

    def _do_save(self, *_):
        new_values = {}
        for name, fw in self.fields.items():
            v = extract_value(fw)
            if v is not None or fw[0] in ("str", "bool", "enum", "number", "tuple"):
                new_values[name] = v
        self.on_save(self.obj, new_values)
        if self.popup:
            self.popup.dismiss()

    def _do_cancel(self, *_):
        if self.popup:
            self.popup.dismiss()


def open_editor(obj, on_save):
    editor = DefinitionEditor(obj, on_save)
    popup = Popup(
        title=f"Düzenle: {getattr(obj, 'name', type(obj).__name__)}",
        content=editor,
        size_hint=(0.75, 0.8),
    )
    editor.popup = popup
    popup.open()
    return popup
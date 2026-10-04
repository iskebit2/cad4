# gui/project_data_panel.py
"""
ProjectDataPanel — DefinitionManager içeriğini gösterir.
Toolbar YOK. Sadece browser + detay paneli.
Ana ekrandaki 'Project Data' butonu bunu Popup içine koyar.
"""
from typing import Callable, Optional

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.properties import ObjectProperty

from domain.definition_manager import DefinitionManager
from gui.definition_browser import DefinitionBrowser
from gui.definition_editor import open_editor


class ProjectDataPanel(BoxLayout):
    """
    manager   : DefinitionManager (scene.def_mgr referansı)
    on_change : her düzenleme sonrası çağrılır (CAD yeniden çiz)
    """
    manager = ObjectProperty(None, allownone=True)

    def __init__(self,
                 manager: DefinitionManager,
                 on_change: Optional[Callable[[], None]] = None,
                 **kw):
        super().__init__(orientation="vertical", **kw)
        self.on_change = on_change or (lambda: None)
        self.manager = manager

        # --- Gövde: browser | detay ---
        body = BoxLayout(orientation="horizontal")

        self.browser = DefinitionBrowser(
            self.manager,
            on_select=self._on_select,
            on_save=self._on_editor_save,
            size_hint_x=0.45,
        )
        body.add_widget(self.browser)

        self.detail = BoxLayout(orientation="vertical", padding=8)
        self.detail.add_widget(Label(
            text="Soldaki ağaçtan bir öğe seçin",
            color=(0.6, 0.6, 0.6, 1),
        ))
        body.add_widget(self.detail)

        self.add_widget(body)

    # ------------------------------------------------------------------
    def refresh(self):
        """Dışarıdan scene değiştiğinde ağacı tazele."""
        self.browser.set_manager(self.manager)

    def _notify_change(self):
        try:
            self.on_change()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"on_change hatası: {e}")

    # ------------------------------------------------------------------
    def _on_select(self, obj):
        self.detail.clear_widgets()
        title = getattr(obj, "name", type(obj).__name__)
        self.detail.add_widget(Label(
            text=f"[b]{title}[/b]", markup=True,
            size_hint_y=None, height=30,
        ))
        self.detail.add_widget(Label(
            text=self._summarize(obj),
            size_hint_y=None, height=300,
        ))
        btn = Button(text="✎ Düzenle", size_hint_y=None, height=40)
        btn.bind(on_release=lambda *_: open_editor(obj, self._on_editor_save))
        self.detail.add_widget(btn)

    @staticmethod
    def _summarize(obj) -> str:
        from gui.property_editor import iter_fields
        lines = []
        for name, value in iter_fields(obj):
            sval = str(value)
            if len(sval) > 80:
                sval = sval[:77] + "..."
            lines.append(f"{name} = {sval}")
        return "\n".join(lines)

    def _on_editor_save(self, obj, values: dict):
        for k, v in values.items():
            if v is None and k in ("static_assignments", "items", "assignments",
                                   "points", "DOF", "Ke", "Ce", "Fixed"):
                continue
            try:
                setattr(obj, k, v)
            except Exception:
                pass
        self.browser.refresh()
        self._on_select(obj)
        self._notify_change()
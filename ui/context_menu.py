# ui/context_menu.py
from __future__ import annotations

import math
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from imgui_bundle import imgui
from app.commands import project_commands as PC
from domain.element import Area, Frame, Link, Node
from domain.line import Line
from domain.polygon import Polygon

if TYPE_CHECKING:
    from app.cad_app import CadApp


class ContextTarget(Enum):
    NONE = auto()
    ELEMENT = auto()
    VIEWPORT_EMPTY = auto()
    ACTIVE_TOOL = auto()
    WINDOW_GLOBAL = auto()


class ContextMenuManager:
    """
    imgui_bundle uyumlu, tek merkezli sağ tık bağlam menüsü.
    UIHost.render() içinde her frame self.context_menu.render() çağrılması yeterlidir.
    """

    POPUP_ID = "##cad_global_context_menu"
    DRAG_THRESHOLD_PX = 4.0

    def __init__(self, app: "CadApp") -> None:
        self.app = app
        self._open_requested = False
        self._target_type = ContextTarget.NONE
        self._target_element: Any = None
        self._rmb_press_pos: tuple[float, float] | None = None

    # ------------------------------------------------------------------
    # Otomatik Sağ Tık Algılama (Root ID Stack üzerinde)
    # ------------------------------------------------------------------
    def _poll_right_click(self) -> None:
        # Sağ tuşa basıldığı an koordinatı kaydet
        if imgui.is_mouse_clicked(imgui.MouseButton_.right):
            pos = imgui.get_mouse_pos()
            self._rmb_press_pos = (pos.x, pos.y)

        # Sağ tuş bırakıldığında sürükleme yoksa menüyü hazırla
        if imgui.is_mouse_released(imgui.MouseButton_.right) and self._rmb_press_pos is not None:
            pos = imgui.get_mouse_pos()
            dist = math.hypot(pos.x - self._rmb_press_pos[0], pos.y - self._rmb_press_pos[1])
            self._rmb_press_pos = None

            if dist >= self.DRAG_THRESHOLD_PX:
                return

            # Fare bir viewport üzerinde mi? (ViewportPanel hover güncellediyse hover.pointer doludur)
            eng = self.app.engine
            in_viewport = False
            if eng is not None and getattr(eng, "hover", None) is not None:
                in_viewport = getattr(eng.hover, "pointer", None) is not None

            if in_viewport:
                self.open_for_viewport()
            elif not imgui.is_any_item_hovered():
                self.open_for_window()

    def open_for_viewport(self) -> None:
        eng = self.app.engine
        if eng is None:
            return

        if (eng.draw_mgr and eng.draw_mgr.is_active) or (
            getattr(eng, "plane_draw_mgr", None) and eng.plane_draw_mgr.is_active
        ):
            self._target_type = ContextTarget.ACTIVE_TOOL
            self._target_element = None
            self._open_requested = True
            return

        el = getattr(eng, "hover_element", None)
        if el is None and getattr(eng, "hover_id", 0) > 0:
            el = eng._find_element(eng.hover_id)

        if el is not None:
            if eng.sel_mgr and not eng.sel_mgr.is_selected(el):
                eng.sel_mgr.select(el, additive=False)
            self._target_type = ContextTarget.ELEMENT
            self._target_element = el
        else:
            self._target_type = ContextTarget.VIEWPORT_EMPTY
            self._target_element = None

        self._open_requested = True

    def open_for_window(self) -> None:
        self._target_type = ContextTarget.WINDOW_GLOBAL
        self._target_element = None
        self._open_requested = True

    # ------------------------------------------------------------------
    # ImGui Çizim Döngüsü (UIHost.render() içinde pencere dışında çağırın)
    # ------------------------------------------------------------------
    def render(self) -> None:
        self._poll_right_click()

        if self._open_requested:
            imgui.open_popup(self.POPUP_ID)
            self._open_requested = False

        if not imgui.begin_popup(self.POPUP_ID):
            return

        try:
            if self._target_type == ContextTarget.ACTIVE_TOOL:
                self._draw_active_tool_menu()
            elif self._target_type == ContextTarget.ELEMENT:
                self._draw_element_menu(self._target_element)
            elif self._target_type == ContextTarget.VIEWPORT_EMPTY:
                self._draw_viewport_empty_menu()
            elif self._target_type == ContextTarget.WINDOW_GLOBAL:
                self._draw_window_global_menu()
        finally:
            imgui.end_popup()

    # ------------------------------------------------------------------
    # Alt Menüler (imgui_bundle: menu_item_simple kullanımı)
    # ------------------------------------------------------------------
    def _draw_active_tool_menu(self) -> None:
        eng = self.app.engine
        imgui.text_disabled("Çizim Aracı")
        imgui.separator()

        if eng and eng.draw_mgr and eng.draw_mgr.is_active:
            if imgui.menu_item_simple("Tamamla / Kapat", "Enter"):
                eng.draw_mgr.close()
            if imgui.menu_item_simple("Son Noktayı Geri Al", "Backspace"):
                if eng.draw_mgr.points:
                    eng.draw_mgr.points.pop()
            imgui.separator()
            if imgui.menu_item_simple("İptal Et", "Esc"):
                eng.draw_mgr.cancel()
        elif eng and getattr(eng, "plane_draw_mgr", None) and eng.plane_draw_mgr.is_active:
            if imgui.menu_item_simple("Düzlem Seçimini İptal Et", "Esc"):
                eng.plane_draw_mgr.cancel()

    def _draw_element_menu(self, el: Any) -> None:
        eng = self.app.engine
        selected = list(eng.sel_mgr.get_selected()) if (eng and eng.sel_mgr) else [el]
        count = len(selected)
        type_name = type(el).__name__
        uid = getattr(el, "unique_id", "?")

        header = f"{type_name} #{uid}" if count <= 1 else f"{count} Seçili Eleman ({type_name})"
        imgui.text_disabled(header)
        imgui.separator()

        if isinstance(el, Node):
            self._draw_node_actions(selected)
            imgui.separator()
        elif isinstance(el, Frame):
            if imgui.menu_item_simple("Link Elemanına Dönüştür"):
                self.app.put_command(PC.ConvertFramesToLinks())
            imgui.separator()

        if imgui.begin_menu("Hızlı Çoğalt (Replicate)"):
            if imgui.menu_item_simple("+Z Yönünde (+3.0 m)"):
                self.app.put_command(PC.ReplicateSelected(0.0, 0.0, 3.0, count=1))
            if imgui.menu_item_simple("+X Yönünde (+5.0 m)"):
                self.app.put_command(PC.ReplicateSelected(5.0, 0.0, 0.0, count=1))
            if imgui.menu_item_simple("+Y Yönünde (+5.0 m)"):
                self.app.put_command(PC.ReplicateSelected(0.0, 5.0, 0.0, count=1))
            imgui.end_menu()

        uids = [getattr(e, "unique_id", None) for e in selected if getattr(e, "unique_id", None) is not None]
        if uids:
            if imgui.menu_item_simple("Sadece Seçilileri Göster"):
                self.app.put_command(PC.ShowOnly(uids=uids))
            if imgui.menu_item_simple("Gizle"):
                self.app.put_command(PC.HideElements(uids=uids))

        imgui.separator()
        if imgui.menu_item_simple("Sil", "Del"):
            self.app.put_command(PC.DeleteSelected())

    def _draw_node_actions(self, selected: list[Any]) -> None:
        nodes = [e for e in selected if isinstance(e, Node)]
        if not nodes:
            return
        if imgui.begin_menu("Mesnet Ata (Restraint)"):
            presets = [
                ("Ankastre (Fixed)", (True, True, True, True, True, True)),
                ("Sabit Mafsal (Pinned)", (True, True, True, False, False, False)),
                ("Kayıcı Z (Roller)", (False, False, True, False, False, False)),
                ("Serbest (Free)", (False, False, False, False, False, False)),
            ]
            for label, dofs in presets:
                if imgui.menu_item_simple(label):
                    changes = {
                        "restraint.ux": dofs[0], "restraint.uy": dofs[1], "restraint.uz": dofs[2],
                        "restraint.rx": dofs[3], "restraint.ry": dofs[4], "restraint.rz": dofs[5],
                    }
                    for nd in nodes:
                        self.app.put_command(PC.UpdateElementFields(nd.unique_id, changes))
            imgui.end_menu()

    def _draw_viewport_empty_menu(self) -> None:
        imgui.text_disabled("Sahne")
        imgui.separator()

        if imgui.begin_menu("Çizim Başlat"):
            if imgui.menu_item_simple("Çizgi (Line)"):
                self.app.put_command(PC.StartDrawTool(mode="line"))
            if imgui.menu_item_simple("Poligon (Polygon)"):
                self.app.put_command(PC.StartDrawTool(mode="sequential"))
            if imgui.menu_item_simple("Dikdörtgen (Rectangle)"):
                self.app.put_command(PC.StartDrawTool(mode="rectangle"))
            imgui.end_menu()

        if imgui.begin_menu("Kamera Görünümü"):
            for label, preset in [("3D İzometrik", "3d"), ("Üst (XY)", "xy"), ("Ön (XZ)", "xz"), ("Sağ (YZ)", "yz")]:
                if imgui.menu_item_simple(label):
                    self.app.put_command(PC.SetCameraPreset(preset=preset))
            imgui.end_menu()

        imgui.separator()
        if imgui.menu_item_simple("Refresh", "R"):
            self.app.put_command(PC.RefreshGeometry())
        if imgui.menu_item_simple("Görünüme Sığdır", "F"):
            self.app.put_command(PC.FitView())
        if imgui.menu_item_simple("Tüm Modeli Göster"):
            self.app.put_command(PC.ShowEntireModel())
        if imgui.menu_item_simple("Seçimi Temizle", "Esc"):
            self.app.put_command(PC.ClearSelection())

    def _draw_window_global_menu(self) -> None:
        imgui.text_disabled("Çalışma Alanı")
        imgui.separator()

        if imgui.menu_item_simple("Geri Al (Undo)", "Ctrl+Z"):
            self.app.put_command(PC.Undo())
        if imgui.menu_item_simple("Yinele (Redo)", "Ctrl+Y"):
            self.app.put_command(PC.Redo())

        imgui.separator()
        if imgui.begin_menu("Paneller"):
            for entry in self.app.panel_registry.all():
                clicked, new_vis = imgui.menu_item(entry.title, "", entry.instance.visible)
                if clicked:
                    entry.instance.visible = new_vis
            imgui.end_menu()
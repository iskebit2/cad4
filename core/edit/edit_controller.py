# core/edit/edit_controller.py
from dataclasses import dataclass
from typing import Any, Dict
from logging_config import CadLogger

from core.commands import (
    CommandManager,
    CreateElementCommand,
    UpdateElementCommand,
    DeleteElementsCommand,
)

logger = CadLogger.get(__name__)


@dataclass
class EditResult:
    ok: bool
    element: Any = None
    message: str = ""
    created: bool = False


class EditController:
    """
    Panel ↔ Scene köprüsü.
    Tüm işlemler kendi CommandManager'ı üzerinden → undo/redo.
    Mevcut SelectionManager.undo/redo'ya DOKUNMAZ; paralel çalışır.
    """

    def __init__(self, engine, max_history: int = 100):
        self.engine = engine
        self.commands = CommandManager(max_history=max_history)
        # Her başarılı komuttan sonra renderer'ı tazele
        self.commands.add_listener(self._refresh)

    @property
    def scene(self):
        return self.engine.scene

    # ========================================================
    # CREATE
    # ========================================================

    def create(self, element_type: str, values: Dict[str, Any]) -> EditResult:
        et = element_type.lower().strip()
        factory = self._factory_for(et)
        if factory is None:
            return EditResult(False, message=f"Bilinmeyen tip: {element_type}")

        try:
            cmd = CreateElementCommand(self.scene, et, factory, values)
            if not self.commands.execute(cmd):
                return EditResult(False, message="Oluşturulamadı")
        except Exception as e:
            logger.exception(f"create({et}) hatası")
            return EditResult(False, message=str(e))

        return EditResult(
            True,
            element=cmd.created,
            created=True,
            message=f"{element_type} eklendi",
        )

    # ========================================================
    # UPDATE
    # ========================================================

    def update(self, element, new_values: Dict[str, Any]) -> EditResult:
        if element is None:
            return EditResult(False, message="Eleman yok")

        before, after = {}, {}
        for f, raw in new_values.items():
            try:
                old = self._read_field(element, f)
            except Exception:
                old = None
            if not self._is_same(old, raw):
                before[f] = old
                after[f] = raw

        if not after:
            return EditResult(True, element=element, message="Değişiklik yok")

        try:
            cmd = UpdateElementCommand(
                element=element,
                before=before,
                after=after,
                setter=self._apply_field,
            )
            if not self.commands.execute(cmd):
                return EditResult(False, element=element, message="Güncellenemedi")
        except Exception as e:
            logger.exception("update hatası")
            return EditResult(False, element=element, message=str(e))

        return EditResult(
            True, element=element,
            message=f"{len(after)} alan güncellendi",
        )

    # ========================================================
    # DELETE
    # ========================================================

    def delete(self, elements) -> EditResult:
        if not elements:
            return EditResult(False, message="Eleman yok")

        if not isinstance(elements, (list, tuple)):
            elements = [elements]

        try:
            cmd = DeleteElementsCommand(self.scene, list(elements))
            if not self.commands.execute(cmd):
                return EditResult(False, message="Silinemedi")
        except Exception as e:
            logger.exception("delete hatası")
            return EditResult(False, message=str(e))

        msg = f"{len(cmd.deleted)} silindi"
        if cmd.rejected:
            msg += f", {len(cmd.rejected)} reddedildi"
        return EditResult(True, message=msg)

    # ========================================================
    # UNDO / REDO  (bu controller'ın kendi geçmişi)
    # ========================================================

    def undo(self) -> EditResult:
        if not self.commands.can_undo():
            return EditResult(False, message="Geri alınacak işlem yok")
        ok = self.commands.undo()
        return EditResult(ok, message="Geri alındı" if ok else "Geri alınamadı")

    def redo(self) -> EditResult:
        if not self.commands.can_redo():
            return EditResult(False, message="Yinelenecek işlem yok")
        ok = self.commands.redo()
        return EditResult(ok, message="Yinelendi" if ok else "Yinelenemedi")

    # ========================================================
    # FABRİKALAR (nesne üretir, scene'e EKLEMEZ)
    # ========================================================

    def _factory_for(self, et: str):
        return {
            "node":    self._build_node,
            "frame":   self._build_frame,
            "link":    self._build_link,
            "area":    self._build_area,
            "polygon": self._build_polygon,
        }.get(et)

    def _build_node(self, v):
        from domain.element import Node
        return Node(
            x=float(v.get("x", 0.0)),
            y=float(v.get("y", 0.0)),
            z=float(v.get("z", 0.0)),
            label=v.get("label") or None,
        )

    def _build_frame(self, v):
        from domain.element import Frame
        ni = self._resolve_node(v.get("node_i_id") or v.get("node_i"))
        nj = self._resolve_node(v.get("node_j_id") or v.get("node_j"))
        if ni is None or nj is None:
            raise ValueError("Frame için iki node gerekli")
        sec = self._resolve_section(v.get("section_name"))
        return Frame(node_i=ni, node_j=nj, section=sec,
                     label=v.get("label") or None)

    def _build_link(self, v):
        from domain.element import Link
        ni = self._resolve_node(v.get("node_i_id") or v.get("node_i"))
        nj = self._resolve_node(v.get("node_j_id") or v.get("node_j"))
        if ni is None or nj is None:
            raise ValueError("Link için iki node gerekli")
        return Link(node_i=ni, node_j=nj,
                    propname=v.get("propname", ""),
                    label=v.get("label") or None)

    def _build_area(self, v):
        from domain.element import Area
        node_labels = v.get("nodes", [])
        if isinstance(node_labels, str):
            node_labels = [s.strip() for s in node_labels.split(",") if s.strip()]
        nodes = [self._resolve_node(n) for n in node_labels]
        if not nodes or any(n is None for n in nodes):
            raise ValueError("Area için tüm node'lar bulunamadı")
        return Area(nodes=nodes,
                    thickness=float(v.get("thickness", 0.0)),
                    label=v.get("label") or None)

    def _build_polygon(self, v):
        from domain.element import Polygon
        node_labels = v.get("nodes", [])
        if isinstance(node_labels, str):
            node_labels = [s.strip() for s in node_labels.split(",") if s.strip()]
        nodes = [self._resolve_node(n) for n in node_labels]
        if not nodes or any(n is None for n in nodes):
            raise ValueError("Polygon için tüm node'lar bulunamadı")
        return Polygon(nodes=nodes, label=v.get("label") or None)

    # ========================================================
    # ALAN OKU / YAZ
    # ========================================================

    def _read_field(self, element, field: str):
        if field == "node_i_id":
            return getattr(getattr(element, "node_i", None), "unique_id", None)
        if field == "node_j_id":
            return getattr(getattr(element, "node_j", None), "unique_id", None)
        if field == "section_name":
            return getattr(getattr(element, "section", None), "name", None)
        if field == "nodes":
            return [n.unique_id for n in getattr(element, "nodes", [])]

        parts = field.split(".")
        obj = element
        for p in parts[:-1]:
            obj = getattr(obj, p)
        return getattr(obj, parts[-1])

    def _apply_field(self, element, field: str, value):
        if field in ("node_i_id", "node_j_id"):
            node = self._resolve_node(value)
            if node is None:
                raise ValueError(f"{field}: node bulunamadı: {value!r}")
            attr = "node_i" if field == "node_i_id" else "node_j"
            setattr(element, attr, node)
            return

        if field == "section_name":
            element.section = self._resolve_section(value)
            return

        if field == "nodes":
            if isinstance(value, str):
                value = [s.strip() for s in value.split(",") if s.strip()]
            node_objs = [self._resolve_node(n) for n in value]
            if any(n is None for n in node_objs):
                raise ValueError("Bazı node'lar bulunamadı")
            element.nodes = node_objs
            return

        parts = field.split(".")
        obj = element
        for p in parts[:-1]:
            obj = getattr(obj, p)
        setattr(obj, parts[-1], value)

    # ========================================================
    # YARDIMCILAR
    # ========================================================

    def _resolve_node(self, ref):
        """ref: Node | unique_id (int) | label (str) | UUID (str)"""
        if ref is None:
            return None
        from domain.element import Node

        if isinstance(ref, Node):
            return ref

        scene = self.scene

        if isinstance(ref, int):
            return scene.nodes.get(ref)

        try:
            return scene.nodes.get(int(ref))
        except (ValueError, TypeError):
            pass

        for n in scene.nodes.values():
            if getattr(n, "label", None) == ref:
                return n
            if getattr(n, "element_id", None) == ref:
                return n

        return None

    def _resolve_section(self, name):
        if not name:
            return None
        scene = self.scene
        def_mgr = getattr(scene, "def_mgr", None)
        if def_mgr and hasattr(def_mgr, "get_section"):
            return def_mgr.get_section(str(name))
        if hasattr(scene, "get_section"):
            return scene.get_section(str(name))
        return None

    def _is_same(self, a, b):
        try:
            return a == b
        except Exception:
            return False

    def _refresh(self):
        try:
            self.engine.renderer.update_geo(self.engine.scene)
        except Exception:
            logger.exception("renderer.update_geo hatası")
# app/commands/replicate.py
from __future__ import annotations

from typing import Any

from app.commands.base import Command
from domain.element import Area, Frame, Link, Node
from domain.polygon import Polygon
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class ReplicateElementsCommand(Command):
    """
    Seçili elemanları (dx, dy, dz) artımla `count` kez çoğaltır.
    - execute(): İlk çalıştırmada yeni Node ve elemanları üretir; redo'da aynı
                 nesneleri restore_element ile geri koyar.
    - undo():    Üretilen elemanları (önce üst elemanlar, sonra düğümler) siler.
    """

    def __init__(
        self,
        scene,
        elements: list[Any],
        dx: float,
        dy: float,
        dz: float,
        count: int = 1,
    ) -> None:
        self.scene = scene
        self.source_elements = list(elements)
        self.dx = float(dx)
        self.dy = float(dy)
        self.dz = float(dz)
        self.count = max(1, int(count))

        # İlk execute() sonrası doldurulur; redo/undo aynı referansları kullanır
        self.created_nodes: list[Node] = []
        self.created_elements: list[Any] = []
        self._built = False

    def execute(self) -> None:
        if not self._built:
            self._build_and_add()
            self._built = True
            return

        # Redo: önce düğümleri, sonra bağlı elemanları geri koy
        for node in self.created_nodes:
            self.scene.restore_element(node)
        for el in self.created_elements:
            self.scene.restore_element(el)

    def undo(self) -> None:
        if not self._built:
            return
        # Ters sırada sil (önce Frame/Area/Polygon/Link, en son Node)
        for el in reversed(self.created_elements):
            self.scene.remove_element(el)
        for node in reversed(self.created_nodes):
            self.scene.remove_element(node)

    def _build_and_add(self) -> None:
        self.created_nodes.clear()
        self.created_elements.clear()

        # Kaynak elemanları sınıflandır
        src_nodes: dict[int, Node] = {}
        src_frames: list[Frame] = []
        src_links: list[Link] = []
        src_areas: list[Area] = []
        src_polygons: list[Polygon] = []

        for el in self.source_elements:
            if isinstance(el, Node):
                src_nodes[el.unique_id] = el
            elif isinstance(el, Frame):
                src_frames.append(el)
                if el.node_i:
                    src_nodes[el.node_i.unique_id] = el.node_i
                if el.node_j:
                    src_nodes[el.node_j.unique_id] = el.node_j
            elif isinstance(el, Link):
                src_links.append(el)
                if el.node_i:
                    src_nodes[el.node_i.unique_id] = el.node_i
                if el.node_j:
                    src_nodes[el.node_j.unique_id] = el.node_j
            elif isinstance(el, Area):
                src_areas.append(el)
                for n in el.nodes:
                    src_nodes[n.unique_id] = n
            elif isinstance(el, Polygon):
                src_polygons.append(el)
                for n in el.nodes:
                    src_nodes[n.unique_id] = n

        for step in range(1, self.count + 1):
            ox = self.dx * step
            oy = self.dy * step
            oz = self.dz * step

            # 1. Adım içi düğüm haritası (topolojik paylaşım için)
            node_map: dict[int, Node] = {}
            for uid, orig in src_nodes.items():
                new_node = Node(
                    x=orig.x + ox,
                    y=orig.y + oy,
                    z=orig.z + oz,
                    restraint=orig.restraint.copy() if getattr(orig, "restraint", None) else None,
                )
                if hasattr(orig, "color") and orig.color is not None:
                    new_node.color = list(orig.color)
                if self.scene.add_element(new_node):
                    node_map[uid] = new_node
                    self.created_nodes.append(new_node)

            # 2. Frame kopyaları
            for fr in src_frames:
                ni = node_map.get(fr.node_i.unique_id)
                nj = node_map.get(fr.node_j.unique_id)
                if ni is None or nj is None:
                    continue
                new_fr = Frame(
                    node_i=ni,
                    node_j=nj,
                    section=fr.section,
                    rotation_deg=getattr(fr, "rotation_deg", 0.0),
                )
                if hasattr(fr, "color") and fr.color is not None:
                    new_fr.color = list(fr.color)
                if self.scene.add_element(new_fr):
                    self.created_elements.append(new_fr)

            # 3. Link kopyaları
            for lk in src_links:
                ni = node_map.get(lk.node_i.unique_id)
                nj = node_map.get(lk.node_j.unique_id)
                if ni is None or nj is None:
                    continue
                new_lk = Link(
                    node_i=ni,
                    node_j=nj,
                    propname=getattr(lk, "propname", ""),
                )
                if self.scene.add_element(new_lk):
                    self.created_elements.append(new_lk)

            # 4. Area kopyaları
            for ar in src_areas:
                mapped = [node_map.get(n.unique_id) for n in ar.nodes]
                if any(m is None for m in mapped):
                    continue
                new_ar = Area(
                    nodes=mapped,
                    thickness=getattr(ar, "thickness", 0.0),
                )
                if hasattr(ar, "color") and ar.color is not None:
                    new_ar.color = list(ar.color)
                if self.scene.add_element(new_ar):
                    self.created_elements.append(new_ar)

            # 5. Polygon kopyaları
            for poly in src_polygons:
                mapped = [node_map.get(n.unique_id) for n in poly.nodes]
                if any(m is None for m in mapped):
                    continue
                new_poly = Polygon(
                    nodes=mapped,
                    poly_type=poly.poly_type,
                )
                if self.scene.add_element(new_poly):
                    self.created_elements.append(new_poly)

    @property
    def all_created(self) -> list[Any]:
        return [*self.created_nodes, *self.created_elements]

    @property
    def name(self) -> str:
        return f"Replicate({len(self.all_created)} eleman, x{self.count})"
# domain/plane_manager.py
"""
PlaneManager — Project.planes üzerinde ince operasyon katmanı.

Sorumluluk:
    - CRUD (ekle / sil / listele / isimle bul)
    - Toplu assoc yenileme
    - Toplu pending uygulama
    - Konum bazlı plane sorgulama
"""

from __future__ import annotations

from domain.plane import Plane


class PlaneManager:

    def __init__(self, project):
        self.project = project

    # ---------------- CRUD ----------------

    def add(self, plane: Plane) -> Plane:
        """Plane'i ismiyle kaydet. Aynı isim varsa üzerine yazar."""
        self.project.planes[plane.name] = plane
        return plane

    def remove(self, name: str) -> bool:
        return self.project.planes.pop(name, None) is not None

    def get(self, name: str) -> Plane | None:
        return self.project.planes.get(name)

    def all(self) -> list[Plane]:
        return list(self.project.planes.values())

    def names(self) -> list[str]:
        return sorted(self.project.planes.keys())

    def count(self) -> int:
        return len(self.project.planes)

    # ---------------- Assoc ----------------

    def refresh_all(self, scene=None):
        """Tüm plane'lerde auto-assoc'u yeniden hesapla (excluded korunur)."""
        scene = scene or self.project.scene
        for p in self.project.planes.values():
            p.refresh_assoc(scene)

    def refresh(self, name: str, scene=None) -> bool:
        scene = scene or self.project.scene
        p = self.project.planes.get(name)
        if p is None:
            return False
        p.refresh_assoc(scene)
        return True

    # ---------------- Pending ----------------

    def apply_pending_all(self, scene=None) -> dict[str, dict]:
        scene = scene or self.project.scene
        results = {}
        for name, p in self.project.planes.items():
            if p.pending:
                results[name] = p.apply_pending(scene)
        return results

    def clear_pending_all(self):
        for p in self.project.planes.values():
            p.clear_pending()

    def pending_summary(self) -> dict[str, int]:
        """Plane ismi → pending sayısı (panel/debug için)."""
        return {name: len(p.pending) for name, p in self.project.planes.items()}

    # ---------------- Konum sorguları ----------------

    def planes_containing(self, pt) -> list[Plane]:
        return [p for p in self.project.planes.values() if p.contains_pt(pt)]

    def planes_containing_band_only(self, pt) -> list[Plane]:
        return [p for p in self.project.planes.values() if p.band_contains_pt(pt)]

    # ---------------- Test / debug ----------------

    def summary(self) -> dict[str, dict]:
        """Her plane için kısa özet (log/UI için)."""
        out = {}
        for name, p in self.project.planes.items():
            out[name] = {
                "id": p.plane_id[:8],
                "depth": (p.depth_minus, p.depth_plus),
                "bounds": (p.u_min, p.u_max, p.v_min, p.v_max),
                "assoc": {k: len(v) for k, v in p.associated.items()},
                "excluded": {k: len(v) for k, v in p.excluded.items()},
                "pending": len(p.pending),
            }
        return out
# domain/plane_manager.py
"""
PlaneManager — Project.planes üzerinde ince operasyon katmanı.

Sorumluluk:
    - CRUD (ekle / sil / listele / isimle bul)
    - Benzersiz plane ID ve aktif plane yönetimi
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
        existing_by_name = self.project.planes.get(plane.name)
        existing_by_id = self.get_by_id(plane.plane_id)
        if existing_by_id is not None and existing_by_id is not existing_by_name:
            raise ValueError(f"Plane ID zaten kayıtlı: {plane.plane_id}")

        scene = self.project.scene
        if scene is not None:
            scene.refresh_plane_associations()
        if (
            existing_by_name is not None
            and existing_by_name.plane_id != plane.plane_id
            and self.project._active_plane_id == existing_by_name.plane_id
        ):
            self.project._active_plane_id = None

        self.project.planes[plane.name] = plane
        if scene is not None:
            plane.refresh_assoc(scene)
        return plane

    def remove(self, name: str) -> bool:
        plane = self.project.planes.pop(name, None)
        if plane is None:
            return False
        if self.project._active_plane_id == plane.plane_id:
            self.project._active_plane_id = None
        return True

    def get(self, name: str) -> Plane | None:
        return self.project.planes.get(name)

    def get_by_id(self, plane_id: str) -> Plane | None:
        return next(
            (plane for plane in self.project.planes.values()
             if plane.plane_id == plane_id),
            None,
        )

    def all(self) -> list[Plane]:
        return list(self.project.planes.values())

    def names(self) -> list[str]:
        return sorted(self.project.planes.keys())

    def count(self) -> int:
        return len(self.project.planes)

    # ---------------- Aktif plane ----------------

    @property
    def active_plane_id(self) -> str | None:
        plane_id = self.project._active_plane_id
        if plane_id is not None and self.get_by_id(plane_id) is None:
            self.project._active_plane_id = None
            return None
        return plane_id

    @property
    def active_plane(self) -> Plane | None:
        self.project.scene.refresh_plane_associations()
        plane_id = self.active_plane_id
        return self.get_by_id(plane_id) if plane_id is not None else None

    def activate(self, plane: str | Plane) -> Plane:
        """Activate a registered plane by name, ID, or object."""
        if isinstance(plane, Plane):
            registered = self.get_by_id(plane.plane_id)
            if registered is not plane:
                raise KeyError(f"Plane kayıtlı değil: {plane.plane_id}")
        else:
            registered = self.get(plane) or self.get_by_id(plane)
            if registered is None:
                raise KeyError(f"Plane bulunamadı: {plane}")

        self.project._active_plane_id = registered.plane_id
        return registered

    def deactivate(self) -> Plane | None:
        """Deactivate and return the previously active plane, if any."""
        active = self.active_plane
        self.project._active_plane_id = None
        return active

    # ---------------- Assoc ----------------

    def refresh_all(self, scene=None):
        """Tüm plane'lerde auto-assoc'u yeniden hesapla (excluded korunur)."""
        scene = scene or self.project.scene
        for p in self.project.planes.values():
            p.refresh_assoc(scene)
        if scene is self.project.scene:
            scene.mark_plane_associations_current()

    def refresh(self, name: str, scene=None) -> bool:
        scene = scene or self.project.scene
        scene.refresh_plane_associations()
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
        self.project.scene.refresh_plane_associations()
        out = {}
        for name, p in self.project.planes.items():
            out[name] = {
                "id": p.plane_id[:8],
                "depth": (p.depth_minus, p.depth_plus),
                "bounds": (p.u_min, p.u_max, p.v_min, p.v_max),
                "assoc": {k: len(v) for k, v in p.associated.items()},
                "association_status": p.association_counts(),
                "excluded": {k: len(v) for k, v in p.excluded.items()},
                "pending": len(p.pending),
            }
        return out
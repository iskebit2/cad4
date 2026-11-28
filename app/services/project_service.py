# app/services/project_service.py
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from core.units import UnitSystem, convert_project_units
from domain.project import Project
from logging_config import CadLogger
from tools.project_catalog import ProjectCatalog

from core.design.steel_check import (
    compute_model_geometry_hash,
    load_steel_design_results,
    save_steel_design_results,
)

if TYPE_CHECKING:
    from app.cad_app import CadApp

logger = CadLogger.get(__name__)


@dataclass
class ProjectState:
    project: Project = field(default_factory=Project)
    file_path: str | None = None
    model_text: str = "MODEL: YENİ SAHNE"


class ProjectService:
    """Proje yaşam döngüsü: yeni/aç/kaydet/değiştir + birim dönüşümü."""

    def __init__(self, app: "CadApp"):
        self.app = app
        self.state = ProjectState()
        self.catalog = ProjectCatalog(self.state.project)

    # ---- okuma ----
    @property
    def project(self) -> Project:
        return self.state.project

    @property
    def file_path(self) -> str | None:
        return self.state.file_path

    @property
    def model_text(self) -> str:
        return self.state.model_text

    # ---- yazma ----
    def replace(self, project: Project, *, path: str | None = None, model_text: str | None = None) -> None:
        if self.app.ui is not None:
            self.app.ui.reset_all()

        self.state.project = project
        self.catalog = ProjectCatalog(project)
        self.state.file_path = path
        if model_text is not None:
            self.state.model_text = model_text

        eng = self.app.engine
        if eng is not None and project.scene is not None:
            project.math_model.refresh_bounds()
            project.scene.refresh_bounds()
            eng.set_scene(project)
            eng.update_geo(project)

            if eng.grid and project.scene.grid:
                eng.grid.set_grid(project.scene.grid)
                eng.grid.mark_dirty()

            if eng.sel_mgr:
                eng.sel_mgr.clear()

            self._fit_viewports()
            eng.fit_view()

        self._notify_ui()

    def new(self) -> None:
        self.replace(Project(), path=None, model_text="MODEL: YENİ SAHNE")

    def load(self, path: str) -> None:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Proje dosyası bulunamadı: {path}")
        proj = Project.load(path)
        self._restore_sidecar_results(proj, Path(path))
        self.replace(proj, path=path,
                     model_text=f"MODEL: {os.path.basename(path)}")
        eng = self.app.engine
        if eng is not None:
            eng.fit_view()
            if eng.sel_mgr:
                eng.sel_mgr.clear()

    def save(self, path: str) -> None:
        target = Path(path)
        if target.suffix != ".cd4":
            target = target.with_suffix(".cd4")
        target_path = str(target)

        if self.state.project.steel_design_results:
            des_target = target.with_suffix(".cd4des")
            current_hash = self.state.project.steel_design_hash or compute_model_geometry_hash(self.state.project)
            saved_des = save_steel_design_results(
                des_target,
                self.state.project.steel_design_results,
                geometry_hash=current_hash,
                design_method=self.state.project.config.steel.design_method,
            )
            self.state.project.steel_design_path = saved_des.name
            self.state.project.steel_design_hash = current_hash

        self.state.project.save(target_path)
        self.state.file_path = target_path
        self.state.model_text = f"MODEL: {os.path.basename(target_path)}"

    def _restore_sidecar_results(self, proj: Project, project_path: Path) -> None:
        base_dir = project_path.parent
        des_candidate: Path | None = None
        if proj.steel_design_path:
            ref = Path(proj.steel_design_path)
            des_candidate = ref if ref.is_absolute() else (base_dir / ref)
        if des_candidate is None or not des_candidate.is_file():
            fallback = project_path.with_suffix(".cd4des")
            if fallback.is_file():
                des_candidate = fallback

        if des_candidate is not None and des_candidate.is_file():
            results, manifest = load_steel_design_results(des_candidate)
            proj.steel_design_results = results
            proj.steel_design_path = des_candidate.name
            saved_hash = manifest.get("geometry_hash")
            proj.steel_design_hash = saved_hash
            current_hash = compute_model_geometry_hash(proj)
            if saved_hash and saved_hash != current_hash:
                proj.steel_design_warning = "Geometri veya kombinasyonlar değişti; çelik tahkik sonuçları güncel değil."
            else:
                proj.steel_design_warning = None
        elif proj.steel_design_path:
            proj.steel_design_warning = f"Tahkik dosyası diskte bulunamadı: {proj.steel_design_path}"

    def save_current(self) -> bool:
        """True = kaydedildi, False = yol yok (UI dialog açmalı)."""
        if not self.state.file_path:
            return False
        self.save(self.state.file_path)
        return True

    def set_unit_system(self, unit_system: UnitSystem) -> None:
        if self.state.project.unit_system == unit_system:
            return
        convert_project_units(self.state.project, unit_system, reason="ui")
        self._refresh_engine_after_unit_change()
        self._notify_ui(unit_changed=True)

    # ---- iç yardımcılar ----
    def _fit_viewports(self) -> None:
        eng, vm = self.app.engine, self.app.viewport_manager
        if eng is None or vm is None:
            return
        get_bounds = getattr(eng, "combined_bounds", None) or getattr(eng, "_combined_bounds", None)
        if get_bounds is None:
            return
        bounds = get_bounds()
        if bounds is None:
            return
        for vp in vm.viewports.values():
            vp.camera.update_bounds(bounds.center, bounds.size)
            vp.camera.focus_on_model()

    def _refresh_engine_after_unit_change(self) -> None:
        eng = self.app.engine
        if eng is None:
            return
        p = self.state.project
        p.math_model.units = p.unit_system.value
        p.scene.units = p.unit_system.value
        p.invalidate_grid_planes()
        for el in p.math_model.all_elements.values():
            if hasattr(el, "mark_dirty"):
                el.mark_dirty()
        if eng.grid and p.grid:
            eng.grid.set_grid(p.grid)
            eng.grid.mark_dirty()
        if eng.math_model:
            eng.math_model.mark_dirty()
            eng.math_model.refresh_bounds()
        if eng.scene:
            eng.scene.mark_dirty()
            eng.scene.refresh_bounds()
        eng.update_geo(p)
        if eng.math_model:
            eng.math_model.clear_dirty()
        if self.app.viewport_manager is not None:
            self.app.viewport_manager.invalidate_all()
        self._fit_viewports()
        eng.fit_view()

    def _notify_ui(self, unit_changed: bool = False) -> None:
        ui = self.app.ui
        if ui is None:
            return
        ui.on_project_changed()
        if unit_changed:
            ui.on_unit_changed()
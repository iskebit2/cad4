# ui/load_manager_panel.py (YENİ)
"""LoadManagerPanel — tüm yük işlemleri tek pencerede, sekmeli."""

from __future__ import annotations

from imgui_bundle import imgui

from logging_config import CadLogger
from ui.base_panel import BasePanel
from domain.definition import LoadPattern

logger = CadLogger.get(__name__)

class _PatternSubPanel:
    """Load Manager → Pattern'lar sekmesi. BasePanel değil — gömülü."""

    PATTERN_TYPES = ("Dead", "Live", "Snow", "Wind", "Quake", "Other")

    def __init__(self):
        self.project = None
        self._new_name: str = ""
        self._new_type_idx: int = 0
        self._status: str = ""

    def set_context(self, ctx: dict) -> None:
        self.project = ctx.get("project")

    def draw_content(self) -> None:
        if self.project is None:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.55, 0.4, 1.0),
                "Proje bağlı değil.",
            )
            return

        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            "Load Pattern'lar",
        )
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
            "Dead, Live, Snow, Wind, Quake pattern'ları burada yönetilir.",
        )
        imgui.separator()

        self._draw_pattern_table()
        imgui.separator()
        self._draw_add_form()

        if self._status:
            imgui.separator()
            imgui.text_colored(
                imgui.ImVec4(0.55, 0.85, 0.6, 1.0),
                self._status,
            )

    # ------------------------------------------------------------------
    def _draw_pattern_table(self) -> None:
        patterns = self.project.load_patterns
        if not patterns:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Henüz pattern yok.",
            )
            return

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
        )
        if not imgui.begin_table("##lm_patterns", 5, flags):
            return

        imgui.table_setup_column("Ad", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column(
            "Tip", imgui.TableColumnFlags_.width_fixed, 100
        )
        imgui.table_setup_column(
            "self_wt", imgui.TableColumnFlags_.width_fixed, 80
        )
        imgui.table_setup_column(
            "Kullanım", imgui.TableColumnFlags_.width_fixed, 80
        )
        imgui.table_setup_column(
            "", imgui.TableColumnFlags_.width_fixed, 50
        )
        imgui.table_headers_row()

        to_delete: str | None = None
        for name, pat in sorted(patterns.items()):
            imgui.table_next_row()

            # Ad
            imgui.table_set_column_index(0)
            imgui.text(name)

            # Tip (combo)
            imgui.table_set_column_index(1)
            try:
                cur_idx = self.PATTERN_TYPES.index(
                    str(getattr(pat, "design_type", "Dead"))
                )
            except ValueError:
                cur_idx = 0
            imgui.push_item_width(-1)
            changed, new_idx = imgui.combo(
                f"##type_{name}", cur_idx, list(self.PATTERN_TYPES),
            )
            imgui.pop_item_width()
            if changed:
                pat.design_type = self.PATTERN_TYPES[new_idx]

            # self_wt_mult
            imgui.table_set_column_index(2)
            imgui.push_item_width(-1)
            _, new_mult = imgui.input_float(
                f"##mult_{name}",
                float(getattr(pat, "self_wt_mult", 0.0)),
                step=0.1, format="%.2f",
            )
            imgui.pop_item_width()
            if abs(new_mult - float(getattr(pat, "self_wt_mult", 0.0))) > 1e-9:
                pat.self_wt_mult = float(new_mult)

            # Kullanım sayısı
            imgui.table_set_column_index(3)
            count = self._count_pattern_usage(name)
            color = (
                (0.5, 0.9, 0.5, 1.0) if count > 0
                else (0.6, 0.6, 0.6, 1.0)
            )
            imgui.text_colored(
                imgui.ImVec4(*color),
                f"{count} eleman",
            )

            # Sil
            imgui.table_set_column_index(4)
            if count == 0:
                if imgui.button(f"x##del_{name}", imgui.ImVec2(30, 0)):
                    to_delete = name
                if imgui.is_item_hovered():
                    imgui.set_tooltip("Pattern'ı sil (kullanılmıyor)")
            else:
                imgui.text_colored(
                    imgui.ImVec4(0.5, 0.5, 0.5, 1.0),
                    "—",
                )

        imgui.end_table()

        if to_delete is not None:
            self.project.load_patterns.pop(to_delete, None)
            self._status = f"'{to_delete}' silindi."

    # ------------------------------------------------------------------
    def _draw_add_form(self) -> None:
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            "Yeni Pattern",
        )
        imgui.spacing()

        # Satır 1: Ad
        imgui.text("Ad")
        imgui.same_line(120)
        imgui.push_item_width(-1)
        _, self._new_name = imgui.input_text(
            "##new_name", self._new_name, 128,
        )
        imgui.pop_item_width()

        # Satır 2: Tip
        imgui.text("Tip")
        imgui.same_line(120)
        imgui.push_item_width(-1)
        _, self._new_type_idx = imgui.combo(
            "##new_type", self._new_type_idx, list(self.PATTERN_TYPES),
        )
        imgui.pop_item_width()

        # Ekle butonu
        imgui.spacing()
        can_add = bool(self._new_name.strip())
        name_clean = self._new_name.strip()
        exists = name_clean in self.project.load_patterns

        if not can_add or exists:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0),
            )

        if imgui.button("+ Pattern Ekle", imgui.ImVec2(-1, 28)) and can_add and not exists:
            self._add_pattern(name_clean, self._new_type_idx)

        if not can_add or exists:
            imgui.pop_style_color(1)

        if exists:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                f"⚠ '{name_clean}' zaten var.",
            )
        elif not can_add:
            imgui.text_colored(
                imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                "Ad gerekli.",
            )

    # ------------------------------------------------------------------
    def _add_pattern(self, name: str, type_idx: int) -> None:
        try:
            self.project.add_load_pattern(
                LoadPattern(
                    name=name,
                    design_type=self.PATTERN_TYPES[type_idx],
                    self_wt_mult=0.0,
                )
            )
            self._status = f"'{name}' eklendi ({self.PATTERN_TYPES[type_idx]})."
            logger.info(
                "[LoadManager] Pattern eklendi: %s (%s)",
                name, self.PATTERN_TYPES[type_idx],
            )
            self._new_name = ""
        except Exception:
            logger.exception("[LoadManager] Pattern ekleme hatası")
            self._status = "Pattern eklenemedi; log'a bakın."

    # ------------------------------------------------------------------
    def _count_pattern_usage(self, pattern: str) -> int:
        """Bu pattern'ı kullanan frame + node sayısı."""
        if self.project is None:
            return 0

        scene = getattr(self.project, "scene", None)
        if scene is None:
            return 0

        count = 0
        for frame in scene.frames.values():
            load_sets = getattr(frame, "dist_load_sets", None) or {}
            if pattern in load_sets:
                count += 1

        for node in scene.nodes.values():
            for pl in getattr(node, "loads", None) or []:
                if getattr(pl, "pattern_name", None) == pattern:
                    count += 1
                    break

        # Polygon yükleri
        for poly in scene.polygons.values():
            for load in getattr(poly, "assigned_loads", None) or []:
                if getattr(load, "pattern_name", None) == pattern:
                    count += 1
                    break

        return count
    
class LoadManagerPanel(BasePanel):
    """Tüm yük atama/aktarım/görüntüleme tek yerde."""

    def __init__(self):
        super().__init__(
            title="Load Manager",
            width=640,
            height=680,
            pos_first_use=(400, 80),
        )
        self.project = None
        self.scene = None

        # Alt panelleri dahil et (mevcut kodları kullan)
        from ui.load_assign_panel import LoadAssignPanel
        from ui.area_to_frame_panel import AreaToFramePanel
        from ui.frame_load_panel import FrameLoadPanel
        from ui.joint_load_panel import JointLoadPanel
        from ui.load_display_panel import LoadDisplayPanel

        self._pattern_panel = _PatternSubPanel()          # yeni
        self._assign_panel = LoadAssignPanel()            # mevcut
        self._transfer_panel = AreaToFramePanel()         # mevcut
        self._frame_load_panel = FrameLoadPanel()         # mevcut
        self._joint_load_panel = JointLoadPanel()         # mevcut
        self._display_panel = LoadDisplayPanel()          # mevcut

        self._tab = 0

    def set_context(self, ctx: dict):
        super().set_context(ctx)
        self.project = ctx.get("project")
        self.scene = ctx.get("scene")

        # Alt panelere context geçir
        for sub in (
            self._assign_panel, self._transfer_panel,
            self._frame_load_panel, self._joint_load_panel,
            self._display_panel,
        ):
            try:
                sub.app = self.app
                sub.set_context(ctx)
            except Exception:
                logger.exception(
                    "[LoadManager] %s.set_context hatası", type(sub).__name__
                )

    def draw_content(self):
        if self.project is None or self.scene is None:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.55, 0.4, 1.0),
                "Proje/sahne bağlı değil.",
            )
            return

        # Sekme çubuğu
        if imgui.begin_tab_bar("##lm_tabs"):
            if imgui.begin_tab_item("Pattern'lar")[0]:
                self._draw_patterns_tab()
                imgui.end_tab_item()

            if imgui.begin_tab_item("Alan Yükleri")[0]:
                self._draw_sub_panel(self._assign_panel)
                imgui.end_tab_item()

            if imgui.begin_tab_item("Frame'e Aktar")[0]:
                self._draw_sub_panel(self._transfer_panel)
                imgui.end_tab_item()

            if imgui.begin_tab_item("Frame Yükleri")[0]:
                self._draw_frame_loads_tab()
                imgui.end_tab_item()

            if imgui.begin_tab_item("Görüntüle")[0]:
                self._draw_sub_panel(self._display_panel)
                imgui.end_tab_item()

            imgui.end_tab_bar()

    def _draw_sub_panel(self, sub_panel):
        """Alt panelin draw_content'ini çağır."""
        try:
            sub_panel.draw_content()
        except Exception:
            logger.exception(
                "[LoadManager] %s draw hatası", type(sub_panel).__name__
            )

    def _draw_frame_loads_tab(self):
        """Frame + Joint yükleri iki sütunda."""
        # Sol: Frame load
        imgui.begin_child(
            "##lm_frame_load", imgui.ImVec2(0, 0),
            imgui.ChildFlags_.borders,
        )
        try:
            imgui.text_colored(
                imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
                "Frame Yayılı Yükler",
            )
            self._draw_sub_panel(self._frame_load_panel)
        finally:
            imgui.end_child()

    def _draw_patterns_tab(self):
        """Load pattern listesi — ekle/sil."""
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0), "Load Pattern'lar"
        )
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
            "Dead, Live, Snow, Wind pattern'ları burada yönetilir.",
        )
        imgui.separator()

        patterns = self.project.load_patterns
        if not patterns:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Henüz pattern yok.",
            )

        # Liste
        for name, pat in sorted(patterns.items()):
            imgui.bullet_text(
                f"{name} — tip: {pat.design_type}"
            )

        imgui.separator()
        # Yeni pattern
        if "_new_pattern_name" not in self.__dict__:
            self._new_pattern_name = ""
            self._new_pattern_type = "Dead"
        imgui.push_item_width(200)
        _, self._new_pattern_name = imgui.input_text(
            "##new_name", self._new_pattern_name, 128,
        )
        imgui.pop_item_width()
        imgui.same_line()
        imgui.push_item_width(120)
        _, self._new_pattern_type = imgui.combo(
            "##new_type", 0,
            ["Dead", "Live", "Snow", "Wind", "Quake", "Other"],
        )
        imgui.pop_item_width()
        imgui.same_line()
        if imgui.button("+ Ekle") and self._new_pattern_name.strip():
            from domain.definition import LoadPattern
            name = self._new_pattern_name.strip()
            if name not in patterns:
                self.project.add_load_pattern(
                    LoadPattern(
                        name=name,
                        design_type=["Dead", "Live", "Snow", "Wind",
                                     "Quake", "Other"][self._new_pattern_type],
                    )
                )
                logger.info("[LoadManager] Pattern eklendi: %s", name)
            self._new_pattern_name = ""
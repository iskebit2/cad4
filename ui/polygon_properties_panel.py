# ui/polygon_properties_panel.py
from __future__ import annotations

from imgui_bundle import imgui
from data.enums import DistType, PolygonType
from domain.polygon import Polygon
from tools.area_to_frame import AreaToFrame, AssocPreview
from structload.data.preset_loader import PresetLibrary
from ui.base_panel import BasePanel
from ui.widgets.color_picker import color_edit3
from core.units import Dimension, convert_value, UnitSystem
from domain.definition import AreaUniformLoad, LoadDirection, LoadPattern
from logging_config import CadLogger
logger = CadLogger.get(__name__)

_DEFAULT_PATTERN = {"G": ("DEAD", "Dead"), "Q": ("LIVE", "Live")}
_SOURCE_LOAD_SYSTEM = UnitSystem.KN_M
_NON_AREA_PRESET_CATEGORIES = {"hazir_kiris_senaryolari"}


class PolygonPropertiesPanel(BasePanel):
    """Viewport seçimleriyle tam entegre çalışan, tekil seçimde derinlemesine 
    Assoc/Yük/Zone yönetimi, çoklu seçimde toplu düzenleme yapabilen süper panel."""

    W = 580
    H = 700

    TYPES = ("GENERIC", "SURFACE", "ZONE", "SECTION_CUT", "LOAD_AREA")
    DIST_VALUES = (DistType.TWO_WAY, DistType.ONE_WAY_U1, DistType.ONE_WAY_U2)
    DIST_LABELS = ("Two way", "One way (U1)", "One way (U2)")

    def __init__(self):
        super().__init__(
            title="Polygon",
            width=self.W,
            height=self.H,
            pos_first_use=(900, 100),
        )
        self.app = None
        self.project = None
        self.context = None
        self.service: AreaToFrame | None = None

        self._selected_ids: set[int] = set()
        self._draft = None
        self._status: str = ""
        self._show_all_frames: bool = False

        # Batch (Çoklu seçim) state
        self._batch_type = 0
        self._batch_dist = 0
        self._batch_color = [0.8, 0.3, 0.8]

        # Yük kütüphanesi state
        self._preset_library: PresetLibrary | None = None
        self._preset_error: str | None = None
        self._categories = []
        self._category_id = ""
        self._selected_presets: set[tuple[str, int]] = set()
        self._selected_patterns = {k: v[0] for k, v in _DEFAULT_PATTERN.items()}
        self._distribution_type_index = 0
        self._distribution_types = [DistType.ONE_WAY_U1, DistType.ONE_WAY_U2, DistType.TWO_WAY]

        # Rüzgar / Zone state
        self._selected_wind_zone = None
        self._wind_cpe_index = 0
        self._cpi_positive = 0.2
        self._cpi_negative = -0.3

        # ★ Yük yönetimi state
        self._selected_pattern: str = ""          # project.load_patterns'tan
        self._selected_preset_idx: int = 0        # kategori içindeki index
        self._preset_value: float | None = None   # editbox değeri (kN/m²)
        self._load_direction: str = "GRAVITY"     # yön
        
        self._active_tab: str = "geometry"

    def set_context(self, ctx: dict):
        super().set_context(ctx)
        self.context = ctx
        self.project = ctx.get("project")
        self.service = AreaToFrame(self.project) if self.project is not None else None
        if not self._selected_pattern and self.project.load_patterns:
            self._selected_pattern = next(iter(self.project.load_patterns.keys()))

        self._load_presets()
        self._sync_pattern_choices()
        self._sync_from_selection()

    def _update_context_pick_handler(self):
        eng = self._engine()
        if eng is None or eng.input is None:
            return
        if self._is_assoc_edit_mode():
            eng.input.set_context_pick_handler(self._viewport_assoc_click)
        else:
            eng.input.set_context_pick_handler(None)
            
    def open(self, polygon: Polygon | None = None):
        super().open()
        if polygon is not None:
            self._selected_ids = {int(polygon.unique_id)}
            self._refresh([polygon])

        if not self._selected_pattern and self.project.load_patterns:
            self._selected_pattern = next(iter(self.project.load_patterns.keys()))
        self._preset_value = None   # her açılışta sıfırla
        self._load_presets()
        self._sync_pattern_choices()
        self._sync_from_selection()
        
    def close(self):
        self._clear_preview()
        eng = self._engine()
        if eng is not None and eng.input is not None:
            eng.input.set_context_pick_handler(None)
        super().close()

    def on_selection_changed(self, selected: list):
        # ★ Assoc modundaysa global seçim değişimini yut
        if self._is_assoc_edit_mode():
            return
        self._selected_ids = {
            int(e.unique_id) for e in selected
            if hasattr(e, "poly_type")
        }
        self._draft = None
        if len(self._selected_ids) == 1:
            self._sync_preview()
        else:
            self._clear_preview()
        self._refresh(selected)
        
        
    def _refresh(self, selected: list):
        # Dinamik başlık mantığı
        polys = [e for e in selected if hasattr(e, "poly_type")]
        if len(polys) == 1:
            self.set_title(f"Polygon ID: {polys[0].unique_id}")
        elif len(polys) > 1:
            self.set_title("List")
        else:
            self.set_title("Polygon")
        logger.debug("[PANEL_DEBUG] open() çağrıldı -> Panel Adresi: %s | Görünür mü: %s | Gelen Polygon: %s", 
             hex(id(self)), self.visible, selected)
        
    def _sync_from_selection(self):
        eng = getattr(self.app, "engine", None) if self.app else None
        sel = getattr(eng, "sel_mgr", None) if eng else None
        if sel:
            self._selected_ids = {
                int(e.unique_id) for e in sel.get_selected()
                if hasattr(e, "poly_type")
            }

    def _polygons(self) -> list[Polygon]:
        if not self.project or not self._selected_ids:
            return []
        return [self.project.polygons[i] for i in self._selected_ids if i in self.project.polygons]

    def _refresh_polygons(self):
        eng = getattr(self.app, "engine", None) if self.app else None
        pr = getattr(eng, "presentation_renderer", None) if eng else None
        if pr and self.project:
            pr.update_polygons(list(self.project.polygons.values()))

    # ------------------------------------------------------------------
    # YÜK KÜTÜPHANESİ YÜKLEME
    # ------------------------------------------------------------------
    def _load_presets(self):
        if self._preset_library is not None or self._preset_error:
            return
        try:
            self._preset_library = PresetLibrary()
            categories = []
            for category_id, label, load_type in self._preset_library.kategori_listesi():
                if load_type not in _DEFAULT_PATTERN or category_id in _NON_AREA_PRESET_CATEGORIES:
                    continue
                items = self._preset_library.kategori_yukleri(category_id)
                area_loads = [
                    item for item in items
                    if item.get("unit", "kN/m²") == "kN/m²" and item.get("kn") is not None
                ]
                if area_loads:
                    categories.append((category_id, label, load_type, area_loads))
            self._categories = categories
            if self._categories and self._category_id not in {c[0] for c in self._categories}:
                self._category_id = self._categories[0][0]
        except (OSError, ValueError, KeyError) as error:
            self._preset_error = str(error)
            logger.exception("[SuperPolygon] Hazır yük kütüphanesi yüklenemedi.")

    def _matching_patterns(self, load_type: str) -> list[str]:
        if self.project is None:
            return []
        target = _DEFAULT_PATTERN[load_type][1].lower()
        return sorted(
            name for name, pattern in self.project.load_patterns.items()
            if str(getattr(pattern, "design_type", "")).strip().lower() == target
        )

    def _sync_pattern_choices(self):
        for load_type, (default_name, _) in _DEFAULT_PATTERN.items():
            options = self._matching_patterns(load_type)
            if self._selected_patterns[load_type] not in options:
                self._selected_patterns[load_type] = options[0] if options else default_name

    # ------------------------------------------------------------------
    # ANA ÇİZİM DÖNGÜSÜ
    # ------------------------------------------------------------------
    def draw_content(self):
        self._update_context_pick_handler()
        self.set_status("")
        self._sync_from_selection()
        if self.project is None or self.service is None:
            self.set_status("Proje bağlı değil.")
            self._clear_preview()
            return

        items = self._polygons()
        if not items:
            self.set_status("Select a polygon")
            self._clear_preview()
            return

        if len(items) == 1:
            p = items[0]
            self._ensure_draft(p)
            self._draw_single_polygon_ui(p)
        else:
            self._clear_preview()
            self._draw_multi_polygon_ui(items)

        if self._status:
            imgui.separator()
            imgui.text_wrapped(self._status)

    def _ensure_draft(self, p: Polygon):
        if self._draft is None or self._draft.polygon_id != int(p.unique_id):
            self._draft = self.service.new_draft(p)
            
            self._sync_preview()

    # ------------------------------------------------------------------
    # TEKİL SEÇİM: SEKMELİ SÜPER PANEL
    # ------------------------------------------------------------------
    def _draw_single_polygon_ui(self, p: Polygon):
        imgui.text_colored(imgui.ImVec4(0.5, 0.85, 1.0, 1.0), f"{p.label or 'Polygon'} (id={p.unique_id})")
        imgui.separator()

        if imgui.begin_tab_bar("##super_polygon_tabs"):
            if imgui.begin_tab_item("Genel & Geometri")[0]:
                self._active_tab = "geometry"
                self._draw_tab_geometry(p)
                imgui.end_tab_item()

            if imgui.begin_tab_item("Frame Assoc")[0]:
                self._active_tab = "assoc"
                self._draw_tab_assoc(p)
                imgui.end_tab_item()

            if imgui.begin_tab_item("Yük Yönetimi")[0]:
                self._active_tab = "loads"
                self._draw_tab_loads(p)
                imgui.end_tab_item()

            if imgui.begin_tab_item("Rüzgar & Zone")[0]:
                self._active_tab = "zones"
                self._draw_tab_zones(p)
                imgui.end_tab_item()

            imgui.end_tab_bar()

    # --- SEKME 1: GEOMETRİ ---
    def _draw_tab_geometry(self, p: Polygon):
        imgui.spacing()
        cur_type_idx = self.TYPES.index(p.poly_type.name) if p.poly_type.name in self.TYPES else 0
        changed_t, new_t_idx = imgui.combo("Tip##sp_type", cur_type_idx, list(self.TYPES))
        if changed_t:
            p.poly_type = getattr(PolygonType, self.TYPES[new_t_idx])
            p.mark_dirty()
            self._refresh_polygons()

        cur_dist_idx = self.DIST_VALUES.index(p.dist_type) if p.dist_type in self.DIST_VALUES else 0
        changed_d, new_d_idx = imgui.combo("Yön##sp_dist", cur_dist_idx, list(self.DIST_LABELS))
        if changed_d:
            p.set_dist_type(self.DIST_VALUES[new_d_idx])
            self.project.math_model.mark_dirty()
            self._sync_preview()

        rgb = list(p.color[:3]) if p.color else [0.8, 0.3, 0.8]
        changed_c, new_rgb = color_edit3("Renk##sp_color", rgb)
        if changed_c:
            alpha = p.color[3] if p.color and len(p.color) > 3 else 1.0
            p.color = [*new_rgb, alpha]
            p.mark_dirty()
            self._refresh_polygons()

        imgui.spacing()
        imgui.text(f"Köşe Sayısı: {len(p.nodes)}")
        if p.excluded:
            imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0), f"Hariç tutulan: {len(p.excluded)}")

        imgui.spacing()
        if imgui.button("Plane Düzlemine Dönüştür##sp_toplane", imgui.ImVec2(-1, 0)):
            from plane.plane import Plane
            try:
                # Ekteki tool ve element yaklaşımına uygun plane üretimi
                plane = Plane.from_element(
                    p, 
                    name=f"Plane_Polygon_{p.unique_id}"
                )
            except Exception as e:
                plane = Plane.from_polygon(p) # Fallback

            eng = getattr(self.app, "engine", None)
            project = self.project

            if project is not None and plane is not None:
                if eng and hasattr(eng, "math_model"):
                    plane.fit_to_math_model(eng.math_model)
                
                project.add_plane(plane)
                project.activate_plane(plane)

                # if eng and eng.renderer:
                #     eng.renderer.update_geo(project)

                # Plane Manager paneline bildir ve aktif yap (PlaneFromElementState standardı)
                pm = self.app.panels.get("plane_manager", {}).get("instance") if self.app else None
                if pm is not None:
                    pm._selected_name = plane.name
                    pm.visible = True
                    if hasattr(pm, "_load_edit"):
                        pm._load_edit(plane, force=True)

                self._status = f"Polygon {plane.name} düzlemine aktarıldı ve aktif yapıldı."

    # --- SEKME 2: FRAME ASSOC (Viewport Karı-Koca Senkronizasyonu) ---
    def _draw_tab_assoc(self, p: Polygon):
        draft = self._draft
        if draft is None:
            return

        imgui.spacing()
        imgui.text_colored(
            imgui.ImVec4(0.3, 0.9, 0.3, 1.0),
            f"Assoc: {len(draft.associated)} | Hariç: {len(draft.excluded)}"
        )
        imgui.text_disabled("Viewport: Yeşil=assoc, Kırmızı=hariç, Gri=ilgisiz")

        if imgui.button("Auto Assoc##sp_auto", imgui.ImVec2(100, 0)):
            info = self.service.auto_assoc(p, draft, keep_excluded=True)
            self._status = f"Auto assoc: {info['added']} aday eklendi."
            self._sync_preview()

        imgui.same_line()
        if imgui.button("Apply##sp_apply", imgui.ImVec2(80, 0)) and draft.dirty:
            info = self.service.apply(p, draft)
            self._status = f"{info['associated']} frame ilişkilendirildi."
            self._sync_preview()

        imgui.same_line()
        if imgui.button("Temizle##sp_clear", imgui.ImVec2(70, 0)):
            self.service.clear_draft(draft)
            self._status = "Draft temizlendi."
            self._sync_preview()

        imgui.separator()
        frames = self.service.list_frames()
        imgui.checkbox("Tüm frame'leri göster##sp_all", self._show_all_frames)
        visible_ids = sorted(frames.keys()) if self._show_all_frames else sorted(draft.associated | draft.excluded)

        imgui.begin_child("##sp_assoc_list", imgui.ImVec2(0, 240), imgui.ChildFlags_.borders)
        if not visible_ids:
            imgui.text_disabled("Liste boş — Auto Assoc kullanın.")
        for uid in visible_ids:
            fr = frames.get(uid)
            if not fr:
                continue
            is_on = uid in draft.associated
            lbl = fr.label or f"Frame {uid}"
            changed, new_val = imgui.checkbox(f"{lbl} (id={uid})##sp_fr_{uid}", is_on)
            if changed:
                self.service.toggle(draft, uid, bool(new_val))
                self._sync_preview()
        imgui.end_child()

    # --- SEKME 3: YÜK YÖNETİMİ ---
    def _draw_tab_loads(self, p: Polygon):
        imgui.spacing()
        analysis_data = self.project.polygon_analysis_data(p)

        # ---- Atanmış yükler listesi ----
        if analysis_data and analysis_data.assigned_loads:
            imgui.text_colored(
                imgui.ImVec4(0.6, 0.85, 0.7, 1.0),
                f"Atanmış Yükler ({len(analysis_data.assigned_loads)})",
            )
            if imgui.begin_child("##sp_assigned_loads", imgui.ImVec2(0, 90),
                                imgui.ChildFlags_.borders):
                for i, load in enumerate(analysis_data.assigned_loads):
                    imgui.push_id(f"al_{i}")
                    imgui.text(f"{load.pattern_name}")
                    imgui.same_line(180)
                    imgui.text_colored(
                        imgui.ImVec4(0.7, 0.85, 0.9, 1.0),
                        f"{load.value:+.3f} {self.service.area_load_unit()}",
                    )
                    imgui.same_line(320)
                    imgui.text_disabled(f"{load.direction.value}")
                    imgui.same_line(440)
                    if imgui.small_button("X"):
                        analysis_data.assigned_loads.pop(i)
                        p.mark_dirty()
                    imgui.pop_id()
                imgui.end_child()
        else:
            imgui.text_disabled("Bu polygon üzerinde atanmış yük yok.")

        imgui.separator()

        # ---- Hazır yük kütüphanesi hatası ----
        if self._preset_error:
            imgui.text_colored(imgui.ImVec4(0.95, 0.45, 0.4, 1.0),
                            f"Hata: {self._preset_error}")
            return

        if not self._categories:
            imgui.text_disabled("Hazır yük kütüphanesi yüklenemedi.")
            return

        # ---- Pattern seçimi (project.load_patterns'tan) ----
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0),
                        "Yük Pattern")
        imgui.spacing()

        # Tüm pattern'ları listele (design_type filtresi YOK)
        pattern_names = sorted(self.project.load_patterns.keys())
        if not pattern_names:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Projede pattern yok. Önce Definitions panelinden pattern ekleyin.",
            )
            return

        current_pat = self._selected_pattern
        if current_pat not in pattern_names:
            current_pat = pattern_names[0]
            self._selected_pattern = current_pat

        pat_idx = pattern_names.index(current_pat)
        imgui.push_item_width(-1)
        changed, new_idx = imgui.combo("##sp_pattern", pat_idx, pattern_names)
        if changed:
            self._selected_pattern = pattern_names[new_idx]
        imgui.pop_item_width()

        # Pattern bilgisi
        pat = self.project.load_patterns.get(self._selected_pattern)
        if pat is not None:
            imgui.text_disabled(
                f"Tip: {getattr(pat, 'design_type', '-')} | "
                f"Kendinden ağırlık: {getattr(pat, 'self_wt_mult', 0.0):.2f}"
            )

        imgui.separator()

        # ---- Kategori seçimi ----
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Hazır Yük Kategorisi")
        imgui.spacing()

        category = next(
            (c for c in self._categories if c[0] == self._category_id),
            self._categories[0],
        )
        if imgui.begin_combo("##sp_cat", category[1]):
            for cat_id, label, _, _ in self._categories:
                if imgui.selectable(label, cat_id == self._category_id)[1]:
                    self._category_id = cat_id
                    self._selected_preset_idx = 0   # sıfırla
            imgui.end_combo()

        # ---- Hazır yük seçimi ----
        items = category[3]   # [(name, kn, ...), ...]
        if not items:
            imgui.text_disabled("Bu kategoride yük yok.")
            return

        preset_labels = [
            f"{item['name']} | {float(item['kn']):.2f} kN/m²"
            for item in items
        ]
        if self._selected_preset_idx >= len(items):
            self._selected_preset_idx = 0

        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Hazır Yük")
        imgui.spacing()
        imgui.push_item_width(-1)
        changed, new_idx = imgui.combo(
            "##sp_preset", self._selected_preset_idx, preset_labels,
        )
        if changed:
            self._selected_preset_idx = new_idx
            # ★ Editbox'ı yeni değerle güncelle
            self._preset_value = float(items[new_idx]["kn"])
        imgui.pop_item_width()

        # İlk seçimde editbox'ı doldur
        if self._preset_value is None:
            self._preset_value = float(items[self._selected_preset_idx]["kn"])

        # ---- Değer editbox ----
        imgui.spacing()
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0),
                        f"Yük Değeri ({self.service.area_load_unit()})")
        imgui.spacing()
        imgui.push_item_width(-1)
        _, self._preset_value = imgui.input_float(
            "##sp_value", self._preset_value, 0.0, 0.0, "%.3f",
        )
        imgui.pop_item_width()

        # ---- Aktarım modu ----
        imgui.spacing()
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Aktarım Modu")
        imgui.spacing()
        imgui.push_item_width(-1)
        _, self._distribution_type_index = imgui.combo(
            "##sp_dist_mode",
            self._distribution_type_index,
            [dt.value for dt in self._distribution_types],
        )
        imgui.pop_item_width()

        # ---- Yön ----
        imgui.spacing()
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Yön")
        imgui.spacing()
        directions = ["GRAVITY", "GLOBAL_Z", "GLOBAL_X", "GLOBAL_Y", "LOCAL_2"]
        cur_dir = directions.index(self._load_direction) if self._load_direction in directions else 0
        imgui.push_item_width(-1)
        changed, new_idx = imgui.combo("##sp_direction", cur_dir, directions)
        if changed:
            self._load_direction = directions[new_idx]
        imgui.pop_item_width()

        # ---- Ata butonu ----
        imgui.spacing()
        imgui.spacing()
        if imgui.button("Yükü Ata##sp_apply_load", imgui.ImVec2(-1, 32)):
            self._apply_single_load(p, analysis_data, items[self._selected_preset_idx])

        imgui.spacing()

        # ---- Frame'lere transfer ----
        if analysis_data and analysis_data.assigned_loads:
            if imgui.button("Frame'lere Yük Aktar##sp_transfer", imgui.ImVec2(-1, 32)):
                res = self.service.transfer_area_loads(p)
                self._status = res.status


    def _apply_single_load(self, polygon: Polygon, analysis_data, preset_item: dict):
        """Seçili pattern + preset + editbox değeri ile tek yük ata."""
        pat_name = self._selected_pattern
        if not pat_name:
            self._status = "Pattern seçilmedi."
            return
        if pat_name not in self.project.load_patterns:
            self._status = f"'{pat_name}' projede yok."
            return

        # ★ Değer editbox'tan geliyor, preset değil
        value_kn = float(self._preset_value)
        # kN/m² → proje birimine çevir
        val = convert_value(
            Dimension.AREA_LOAD, value_kn, _SOURCE_LOAD_SYSTEM,
            self.project.unit_system,
        )

        # Direction enum
        try:
            direction = LoadDirection(self._load_direction)
        except ValueError:
            direction = LoadDirection.GRAVITY

        load = AreaUniformLoad(
            pattern_name=pat_name,
            direction=direction,
            value=float(val),
            source_name=str(preset_item.get("name", "")),
        )
        analysis_data.assigned_loads.append(load)
        self.project.math_model.mark_dirty()
        self._status = f"'{preset_item['name']}' → {pat_name} ({value_kn:.2f} kN/m²) atandı."
        logger.debug("[PolygonPanel] load assigned: %s", load)

    def _draw_pattern_selector(self, load_type: str, label: str):
        options = self._matching_patterns(load_type)
        current = self._selected_patterns[load_type]
        display = current if options else f"{current} (oluşturulacak)"
        if imgui.begin_combo(f"{label}##pat_{load_type}", display):
            for name in options:
                if imgui.selectable(name, name == current)[1]:
                    self._selected_patterns[load_type] = name
            imgui.end_combo()

    def _apply_selected_presets(self, polygon: Polygon):
        if not self._selected_presets:
            self._status = "Atanacak hazır yük seçilmedi."
            return
        categories = {c[0]: c for c in self._categories}
        for cat_id, idx in self._selected_presets:
            cat = categories.get(cat_id)
            if not cat: continue
            item = cat[3][idx]
            load_type = cat[2]
            pat_name = self._selected_patterns[load_type]
            
            if pat_name not in self.project.load_patterns:
                self.project.add_load_pattern(LoadPattern(name=pat_name, design_type=_DEFAULT_PATTERN[load_type][1]))

            val = convert_value(Dimension.AREA_LOAD, float(item["kn"]), _SOURCE_LOAD_SYSTEM, self.project.unit_system)
            load = AreaUniformLoad(
                pattern_name=pat_name,
                direction=LoadDirection.GRAVITY,
                value=float(val),
                source_name=str(item["name"])
            )
            self.project.loads.add_area_load_transfer(
                polygon, load, analysis_data=self.project.polygon_analysis_data(polygon),
                transfer_target="frames", dist_type=self._distribution_types[self._distribution_type_index]
            )
        self.project.math_model.mark_dirty()
        self._selected_presets.clear()
        self._status = "Seçilen hazır yükler polygon'a atandı."

    # --- SEKME 4: RÜZGAR & ZONE ---
    def _draw_tab_zones(self, p: Polygon):
        imgui.spacing()

        zone_dict = p.zone_children_by_direction or {}
        if not zone_dict:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Bu polygon için rüzgar zone verisi yok.",
            )
            imgui.text_disabled(
                "Önce Wind Analysis panelinden analizi çalıştırın."
            )
            return

        # ★ show_zones_direction None ise ilk yönü kullan
        if p.show_zones_direction is None or p.show_zones_direction not in zone_dict:
            p.show_zones_direction = next(iter(zone_dict.keys()))
            p.mark_dirty()

        # ★ list_wind_zones artık zone_children_by_direction'dan çalışıyor
        entries = self.service.list_wind_zones(p)
        if not entries:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                f"'{p.show_zones_direction}' yönü için zone boş.",
            )
            return

        # ---- Yön seçimi ----
        dir_keys = sorted(zone_dict.keys())
        cur_dir_idx = (
            dir_keys.index(p.show_zones_direction)
            if p.show_zones_direction in dir_keys else 0
        )
        imgui.push_item_width(140)
        changed, new_idx = imgui.combo(
            "Yön##sp_zone_dir", cur_dir_idx, dir_keys,
        )
        imgui.pop_item_width()
        if changed:
            p.show_zones_direction = dir_keys[new_idx]
            p.mark_dirty()

        imgui.same_line()
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.85, 0.7, 1.0),
            f"{len(entries)} zone",
        )

        # ---- Zone seçimi ----
        entry_keys = [(k, i) for k, i, _ in entries]
        if self._selected_wind_zone not in entry_keys:
            self._selected_wind_zone = entry_keys[0]
        sel = next(
            (e for e in entries if (e[0], e[1]) == self._selected_wind_zone),
            entries[0],
        )
        direction_key, zone_index, zone = sel

        label = f"{direction_key} | {zone.label} ({zone_index + 1})"
        if imgui.begin_combo("Wind Zone##sp_wz", label):
            for key, idx, item in entries:
                is_sel = (key, idx) == self._selected_wind_zone
                if imgui.selectable(f"{key} | {item.label} ({idx + 1})", is_sel)[1]:
                    self._selected_wind_zone = (key, idx)
            imgui.end_combo()

        # ---- Cpe / Cpi parametreleri ----
        _, self._wind_cpe_index = imgui.combo(
            "Cpe Türü##sp_cpe", self._wind_cpe_index, ["Cpe10", "Cpe1"],
        )
        _, self._cpi_positive = imgui.input_float(
            "Cpi (+)##sp_cpip", self._cpi_positive,
        )
        _, self._cpi_negative = imgui.input_float(
            "Cpi (-)##sp_cpim", self._cpi_negative,
        )

        # ---- Mini zone tablo (Cpe override) ----
        if imgui.begin_child("##sp_zone_table", imgui.ImVec2(0, 180),
                            imgui.ChildFlags_.borders):
            flags = (
                imgui.TableFlags_.borders
                | imgui.TableFlags_.row_bg
                | imgui.TableFlags_.resizable
            )
            if imgui.begin_table("##zone_edit", 6, flags):
                imgui.table_setup_column("Bölge", imgui.TableColumnFlags_.width_fixed, 90)
                imgui.table_setup_column("Tip", imgui.TableColumnFlags_.width_fixed, 70)
                imgui.table_setup_column("cpe10", imgui.TableColumnFlags_.width_fixed, 80)
                imgui.table_setup_column("cpe1", imgui.TableColumnFlags_.width_fixed, 80)
                imgui.table_setup_column("Override", imgui.TableColumnFlags_.width_stretch, 80)
                imgui.table_setup_column("Sıfırla", imgui.TableColumnFlags_.width_fixed, 60)
                imgui.table_headers_row()

                for zi, z_dict in enumerate(zone_dict[p.show_zones_direction]):
                    imgui.table_next_row()
                    imgui.table_set_column_index(0)
                    imgui.text(str(z_dict.get("label", "")))
                    imgui.table_set_column_index(1)
                    imgui.text(str(z_dict.get("table_type", "-")))

                    cpe10 = z_dict.get("cpe10_override") or z_dict.get("cpe10", (0.0, 0.0))
                    cpe1 = z_dict.get("cpe1_override") or z_dict.get("cpe1", (0.0, 0.0))

                    imgui.table_set_column_index(2)
                    imgui.text(f"{cpe10[0]:+.2f}/{cpe10[1]:+.2f}")
                    imgui.table_set_column_index(3)
                    imgui.text(f"{cpe1[0]:+.2f}/{cpe1[1]:+.2f}")

                    imgui.table_set_column_index(4)
                    has_override = bool(
                        z_dict.get("cpe10_override") or z_dict.get("cpe1_override")
                    )
                    if has_override:
                        imgui.text_colored(
                            imgui.ImVec4(0.9, 0.7, 0.3, 1.0), "override",
                        )
                    else:
                        imgui.text_colored(
                            imgui.ImVec4(0.5, 0.5, 0.5, 1.0), "orijinal",
                        )

                    imgui.table_set_column_index(5)
                    if has_override:
                        if imgui.button(f"Sıfırla##sp_zr_{zi}"):
                            z_dict["cpe10_override"] = None
                            z_dict["cpe1_override"] = None
                            p.mark_dirty()

                imgui.end_table()
        imgui.end_child()

        # ---- Transfer butonu ----
        if imgui.button("Rüzgar Zone Aktar##sp_wind_transfer", imgui.ImVec2(-1, 0)):
            cpe_kind = "cpe10" if self._wind_cpe_index == 0 else "cpe1"
            res = self.service.transfer_wind_zone(
                p, direction_key, zone_index, zone,
                cpe_kind=cpe_kind,
                cpi_pos=self._cpi_positive,
                cpi_neg=self._cpi_negative,
            )
            self._status = res.status

    # ------------------------------------------------------------------
    # ÇOKLU SEÇİM (BATCH) ARAYÜZÜ
    # ------------------------------------------------------------------
    def _draw_multi_polygon_ui(self, items: list[Polygon]):
        imgui.text_colored(imgui.ImVec4(0.5, 0.85, 1.0, 1.0), f"{len(items)} polygon seçili (Toplu İşlem)")
        imgui.separator()

        imgui.text("Tip")
        imgui.same_line(80)
        imgui.push_item_width(-1)
        _, self._batch_type = imgui.combo("##btype", self._batch_type, list(self.TYPES))
        imgui.pop_item_width()

        imgui.text("Yön")
        imgui.same_line(80)
        imgui.push_item_width(-1)
        _, self._batch_dist = imgui.combo("##bdist", self._batch_dist, list(self.DIST_LABELS))
        imgui.pop_item_width()

        imgui.text("Renk")
        imgui.same_line(80)
        _, new_rgb = color_edit3("##bcolor", list(self._batch_color))
        self._batch_color = list(new_rgb)

        imgui.spacing()
        if imgui.button("Tümüne Uygula##batch_apply", imgui.ImVec2(-1, 30)):
            poly_type = getattr(PolygonType, self.TYPES[self._batch_type])
            dist_type = self.DIST_VALUES[self._batch_dist]
            color = [*self._batch_color, 1.0]
            for p in items:
                p.poly_type = poly_type
                p.set_dist_type(dist_type)
                p.color = color
                p.mark_dirty()
            self.project.math_model.mark_dirty()
            self._refresh_polygons()
            self._status = f"{len(items)} polygon toplu olarak güncellendi."

        imgui.spacing()
        total_nodes = sum(len(p.nodes) for p in items)
        total_assoc = sum(len(p.associated) for p in items)
        imgui.text(f"Toplam Köşe: {total_nodes}   |   Toplam Assoc: {total_assoc}")

    # ------------------------------------------------------------------
    # VIEWPORT PREVIEW SENKRONİZASYONU
    # ------------------------------------------------------------------
    def _engine(self):
        return getattr(self.app, "engine", None) if self.app else None

    def _sync_preview(self):
        eng = self._engine()
        renderer = getattr(eng, "renderer", None) if eng else None
        if renderer is None or not self._draft:
            if renderer is not None:
                renderer.set_assoc_preview(None)
            return
        preview = AssocPreview(
            polygon_id=self._draft.polygon_id,
            associated=set(self._draft.associated),
            excluded=set(self._draft.excluded),
            active=True,
        )
        renderer.set_assoc_preview(preview)

    def _is_assoc_edit_mode(self) -> bool:
        return (
            self.visible
            and self._active_tab == "assoc"
            and self._draft is not None
        )

    def _viewport_assoc_click(self, x, y, button) -> bool:
        """Panel assoc modunda viewport tıklaması → frame toggle."""
        if button != 0:
            return False
        eng = self._engine()
        if eng is None or self._draft is None:
            return False
        vp = getattr(eng.viewport_manager, "active", None) if eng.viewport_manager else None
        if vp is None:
            return False
        pick_pass = getattr(eng.renderer, "pick_pass", None)
        if pick_pass is None:
            return False
        # ★ Senkron neighborhood pick
        el = vp.pick_at_neighborhood(pick_pass, int(x), int(y), radius=3)
        if el is None:
            return False
        # Sadece Frame/Link
        from domain.element import Frame, Link
        if not isinstance(el, (Frame, Link)):
            return False
        uid = int(el.unique_id)
        is_on = uid in self._draft.associated
        self.service.toggle(self._draft, uid, not is_on)
        self._sync_preview()
        return True

    def _clear_preview(self):
        eng = self._engine()
        renderer = getattr(eng, "renderer", None) if eng else None
        if renderer is not None:
            renderer.set_assoc_preview(None)
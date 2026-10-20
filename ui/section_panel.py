# ui/section_panel.py
"""
Kesit tanımları paneli.
- Listeleme + arama
- Yeni / Kopyala / Sil
- Tip bazlı parametre editörü
- Otomatik A, I33, I22, J hesabı
- Kullanan çubuk sayısı gösterimi
"""
from typing import Optional, Dict
import imgui

from domain.definition import Section
from data.enums import SectionType
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class SectionPanel:
    def __init__(self):
        self.visible = False
        self.app = None
        self._search = ""
        self._selected_name: Optional[str] = None
        self._draft: Optional[Section] = None     # düzenlenen kopya
        self._dirty = False

    def open(self):   self.visible = True
    def close(self):  self.visible = False

    # ---------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return
        imgui.set_next_window_size(900, 600, imgui.FIRST_USE_EVER)
        expanded, opened = imgui.begin("Kesit Yönetimi", True)
        if not opened:
            self.close()
            imgui.end()
            return

        project = getattr(self.app, "current_project", None)
        if project is None:
            imgui.text_colored("Proje yok.", 1, 0.5, 0.5)
            imgui.end()
            return

        self._draw_toolbar(project)
        imgui.separator()

        imgui.columns(2, "section_cols", border=True)
        self._draw_list(project)
        imgui.next_column()
        self._draw_editor(project)
        imgui.columns(1)

        imgui.end()

    # ---------------------------------------------------------------
    def _draw_toolbar(self, project):
        if imgui.button("+ Yeni"):
            self._create_new(project)
        imgui.same_line()
        if imgui.button("Kopyala") and self._selected_name:
            self._duplicate(project)
        imgui.same_line()
        if imgui.button("Sil") and self._selected_name:
            self._delete(project)
        imgui.same_line()
        imgui.set_next_item_width(200)
        _, self._search = imgui.input_text("Arama", self._search)

    # ---------------------------------------------------------------
    def _draw_list(self, project):
        imgui.text(f"Toplam: {len(project.sections)} kesit")
        imgui.begin_child("section_list", 0, 0, border=True)
        search = self._search.lower()
        for name, sec in sorted(project.sections.items()):
            if search and search not in name.lower():
                continue
            is_sel = (name == self._selected_name)
            clicked, _ = imgui.selectable(
                f"{sec.profile_type.value:<8} {name}",
                is_sel,
            )
            if clicked:
                self._selected_name = name
                self._draft = self._clone(sec)
                self._dirty = False
        imgui.end_child()

    # ---------------------------------------------------------------
    def _draw_editor(self, project):
        if not self._draft:
            imgui.text_disabled("Soldan bir kesit seçin.")
            return

        d = self._draft

        # İsim
        imgui.set_next_item_width(300)
        changed, new_name = imgui.input_text("İsim", d.name)
        if changed:
            d.name = new_name
            self._dirty = True

        # Tip
        imgui.set_next_item_width(200)
        current_type = d.profile_type
        if imgui.begin_combo("Tip", current_type.value):
            for st in SectionType:
                is_sel = (st == current_type)
                clicked, _ = imgui.selectable(st.value, is_sel)
                if clicked:
                    d.profile_type = st
                    self._dirty = True
            imgui.end_combo()

        # Malzeme
        mat_names = list(project.materials.keys()) or ["<yok>"]
        current_mat = d.material.name if d.material else mat_names[0]
        imgui.set_next_item_width(200)
        if imgui.begin_combo("Malzeme", current_mat):
            for mname in mat_names:
                clicked, _ = imgui.selectable(mname, mname == current_mat)
                if clicked:
                    d.material = project.materials.get(mname)
                    self._dirty = True
            imgui.end_combo()

        imgui.separator()
        imgui.text_colored("Profil Parametreleri (mm)", 0.7, 0.9, 0.7)
        self._draw_profile_params(d)

        imgui.separator()
        self._draw_computed_values(d)

        # Kullanan çubuk sayısı
        used = sum(1 for f in project.scene.frames.values()
                   if f.section and f.section.name == self._selected_name)
        imgui.text_colored(f"Kullanan çubuk: {used}", 0.7, 0.8, 1.0)

        imgui.separator()
        if imgui.button("Uygula", width=120) and self._dirty:
            self._apply(project)
        imgui.same_line()
        if imgui.button("İptal", width=120):
            self._draft = None
            self._dirty = False

    # ---------------------------------------------------------------
    def _draw_profile_params(self, d):
        """Tip bazlı parametre editörü."""
        params = d.profile_params
        if d.profile_type == SectionType.RECT:
            self._float_field(params, "h", "Yükseklik h")
            self._float_field(params, "b", "Genişlik b")
        elif d.profile_type == SectionType.CIRCLE:
            self._float_field(params, "d", "Çap d")
        elif d.profile_type == SectionType.PIPE:
            self._float_field(params, "d", "Dış çap")
            self._float_field(params, "t", "Kalınlık")
        elif d.profile_type == SectionType.BOX:
            self._float_field(params, "h", "Yükseklik")
            self._float_field(params, "b", "Genişlik")
            self._float_field(params, "t", "Kalınlık")
        elif d.profile_type == SectionType.I:
            self._float_field(params, "h", "Yükseklik")
            self._float_field(params, "b", "Başlık genişliği")
            self._float_field(params, "tw", "Gövde kalınlığı")
            self._float_field(params, "tf", "Başlık kalınlığı")
        elif d.profile_type == SectionType.C:
            self._float_field(params, "h", "Yükseklik")
            self._float_field(params, "b", "Kanat genişliği")
            self._float_field(params, "tw", "Gövde kalınlığı")
            self._float_field(params, "tf", "Kanat kalınlığı")
        elif d.profile_type == SectionType.L:
            self._float_field(params, "h", "Bacak 1")
            self._float_field(params, "b", "Bacak 2")
            self._float_field(params, "t", "Kalınlık")
        elif d.profile_type == SectionType.T:
            self._float_field(params, "h", "Yükseklik")
            self._float_field(params, "b", "Başlık genişliği")
            self._float_field(params, "tw", "Gövde kalınlığı")
            self._float_field(params, "tf", "Başlık kalınlığı")
        elif d.profile_type == SectionType.TUBE:
            self._float_field(params, "h", "Yükseklik")
            self._float_field(params, "b", "Genişlik")
            self._float_field(params, "t", "Kalınlık")
        elif d.profile_type == SectionType.CHANNEL:
            self._float_field(params, "h", "Yükseklik")
            self._float_field(params, "b", "Kanat genişliği")
            self._float_field(params, "tw", "Gövde kalınlığı")
            self._float_field(params, "tf", "Kanat kalınlığı")
        else:
            imgui.text_disabled(f"{d.profile_type.value} — manuel parametre editörü henüz yok")

    # ---------------------------------------------------------------
    def _draw_computed_values(self, d):
        A, I33, I22, J = self._compute_section_props(d)
        imgui.text_colored("Hesaplanan:", 0.7, 0.9, 0.7)
        imgui.bullet_text(f"A   = {A:,.2f} mm²")
        imgui.bullet_text(f"I33 = {I33:.4e} mm⁴")
        imgui.bullet_text(f"I22 = {I22:.4e} mm⁴")
        imgui.bullet_text(f"J   = {J:.4e} mm⁴")

    # ---------------------------------------------------------------
    def _compute_section_props(self, d):
        """Tip bazlı kesit özellikleri hesabı. Draft değiştikçe canlı güncellenir."""
        p = d.profile_params
        try:
            if d.profile_type == SectionType.RECT:
                h, b = float(p.get("h", 0)), float(p.get("b", 0))
                A = h * b
                I33 = b * h**3 / 12
                I22 = h * b**3 / 12
                J = I33 + I22  # yaklaşık
                return A, I33, I22, J
            if d.profile_type == SectionType.CIRCLE:
                r = float(p.get("d", 0)) / 2
                A = 3.141592653589793 * r**2
                I = 3.141592653589793 * r**4 / 4
                return A, I, I, 2 * I
            if d.profile_type == SectionType.PIPE:
                D, t = float(p.get("d", 0)), float(p.get("t", 0))
                r, ri = D/2, D/2 - t
                A = 3.141592653589793 * (r**2 - ri**2)
                I = 3.141592653589793 * (r**4 - ri**4) / 4
                return A, I, I, 2 * I
            # ... diğer tipler ...
        except Exception:
            pass
        return 0.0, 0.0, 0.0, 0.0

    # ---------------------------------------------------------------
    def _float_field(self, params, key, label):
        val = float(params.get(key, 0.0))
        imgui.set_next_item_width(200)
        changed, new_val = imgui.input_float(label, val, 1.0, 10.0)
        if changed:
            params[key] = new_val
            self._dirty = True

    # ---------------------------------------------------------------
    def _create_new(self, project):
        base_name = "YENI_KESIT"
        name = base_name
        i = 1
        while name in project.sections:
            name = f"{base_name}_{i}"
            i += 1
        sec = Section(
            name=name,
            profile_type=SectionType.RECT,
            profile_params={"h": 300.0, "b": 600.0},
            material=next(iter(project.materials.values()), None),
        )
        project.sections[name] = sec
        self._selected_name = name
        self._draft = self._clone(sec)
        self._dirty = False

    def _duplicate(self, project):
        src = project.sections.get(self._selected_name)
        if not src:
            return
        base_name = f"{src.name}_copy"
        name = base_name
        i = 1
        while name in project.sections:
            name = f"{base_name}_{i}"
            i += 1
        dup = self._clone(src)
        dup.name = name
        project.sections[name] = dup
        self._selected_name = name
        self._draft = self._clone(dup)
        self._dirty = False

    def _delete(self, project):
        if self._selected_name and self._selected_name in project.sections:
            del project.sections[self._selected_name]
            self._selected_name = None
            self._draft = None
            self._dirty = False

    def _clone(self, sec: Section) -> Section:
        return Section(
            name=sec.name,
            profile_type=sec.profile_type,
            profile_params=dict(sec.profile_params),
            material=sec.material,
            color=tuple(sec.color),
        )

    def _apply(self, project):
        if not self._draft:
            return
        project.sections[self._draft.name] = self._draft
        # Sahneyi işaretle — renderer güncellensin
        if project.scene:
            project.scene.mark_dirty()
            if self.app and self.app.engine and self.app.engine.renderer:
                self.app.engine.renderer.update_geo(project.scene)
        self._dirty = False
        logger.info(f"[SectionPanel] Kaydedildi: {self._draft.name}")
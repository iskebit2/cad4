"""
InspectorController — scene ve seçim arasındaki tek köprü.

Sorumluluk:
  - scene referansını tut
  - set_selection(elements)  -> SelectionModel doldur
  - apply()                  -> current values'ı element'lere yaz, scene.mark_dirty()
  - cancel()                 -> current values'ı original'a döndür

UI çizmez, imgui bilmez. Sadece iş mantığı.
"""


from domain.element import Node
from inspector.schema_bridge import (
    MIXED,
    element_to_values,
    elements_to_common_values,
    multi_schema_for,
    schema_for,
    values_to_element,
)
from inspector.selection import SelectionModel
from logging_config import CadLogger

logger = CadLogger.get(__name__)

_IGNORE_KEYS = {"section_info", "material_info", "link_prop_info"}


def _attach_catalog(schema, catalog, element):
    """Her field'a 'catalog' bağlamı ekle. Widget'lar buradan okuyacak."""
    for group in schema:
        for f in group.fields:
            # enum + "section"/"material"/"link_prop" türü alanlar için
            if f.kind == "enum" and f.key.endswith("section") and catalog:
                choices = catalog.list_sections()
                if choices:
                    f.choices = choices
            elif f.kind == "enum" and f.key.endswith("material") and catalog:
                f.choices = catalog.list_materials()
            elif f.kind == "enum" and f.key.endswith("propname") and catalog:
                f.choices = catalog.list_link_props()
    return schema

class InspectorController:

    def __init__(self, scene=None, catalog=None):
        self.scene = scene
        self.catalog = catalog
        self.selection = SelectionModel()
        self.schema = []
        self.filter_type: str | None = None
        self.filter_assoc_only = None

    @property
    def filtered_elements(self):
        if not self.selection.elements:
            return []

        elements = list(self.selection.elements)

        # Assoc filtresi
        if self.filter_assoc_only is not None:
            elements = [e for e in elements
                        if self._element_in_plane_assoc(e, self.filter_assoc_only)]

        # Tip filtresi
        if self.filter_type is not None:
            elements = [e for e in elements
                        if getattr(e, "element_type", None) == self.filter_type]

        return elements

    def set_filter_assoc_only(self, plane):
        """Plane assoc filtresini değiştir."""
        if self.filter_assoc_only is plane:
            return
        self.filter_assoc_only = plane
        # Mevcut seçimi yeniden kur
        self._rebuild_from_filter()

    def _rebuild_from_filter(self):
        """Filtre değişince selection modeli yeniden kur."""
        filtered = self.filtered_elements
        if not filtered:
            self.clear()
            return
        if len(filtered) == 1:
            el = filtered[0]
            self.schema = schema_for(getattr(el, "element_type", "Node"))
            vals = element_to_values(el)
            self._normalize_values(vals, el)
            self.selection.set_single(el, vals)
        else:
            self.schema = multi_schema_for(filtered)
            vals = elements_to_common_values(filtered)
            self._normalize_values_multi(vals, filtered)
            self.selection.set_multi(filtered, vals)

    def set_filter_type(self, type_name):
        if self.filter_type == type_name:
            return
        self.filter_type = type_name
        self._rebuild_from_filter()

    def selection_counts_by_type(self) -> dict[str, int]:
        """Seçimdeki her tipten kaç tane var."""
        counts = {}
        for e in self.selection.elements:
            t = getattr(e, "element_type", "?")
            counts[t] = counts.get(t, 0) + 1
        return counts

    # ==================================================================
    # Seçim
    # ==================================================================
    def set_selection(self, elements):
        elements = list(elements or [])
        if not elements:
            self.clear()
            return

        if len(elements) == 1:
            el = elements[0]
            self.schema = schema_for(getattr(el, "element_type", "Node"))
            vals = element_to_values(el)
            vals = self._normalize_values(vals, el)   # ← YENİ
            self.selection.set_single(el, vals)
        else:
            self.schema = multi_schema_for(elements)
            vals = elements_to_common_values(elements)
            vals = self._normalize_values_multi(vals, elements)   # ← YENİ
            self.selection.set_multi(elements, vals)


    def _normalize_values(self, vals, element):
        """Serialized 'section'/'material' alanlarını gerçek nesneye çevir."""
        if not isinstance(vals, dict):
            return vals

        # section → Section nesnesi
        if "section" in vals and not hasattr(vals["section"], "name"):
            sec = getattr(element, "section", None)
            if sec is not None and hasattr(sec, "name"):
                vals["section"] = sec

        # material → Material nesnesi
        if "material" in vals and not hasattr(vals["material"], "name"):
            mat = getattr(element, "material", None)
            if mat is not None and hasattr(mat, "name"):
                vals["material"] = mat

        return vals


    def _normalize_values_multi(self, vals, elements):
        """Çoklu seçimde her elemandan gerçek nesneyi al."""
        if not isinstance(vals, dict):
            return vals
        for key in ("section", "material"):
            if key in vals and not hasattr(vals[key], "name"):
                # İlk elemanda nesne varsa onu kullan
                for el in elements:
                    obj = getattr(el, key, None)
                    if obj is not None and hasattr(obj, "name"):
                        vals[key] = obj
                        break
        return vals

    def clear(self):
        self.selection.clear()
        self.schema = []

    def refresh_from_scene(self):
        scn = getattr(self, "scene", None)
        if scn is None:
            self.clear()
            return

        # Seçim boşsa hiçbir şey yapma yerine — filtre ve seçim yeniden kur
        if self.selection.is_empty:
            # Ama schema da boş; sadece dirty flag temizle
            return

        # Seçim varsa yeniden kur (mevcut davranış)
        self.set_selection(self.selection.elements)

    # ==================================================================
    # Düzenleme yaşam döngüsü
    # ==================================================================
    def apply(self) -> bool:

        if self.selection.is_empty:
            return False
        values = self._sanitize(self.selection.values)

        # ↓ Katalog alanlarını gerçek nesneye çevir
        values = self._resolve_catalog_refs(values)

        if not values:
            return False
        try:
            if self.selection.is_single:
                values_to_element(self.selection.primary, values)
            else:
                for el in self.selection.elements:
                    values_to_element(el, values)


            scene = self.scene
            if scene is not None:
                for el in self.selection.elements:
                    if isinstance(el, Node):
                        scene.mark_dirty_from_node(el)
            # ---------------------------------------------------

            self.selection.original = _copy(self.selection.values)
            self._notify_scene_changed()
            return True
        
        except Exception:
            logger.exception("Inspector apply hatası")
            return False

    def cancel(self):
        """Cancel — current values'ı original'a geri al."""
        self.selection.reset_to_original()
        

    def _notify_scene_changed(self):
        s = self.scene
        if s is None:
            return
        mark = getattr(s, "mark_dirty", None)
        if callable(mark):
            mark()
        else:
            # fallback: alan adı bilinen ise direkt set et
            try:
                s._is_dirty = True
            except Exception:
                logger.warning("scene dirty API yok — renderer güncellenmeyebilir")

    def _resolve_catalog_refs(self, values):
        """'section' → Section nesnesi, 'material' → Material nesnesi, ..."""
        if self.catalog is None:
            return values
        out = dict(values)

        sec_name = out.get("section")
        if isinstance(sec_name, str) and sec_name:
            sec = self.catalog.get_section(sec_name)
            if sec is not None:
                out["section"] = sec

        mat_name = out.get("material")
        if isinstance(mat_name, str) and mat_name:
            mat = self.catalog.get_material(mat_name)
            if mat is not None:
                out["material"] = mat

        return out

    # ==================================================================
    # Yardımcı
    # ==================================================================
    def _sanitize(self, d):
        """MIXED sentinel'lerini payload'dan çıkar."""
        if isinstance(d, dict):
            return {k: self._sanitize(v) for k, v in d.items()
                if v != MIXED and k not in _IGNORE_KEYS}
        if isinstance(d, list):
            return [self._sanitize(v) for v in d]
        return d

    def _element_in_plane_assoc(self, el, plane) -> bool:
        if plane is None:
            return True
        kind_map = {
            "Node": "node", "Frame": "frame", "Area": "area",
            "Link": "link", "Polygon": "poly",
        }
        kind = kind_map.get(getattr(el, "element_type", ""), None)
        if kind is None:
            return False
        uid = getattr(el, "unique_id", None)
        if uid is None:
            return False
        return uid in plane.associated.get(kind, set())

    def list_planes(self):
        """Projedeki tüm plane'ler (dropdown için)."""
        if self.catalog is None:
            return []
        if hasattr(self.catalog, "list_planes"):
            return self.catalog.list_planes()
        project = getattr(self.catalog, "project", None)
        if project is not None:
            return sorted(project.planes.values(), key=lambda p: p.name)
        return []

# ----------------------------------------------------------------------
def _copy(d):
    if isinstance(d, dict):
        return {k: _copy(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_copy(v) for v in d]
    return d
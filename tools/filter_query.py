# tools/filter_query.py
from __future__ import annotations
import math
import fnmatch
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class ElementFilterQuery:
    # Metin / Kimlik bazlı filtreler (Regex veya içerir desteği ile)
    name_pattern: str | None = None          # Örn: "COL*", "B*"
    element_types: set[str] = field(default_factory=set)  # {"Frame", "Area", "Node", "Link", "Polygon"}
    
    # Frame / Kesit / Malzeme bazlı filtreler
    sections: set[str] = field(default_factory=set)       # Örn: {"IPE300", "HEB200"}
    materials: set[str] = field(default_factory=set)      # Örn: {"S235", "C30"}
    
    # Sınıflandırma (Kolon / Kiriş / Diagonal ayrımı için özel etiket veya geometri filtresi)
    structural_subtypes: set[str] = field(default_factory=set)  # {"column", "beam", "brace"}
    
    # Polygon / Area özel özellikleri
    polygon_types: set[Any] = field(default_factory=set)  # Örn: {PolygonType.GENERIC, ...}
    dist_types: set[Any] = field(default_factory=set)     # Örn: {DistType.ONE_WAY, DistType.TWO_WAY}
    
    # Özel Lambda / Fonksiyonel filtre (İleri düzey kullanıcı tanımlı filtreler için)
    custom_predicate: Callable[[Any], bool] | None = None

    def is_empty(self) -> bool:
        """Filtre hiçbir kural içermiyor mu? (boşsa hiçbir şey filtreleme)"""
        return not any((
            self.name_pattern, self.element_types, self.sections,
            self.materials, self.structural_subtypes, self.polygon_types,
            self.dist_types, self.custom_predicate,
        ))


_frame_subtype_cache: dict[str, str] = {}

def classify_frame_subtype(frame) -> str:
    uid = getattr(frame, "unique_id", None)
    if uid and uid in _frame_subtype_cache:
        return _frame_subtype_cache[uid]
    
    if not frame.node_i or not frame.node_j:
        return "unknown"
    dx = frame.node_j.x - frame.node_i.x
    dy = frame.node_j.y - frame.node_i.y
    dz = frame.node_j.z - frame.node_i.z
    length = math.hypot(dx, dy, dz)
    if length < 1e-9:
        return "unknown"
    cos_z = abs(dz / length)
    if cos_z > 0.95:
        result = "column"
    elif cos_z < 0.05:
        result = "beam"
    else:
        result = "brace"
    if uid:
        _frame_subtype_cache[uid] = result
    return result


class ModelFilterEngine:
    @staticmethod
    def evaluate_element(element, query: ElementFilterQuery) -> bool:
        if query.is_empty():
            return True   # boş filtre → her şey geçer
        
        e_type = getattr(element, "element_type", type(element).__name__)
        if query.element_types and e_type not in query.element_types:
            return False
        
        if query.name_pattern:
            if not fnmatch.fnmatch(str(getattr(element, "label", "")), query.name_pattern):
                return False
        
        if e_type == "Frame":
            sec = getattr(element, "section", None)
            sec_name = getattr(sec, "name", str(sec)) if sec else ""
            if query.sections and sec_name not in query.sections:
                return False
            
            mat = getattr(sec, "material", None) if sec else None
            mat_name = getattr(mat, "name", str(mat)) if mat else ""
            if query.materials and mat_name not in query.materials:
                return False
            
            if query.structural_subtypes:
                sub = classify_frame_subtype(element)
                if sub not in query.structural_subtypes:
                    return False
        
        if e_type == "Polygon":
            if query.polygon_types and getattr(element, "poly_type", None) not in query.polygon_types:
                return False
            if query.dist_types and getattr(element, "dist_type", None) not in query.dist_types:
                return False
        
        if query.custom_predicate and not query.custom_predicate(element):
            return False
        return True

    # ★ YENİ: ID set'i döndür
    @classmethod
    def filter_to_ids(cls, math_model, query: ElementFilterQuery) -> frozenset[int]:
        """Filtreye uyan tüm element ID'lerini döndür."""
        if query.is_empty():
            return frozenset()   # boş → kısıtlama yok
        ids = set()
        for coll in (math_model.nodes, math_model.frames, math_model.areas,
                     math_model.links, math_model.polygons, math_model.lines):
            for el in coll.values():
                if cls.evaluate_element(el, query):
                    ids.add(el.unique_id)
        return frozenset(ids)

    # Eski API korunuyor (raporlama için)
    @classmethod
    def filter_project_elements(cls, math_model, query):
        results = {"nodes": [], "frames": [], "areas": [],
                   "links": [], "polygons": [], "lines": []}
        collections = {
            "nodes": math_model.nodes.values(),
            "frames": math_model.frames.values(),
            "areas": math_model.areas.values(),
            "links": math_model.links.values(),
            "polygons": math_model.polygons.values(),
            "lines": math_model.lines.values(),
        }
        for key, items in collections.items():
            for item in items:
                if cls.evaluate_element(item, query):
                    results[key].append(item)
        return results
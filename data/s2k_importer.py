# data/s2k_importer.py
"""
SAP2000 .s2k dosyası içe aktarıcı.
TABLE bloklarını ayrıştırıp DefinitionManager'a yazar.
"""
import re
from typing import Dict, List

from domain import definition as D
from domain.definition import (
    Material, MatType, LoadPattern, LoadCase, LoadCombination, ComboItem,
    StaticLoadAssignment, Section, SectionType,
)
from domain.definition_manager import DefinitionManager


class S2KParser:
    def __init__(self, path: str):
        self.path = path
        self.tables: Dict[str, List[Dict[str, str]]] = {}
        self._parse()

    def _parse(self):
        current_table = None
        with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n")
                m = re.match(r'^\s*TABLE:\s*"(.+?)"\s*$', line)
                if m:
                    current_table = m.group(1)
                    self.tables.setdefault(current_table, [])
                    continue
                if current_table and line.strip():
                    row = self._parse_kv(line)
                    if row:
                        self.tables[current_table].append(row)

    @staticmethod
    def _parse_kv(line: str) -> Dict[str, str]:
        pattern = r'(\w+)\s*=\s*(".*?"|\S+)'
        return {k: v.strip('"') for k, v in re.findall(pattern, line)}

    # ------------------------------------------------------------------
    def import_to(self, mgr: DefinitionManager):
        self._import_materials(mgr)
        self._import_sections(mgr)
        self._import_load_patterns(mgr)
        self._import_load_cases(mgr)
        self._import_combinations(mgr)

    def _import_materials(self, mgr):
        for tbl in ("MATERIAL PROPERTIES 01 - GENERAL",
                    "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"):
            for row in self.tables.get(tbl, []):
                name = row.get("Material") or row.get("MatName")
                if not name or mgr.get_material_by_name(name):
                    continue
                mat = Material(name=name)
                t = (row.get("Type") or "").lower()
                if "concrete" in t:
                    mat.mat_type = MatType.CONCRETE
                for k, attr in (("E1", "E1"), ("G12", "G12"),
                                ("U12", "nu12"), ("UnitMass", "density")):
                    if k in row and _num(row[k]):
                        setattr(mat, attr, float(row[k]))
                mgr.add_material(mat)

    def _import_sections(self, mgr):
        for tbl_name, rows in self.tables.items():
            if not tbl_name.startswith("FRAME SECTION PROPERTIES"):
                continue
            for row in rows:
                name = row.get("Section") or row.get("SecName")
                if not name or mgr.get_section_by_name(name):
                    continue
                shape = (row.get("Shape") or "Rectangular").lower()
                ptype = SectionType.RECT
                if "circle" in shape:
                    ptype = SectionType.CIRCLE
                elif shape in ("i", "i-section", "i/w"):
                    ptype = SectionType.I
                elif "pipe" in shape:
                    ptype = SectionType.PIPE
                elif "box" in shape:
                    ptype = SectionType.BOX
                params = {k: float(v) for k, v in row.items()
                          if k in ("t3", "t2", "t1", "tw", "tf",
                                   "Depth", "Width", "Thickness")
                          and _num(v)}
                mat = mgr.get_material_by_name(row.get("Material", ""))
                mgr.add_section(Section(name, ptype, params, mat))

    def _import_load_patterns(self, mgr):
        for row in self.tables.get("LOAD PATTERN DEFINITIONS", []):
            name = row.get("LoadPat")
            if not name or name in mgr.load_patterns:
                continue
            mgr.load_patterns[name] = LoadPattern(
                name=name,
                design_type=row.get("DesignType", "Dead"),
                self_wt_mult=float(row.get("SelfWtMult", 0) or 0),
            )

    def _import_load_cases(self, mgr):
        for row in self.tables.get("LOAD CASE DEFINITIONS", []):
            name = row.get("Case") or row.get("CaseName")
            if not name or name in mgr.load_cases:
                continue
            mgr.load_cases[name] = LoadCase(
                name=name,
                case_type=row.get("Type", "LinStatic"),
                design_type=row.get("DesignType", "Dead"),
            )
        for row in self.tables.get("CASE - STATIC 1 - LOAD ASSIGNMENTS", []):
            case_name = row.get("Case")
            lc = mgr.load_cases.get(case_name)
            if not lc:
                continue
            lc.static_assignments.append(StaticLoadAssignment(
                load_type=row.get("LoadType", "Load pattern"),
                load_name=row.get("LoadName", ""),
                load_sf=float(row.get("LoadSF", 1.0) or 1.0),
            ))

    def _import_combinations(self, mgr):
        for row in self.tables.get("COMBINATION DEFINITIONS", []):
            name = row.get("Combo") or row.get("Name")
            if not name or name in mgr.combinations:
                continue
            items = []
            i = 1
            while f"Case{i}" in row:
                items.append(ComboItem(
                    case_or_pattern_name=row[f"Case{i}"],
                    scale_factor=float(row.get(f"SF{i}", 1.0) or 1.0),
                ))
                i += 1
            mgr.combinations[name] = LoadCombination(
                name=name,
                combo_type=row.get("Type", "Linear Add"),
                items=items,
            )


def _num(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False
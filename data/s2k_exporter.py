# data/s2k_exporter.py
"""
DefinitionManager'daki tanımları SAP2000 .s2k formatına yazar.
"""
from domain.definition_manager import DefinitionManager


class S2KWriter:
    def __init__(self, mgr: DefinitionManager):
        self.mgr = mgr

    def write(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            self._write_materials(f)
            self._write_sections(f)
            self._write_load_patterns(f)
            self._write_load_cases(f)
            self._write_combinations(f)

    @staticmethod
    def _tbl(f, name: str):
        f.write(f'\nTABLE: "{name}"\n')

    def _write_materials(self, f):
        self._tbl(f, "MATERIAL PROPERTIES 01 - GENERAL")
        for m in self.mgr.materials.values():
            t = "Steel" if m.mat_type.name == "STEEL" else "Concrete"
            f.write(f'   Material={m.name}  Type={t}\n')
        self._tbl(f, "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES")
        for m in self.mgr.materials.values():
            f.write(
                f'   Material={m.name}  E1={m.E1}  G12={m.G12}  '
                f'U12={m.nu12}  UnitMass={m.density}\n'
            )

    def _write_sections(self, f):
        self._tbl(f, "FRAME SECTION PROPERTIES 01 - GENERAL")
        for s in self.mgr.sections.values():
            mat = s.material.name if s.material else ""
            params = " ".join(f'{k}={v}' for k, v in s.profile_params.items())
            f.write(
                f'   Section={s.name}  Material={mat}  '
                f'Shape={s.profile_type.value}  {params}\n'
            )

    def _write_load_patterns(self, f):
        self._tbl(f, "LOAD PATTERN DEFINITIONS")
        for p in self.mgr.load_patterns.values():
            f.write(
                f'   LoadPat={p.name}  DesignType={p.design_type}  '
                f'SelfWtMult={p.self_wt_mult}\n'
            )

    def _write_load_cases(self, f):
        self._tbl(f, "LOAD CASE DEFINITIONS")
        for c in self.mgr.load_cases.values():
            f.write(
                f'   Case={c.name}  Type={c.case_type}  '
                f'DesignType={c.design_type}\n'
            )
        self._tbl(f, "CASE - STATIC 1 - LOAD ASSIGNMENTS")
        for c in self.mgr.load_cases.values():
            for a in c.static_assignments:
                f.write(
                    f'   Case={c.name}  LoadType={a.load_type}  '
                    f'LoadName={a.load_name}  LoadSF={a.load_sf}\n'
                )

    def _write_combinations(self, f):
        self._tbl(f, "COMBINATION DEFINITIONS")
        for combo in self.mgr.combinations.values():
            parts = [f'Combo={combo.name}', f'Type={combo.combo_type}']
            for i, it in enumerate(combo.items, start=1):
                parts.append(f'Case{i}={it.case_or_pattern_name}')
                parts.append(f'SF{i}={it.scale_factor}')
            f.write("   " + "  ".join(parts) + "\n")
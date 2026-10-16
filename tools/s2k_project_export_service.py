# tools/s2k_project_export_service.py
"""
Tam proje S2K export servisi.
SAP2000 .s2k formatında tüm modeli dışa aktarır:
- Material definitions
- Section definitions
- Joint coordinates
- Frame connectivity
- Restraints
- Load patterns
- Load cases
- Frame distributed loads
"""
from datetime import datetime
from typing import List, Optional

# tools/s2k_export_service.py
"""
S2K Export Service — Frame distributed load'ları SAP2000 formatında dışa aktarır.
"""
from typing import List

from domain.definition import SAP_DIR_CODES


class S2KExportService:

    # 10 yön SAP2000 kodları (Dir alanı için tam harita)
    type_to_sap_dir = {
        "1":  "1",   # Local 1
        "2":  "2",   # Local 2
        "3":  "3",   # Local 3
        "4":  "4",   # Global X
        "5":  "5",   # Global Y
        "6":  "6",   # Global Z
        "7":  "7",   # Gravity
        "8":  "8",   # Projected X
        "9":  "9",   # Projected Y
        "10": "10",  # Projected Z
    }

    # tools/s2k_export_service.py
    @classmethod
    def export_frame_distributed_loads_to_s2k(cls, frame_objects) -> str:
        lines = ['TABLE: "FRAME ASSIGN - DISTRIBUTED"']

        for frame in frame_objects:
            if not hasattr(frame, "dist_loads") or not frame.dist_loads:
                continue

            frame_id = (
                getattr(frame, "label", None)
                or getattr(frame, "name", None)
                or f"Frame_{getattr(frame, 'unique_id', id(frame))}"
            )

            for load in frame.dist_loads:
                # Güvenlik: points boş veya None olabilir
                pts = list(getattr(load, "points", None) or [])
                if not pts:
                    # Sessizce atla (SAP2000 default ile eşleşmez)
                    continue

                # Tek nokta varsa (tek nokta yükü) 2. noktayı ekle
                while len(pts) < 4:
                    pts.append(pts[-1])

                (d1, v1) = pts[0]
                (d2, v2) = pts[1]
                (d3, v3) = pts[2]
                (d4, v4) = pts[3]

                pattern = load.pattern_name
                coord_sys = getattr(load, "coord_sys", "Local")
                direction = cls.type_to_sap_dir.get(
                    str(getattr(load, "load_dir", "2")), "2"
                )
                dist_type = "Relative" if getattr(load, "is_relative", True) else "Absolute"
                opt = "Add" if load.mode == "ADD" else "Replace"

                line = (
                    f'   Frame="{frame_id}"  LoadPat="{pattern}"  '
                    f'CoordSys="{coord_sys}"  DistType="{dist_type}"  Dir="{direction}"  '
                    f'Dist1={d1:.4f}  V1={v1:.4f}  '
                    f'Dist2={d2:.4f}  V2={v2:.4f}  '
                    f'Dist3={d3:.4f}  V3={v3:.4f}  '
                    f'Dist4={d4:.4f}  V4={v4:.4f}  '
                    f'Opt="{opt}"'
                )
                lines.append(line)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    @classmethod
    def export_full_table(cls, frame_objects) -> str:
        """
        Tam s2k bloğu: header + default satır + tüm frame satırları.
        SAP2000'in okuduğu format.
        """
        header = [
            'TABLE: "FRAME ASSIGN - DISTRIBUTED"',
            '   Frame="DEFAULT"  LoadPat="DEFAULT"  CoordSys="Local"  '
            'DistType="Relative"  Dir="2"  V1=0  V2=0  Dist1=0  Dist2=0  Opt="Replace"',
        ]
        body = cls.export_frame_distributed_loads_to_s2k(frame_objects)
        # Body zaten ilk satırı TABLE ile başlatıyor, onu atlayalım
        body_lines = body.split("\n")[1:]
        return "\n".join(header + body_lines)

class S2KProjectExportService:

    # Birim sistemi haritası (SAP2000 kodları)
    UNIT_MAP = {
        "N_MM":   "N, mm, C",
        "N_M":    "N, m, C",
        "KN_MM":  "KN, mm, C",
        "KN_M":   "KN, m, C",
        "KGF_MM": "Kgf, mm, C",
        "KGF_M":  "Kgf, m, C",
        "TON_MM": "Tonf, mm, C",
        "TON_M":  "Tonf, m, C",
        "LB_IN":  "lb, in, F",
        "LB_FT":  "lb, ft, F",
        "KIP_IN": "Kip, in, F",
        "KIP_FT": "Kip, ft, F",
    }

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    @classmethod
    def export_project(cls, project) -> str:
        """
        Tüm projeyi S2K formatında dışa aktarır.
        Args:
            project: domain.project.Project
        Returns:
            str: S2K metin içeriği
        """
        scene = project.scene
        defs = project.definitions

        lines = []

        # 1) Header
        lines.append(cls._header(project))
        lines.append("")

        # 2) Birim sistemi
        lines.append(cls._units(project))
        lines.append("")

        # 3) Malzeme tanımları
        lines.append(cls._materials(defs))
        lines.append("")

        # 4) Kesit tanımları
        lines.append(cls._sections(defs))
        lines.append("")

        # 5) Load pattern tanımları
        lines.append(cls._load_patterns(defs))
        lines.append("")

        # 6) Load case tanımları
        lines.append(cls._load_cases(defs))
        lines.append("")

        # 7) Joint koordinatları
        lines.append(cls._joints(scene))
        lines.append("")

        # 8) Restraint'ler
        lines.append(cls._restraints(scene))
        lines.append("")

        # 9) Frame connectivity
        lines.append(cls._connectivity(scene))
        lines.append("")

        # 10) Frame distributed loads
        lines.append(cls._frame_distributed_loads(scene))
        lines.append("")

        # 11) Combos (varsa)
        combo_text = cls._combinations(defs)
        if combo_text:
            lines.append(combo_text)
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def save_to_file(cls, project, filepath: str):
        """Projeyi S2K dosyasına kaydeder."""
        text = cls.export_project(project)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(text)
        return filepath

    # ------------------------------------------------------------------
    # 1. HEADER
    # ------------------------------------------------------------------
    @classmethod
    def _header(cls, project) -> str:
        info = getattr(project, "info", None)
        name = getattr(info, "name", "Untitled") or "Untitled"
        desc = getattr(info, "description", "") or ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"# SAP2000 Model — {name}",
            f"# Cad4 Export @ {timestamp}",
        ]
        if desc:
            lines.append(f"# {desc}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 2. UNITS
    # ------------------------------------------------------------------
    @classmethod
    def _units(cls, project) -> str:
        us = getattr(project, "unit_system", None)
        unit_name = getattr(us, "name", "KN_M") if us else "KN_M"
        # Enum'ı string'e çevir (KN_M gibi)
        if hasattr(unit_name, "name"):
            unit_name = unit_name.name
        sap_units = cls.UNIT_MAP.get(str(unit_name), "KN, m, C")
        return f'TABLE: "PROGRAM CONTROL"\n   Units="{sap_units}"'

    # ------------------------------------------------------------------
    # 3. MATERIALS
    # ------------------------------------------------------------------
    @classmethod
    def _materials(cls, defs) -> str:
        mats = getattr(defs, "materials", {}) or {}

        lines = ['TABLE: "MATERIAL PROPERTIES 01 - GENERAL"']
        for name, mat in mats.items():
            mat_type = getattr(mat, "mat_type", None)
            type_str = getattr(mat_type, "name", "Steel") if mat_type else "Steel"
            lines.append(
                f'   Material="{name}"  Type="{type_str}"  '
                f'UnitMass={getattr(mat, "density", 7850) / 1e9:.6e}  '
                f'UnitWeight=0  SymType="Isotropic"  '
                f'TempDepend="No"  Color="Gray"  Notes=""'
            )
        lines.append("")
        lines.append('TABLE: "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"')
        for name, mat in mats.items():
            E = getattr(mat, "E1", 2.1e8)
            nu = getattr(mat, "nu12", 0.3)
            G = getattr(mat, "G12", 8.1e7)
            lines.append(
                f'   Material="{name}"  '
                f'UnitWeight=0  UnitMass=0  '
                f'E1={E:.6e}  E2={E:.6e}  E3={E:.6e}  '
                f'G12={G:.6e}  G13={G:.6e}  G23={G:.6e}  '
                f'U12={nu:.4f}  U13={nu:.4f}  U23={nu:.4f}'
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 4. SECTIONS
    # ------------------------------------------------------------------
    @classmethod
    def _sections(cls, defs) -> str:
        secs = getattr(defs, "sections", {}) or {}

        lines = ['TABLE: "FRAME SECTION PROPERTIES 01 - GENERAL"']
        for name, sec in secs.items():
            mat = getattr(sec, "material", None)
            mat_name = getattr(mat, "name", "DEFAULT_STEEL") if mat else "DEFAULT_STEEL"

            # Profil tipi
            pt = getattr(sec, "profile_type", None)
            pt_name = getattr(pt, "name", "Rectangular") if pt else "Rectangular"

            # SAP profil tipi haritası
            sap_type = {
                "I": "I/Wide Flange",
                "RECT": "Rectangular",
                "CIRCLE": "Circle",
                "TUBE": "Tube",
                "PIPE": "Pipe",
                "C": "Channel",
                "L": "Angle",
                "BOX": "Box/Tube",
                "T": "Tee",
                "CHANNEL": "Channel",
                "CUSTOM": "General",
            }.get(str(pt_name), "Rectangular")

            lines.append(
                f'   Section="{name}"  Material="{mat_name}"  '
                f'Shape="{sap_type}"  '
                f't3=0.1  t2=0.1  t3b=0.1  t2b=0.1  '
                f'Color="Gray"'
            )

        # Detaylı kesit parametreleri
        lines.append("")
        lines.append('TABLE: "FRAME SECTION PROPERTIES 02 - SHAPE DIMENSIONS"')
        for name, sec in secs.items():
            params = getattr(sec, "profile_params", {}) or {}
            # SAP parametreleri: d (yükseklik), b (genişlik), tw, tf
            h = params.get("h", 300)
            b = params.get("b", 200)
            lines.append(
                f'   Section="{name}"  '
                f'Shape="Rectangular"  '
                f'T3={h:.4f}  T2={b:.4f}'
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 5. LOAD PATTERNS
    # ------------------------------------------------------------------
    @classmethod
    def _load_patterns(cls, defs) -> str:
        patterns = getattr(defs, "load_patterns", {}) or {}

        lines = ['TABLE: "LOAD PATTERN DEFINITIONS"']
        # Varsayılan pattern'lar
        lines.append('   LoadPat="DEAD"  DesignType="Dead"  SelfWtMult=1')

        for name, lp in patterns.items():
            if name == "DEAD":
                continue  # zaten yazıldı
            dt = getattr(lp, "design_type", "Other")
            sw = getattr(lp, "self_wt_mult", 0.0)
            lines.append(
                f'   LoadPat="{name}"  '
                f'DesignType="{dt}"  '
                f'SelfWtMult={sw}'
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 6. LOAD CASES
    # ------------------------------------------------------------------
    @classmethod
    def _load_cases(cls, defs) -> str:
        cases = getattr(defs, "load_cases", {}) or {}

        lines = ['TABLE: "LOAD CASE DEFINITIONS"']
        # Varsayılan case
        lines.append(
            '   Case="DEAD"  Type="LinStatic"  '
            'InitialCond="Zero"  DesType="Dead"  '
            'AutoType="None"  RunCase="Yes"'
        )

        for name, lc in cases.items():
            ct = getattr(lc, "case_type", "LinStatic")
            dt = getattr(lc, "design_type", "Dead")
            ic = getattr(lc, "initial_cond", "Zero")
            at = getattr(lc, "auto_type", "None")
            rc = "Yes" if getattr(lc, "run_case", True) else "No"
            lines.append(
                f'   Case="{name}"  Type="{ct}"  '
                f'InitialCond="{ic}"  DesType="{dt}"  '
                f'AutoType="{at}"  RunCase="{rc}"'
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 7. JOINTS
    # ------------------------------------------------------------------
    @classmethod
    def _joints(cls, scene) -> str:
        nodes = getattr(scene, "nodes", {}) or {}

        lines = ['TABLE: "JOINT COORDINATES"']
        for node in nodes.values():
            label = getattr(node, "label", None) or f"J{node.unique_id}"
            x = getattr(node, "x", 0.0)
            y = getattr(node, "y", 0.0)
            z = getattr(node, "z", 0.0)
            lines.append(
                f'   Joint="{label}"  CoordSys="Global"  '
                f'XorR={x:.6f}  YorTheta={y:.6f}  Z={z:.6f}'
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 8. RESTRAINTS
    # ------------------------------------------------------------------
    @classmethod
    def _restraints(cls, scene) -> str:
        nodes = getattr(scene, "nodes", {}) or {}

        lines = ['TABLE: "JOINT RESTRAINT ASSIGNMENTS"']
        for node in nodes.values():
            r = getattr(node, "restraint", None)
            if r is None:
                continue
            label = getattr(node, "label", None) or f"J{node.unique_id}"
            u1 = "Yes" if getattr(r, "ux", False) else "No"
            u2 = "Yes" if getattr(r, "uy", False) else "No"
            u3 = "Yes" if getattr(r, "uz", False) else "No"
            r1 = "Yes" if getattr(r, "rx", False) else "No"
            r2 = "Yes" if getattr(r, "ry", False) else "No"
            r3 = "Yes" if getattr(r, "rz", False) else "No"
            lines.append(
                f'   Joint="{label}"  U1="{u1}"  U2="{u2}"  U3="{u3}"  '
                f'R1="{r1}"  R2="{r2}"  R3="{r3}"'
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 9. CONNECTIVITY
    # ------------------------------------------------------------------
    @classmethod
    def _connectivity(cls, scene) -> str:
        frames = getattr(scene, "frames", {}) or {}

        lines = ['TABLE: "CONNECTIVITY - FRAME"']
        for frame in frames.values():
            label = getattr(frame, "label", None) or f"F{frame.unique_id}"
            ni = getattr(frame, "node_i", None)
            nj = getattr(frame, "node_j", None)

            if not ni or not nj:
                continue

            ni_label = getattr(ni, "label", None) or f"J{ni.unique_id}"
            nj_label = getattr(nj, "label", None) or f"J{nj.unique_id}"

            sec = getattr(frame, "section", None)
            sec_name = getattr(sec, "name", "DEFAULT") if sec else "DEFAULT"

            rot = getattr(frame, "rotation_deg", 0.0)

            lines.append(
                f'   Frame="{label}"  '
                f'JointI="{ni_label}"  JointJ="{nj_label}"  '
                f'IsCurved="No"  '
                f'Length=0  '
                f'SectionName="{sec_name}"  '
                f'Rotation={rot:.4f}'
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 10. FRAME DISTRIBUTED LOADS
    # ------------------------------------------------------------------
    @classmethod
    def _frame_distributed_loads(cls, scene) -> str:

        frames = list((getattr(scene, "frames", {}) or {}).values())
        text = S2KExportService.export_full_table(frames)
        return text

    # ------------------------------------------------------------------
    # 11. COMBINATIONS
    # ------------------------------------------------------------------
    @classmethod
    def _combinations(cls, defs) -> str:
        combos = getattr(defs, "combinations", {}) or {}
        if not combos:
            return ""

        lines = ['TABLE: "COMBINATION DEFINITIONS"']
        for name, cb in combos.items():
            ct = getattr(cb, "combo_type", "Linear Add")
            items = getattr(cb, "items", []) or []

            # Her item dict veya ComboItem olabilir — ikisini de destekle
            item_strs = []
            for it in items:
                if hasattr(it, "case_or_pattern_name"):
                    n = it.case_or_pattern_name
                    sf = it.scale_factor
                elif isinstance(it, dict):
                    n = it.get("case_or_pattern_name", "")
                    sf = float(it.get("scale_factor", 1.0))
                else:
                    continue

                if not n:
                    continue
                item_strs.append(f'{n}="{sf:.4f}"')

            items_str = "  ".join(item_strs)
            lines.append(
                f'   Name="{name}"  Type="{ct}"  AutoDesign="No"  {items_str}'
            )
        return "\n".join(lines)
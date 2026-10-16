# tools/s2k_exporter.py
"""
S2K Exporter — Cad4 projesini SAP2000 .s2k formatına çevirir.
Sadece KULLANILAN elemanları, kesitleri, malzemeleri, noktaları, yükleri export eder.
Zone poligonları ve geçici elemanlar hariç tutulur.
"""
from datetime import datetime
from typing import Set, Dict, Any


class S2KExporter:
    """Cad4 Project → SAP2000 .s2k (filtreli)"""

    # ==================================================================
    # SAP2000 Yön Kodları
    # ==================================================================
    DIR_NAMES = {
        "1": "1", "2": "2", "3": "3",
        "4": "X", "5": "Y", "6": "Z",
        "7": "Gravity", "8": "ProjectedX",
        "9": "ProjectedY", "10": "ProjectedZ",
    }

    UNIT_MAP = {
        "N_MM": "N, mm, C", "N_M": "N, m, C",
        "KN_MM": "KN, mm, C", "KN_M": "KN, m, C",
        "KGF_MM": "Kgf, mm, C", "KGF_M": "Kgf, m, C",
        "TON_MM": "Tonf, mm, C", "TON_M": "Tonf, m, C",
        "LB_IN": "lb, in, F", "LB_FT": "lb, ft, F",
        "KIP_IN": "Kip, in, F", "KIP_FT": "Kip, ft, F",
    }

    DESIGN_TYPE_MAP = {
        "WIND": "Wind", "DEAD": "Dead", "LIVE": "Live",
        "QUAKE": "Quake", "SNOW": "Snow", "SUPERDEAD": "SuperDead",
        "NOTIONAL": "Notional", "OTHER": "Other", "ROOFLIVE": "RoofLive",
        "TEMPERATURE": "Temperature", "PATTERNLIVE": "PatternLive",
    }

    # ==================================================================
    # PUBLIC API
    # ==================================================================
    @classmethod
    def export(cls, project) -> str:
        scene = project.scene
        defs = project.definitions

        # --- Referans analizi ---
        used = cls._collect_used(scene, defs)

        sections = []
        sections.append(cls._program_control(project))
        sections.append(cls._active_dof())
        sections.append(cls._materials(defs, used))
        sections.append(cls._sections(defs, used))
        sections.append(cls._load_patterns(defs, used, scene))
        sections.append(cls._load_cases(defs, used, scene))
        sections.append(cls._combinations(defs, used))
        sections.append(cls._joint_coordinates(scene, used))
        sections.append(cls._joint_restraints(scene, used))
        sections.append(cls._connectivity(scene, used))
        sections.append(cls._frame_section_assignments(scene, used))
        sections.append(cls._frame_local_axes(scene, used))
        sections.append(cls._frame_loads_distributed(scene, used))

        sections = [s for s in sections if s]
        return "\n\n".join(sections) + "\n\nEND TABLE DATA\n"

    @classmethod
    def save(cls, project, filepath: str) -> str:
        text = cls.export(project)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(text)
        return filepath

    # ==================================================================
    # REFERANS ANALİZİ — hangi eleman/kesti/malzeme kullanılıyor?
    # ==================================================================
    @classmethod
    def _collect_used(cls, scene, defs) -> Dict[str, Set]:
        """Sahnedeki kullanılan elemanların referanslarını topla."""
        used_nodes: Set[str] = set()
        used_sections: Set[str] = set()
        used_materials: Set[str] = set()
        used_frame_labels: Set[str] = set()
        used_load_patterns: Set[str] = set()

        # --- Frame'ler ---
        for frame in scene.frames.values():
            label = getattr(frame, "label", None) or f"F{frame.unique_id}"

            # Zone node'larına bağlı frame'leri atla
            ni = getattr(frame, "node_i", None)
            nj = getattr(frame, "node_j", None)
            if not ni or not nj:
                continue

            ni_label = getattr(ni, "label", "") or f"J{ni.unique_id}"
            nj_label = getattr(nj, "label", "") or f"J{nj.unique_id}"

            # W_NODE_ içeren frame'leri atla (zone geometrisi)
            if ni_label.startswith("W_NODE_") or nj_label.startswith("W_NODE_"):
                continue

            used_frame_labels.add(label)
            used_nodes.add(ni_label)
            used_nodes.add(nj_label)

            # Kesit
            sec = getattr(frame, "section", None)
            if sec:
                sec_name = getattr(sec, "name", None)
                if sec_name:
                    used_sections.add(sec_name)
                    mat = getattr(sec, "material", None)
                    if mat:
                        mat_name = getattr(mat, "name", None)
                        if mat_name:
                            used_materials.add(mat_name)

            # Yük pattern'ları
            for dl in getattr(frame, "dist_loads", []) or []:
                pat = getattr(dl, "pattern_name", None)
                # Boş points'li yükleri sayma
                if pat and getattr(dl, "points", None):
                    used_load_patterns.add(pat)

            for pl in getattr(frame, "point_loads", []) or []:
                pat = getattr(pl, "pattern_name", None)
                if pat:
                    used_load_patterns.add(pat)

            for gl in getattr(frame, "gravity_loads", []) or []:
                pat = getattr(gl, "pattern_name", None)
                if pat:
                    used_load_patterns.add(pat)

            for tl in getattr(frame, "temp_loads", []) or []:
                pat = getattr(tl, "pattern_name", None)
                if pat:
                    used_load_patterns.add(pat)

        # --- Area'lar ---
        for area in getattr(scene, "areas", {}).values():
            for node in getattr(area, "nodes", []) or []:
                label = getattr(node, "label", "") or f"J{node.unique_id}"
                if not label.startswith("W_NODE_"):
                    used_nodes.add(label)

            sec_name = getattr(area, "section_name", None)
            if sec_name:
                used_sections.add(sec_name)

            # Yük pattern'ları
            for attr in ("gravity_loads", "strain_loads", "surface_pressures",
                         "temp_loads", "uniform_loads", "uniform_to_frame_loads",
                         "wind_pressures"):
                for ld in getattr(area, attr, []) or []:
                    pat = getattr(ld, "pattern_name", None)
                    if pat:
                        used_load_patterns.add(pat)

        # --- Link'ler ---
        for link in getattr(scene, "links", {}).values():
            ni = getattr(link, "node_i", None)
            nj = getattr(link, "node_j", None)
            if ni and nj:
                ni_label = getattr(ni, "label", "") or f"J{ni.unique_id}"
                nj_label = getattr(nj, "label", "") or f"J{nj.unique_id}"
                if not ni_label.startswith("W_NODE_"):
                    used_nodes.add(ni_label)
                if not nj_label.startswith("W_NODE_"):
                    used_nodes.add(nj_label)

        # --- Node restraint'leri ---
        for node in scene.nodes.values():
            label = getattr(node, "label", "") or f"J{node.unique_id}"
            if label.startswith("W_NODE_"):
                continue
            r = getattr(node, "restraint", None)
            if r and any(getattr(r, k, False) for k in
                         ("ux", "uy", "uz", "rx", "ry", "rz")):
                used_nodes.add(label)

        # --- Node nokta yükleri ---
        for node in scene.nodes.values():
            label = getattr(node, "label", "") or f"J{node.unique_id}"
            if label.startswith("W_NODE_"):
                continue
            for pl in getattr(node, "loads", []) or []:
                pat = getattr(pl, "pattern_name", None)
                if pat:
                    used_load_patterns.add(pat)
                    used_nodes.add(label)

        # --- Load Case'lerin kullandığı pattern'lar ---
        for lc in getattr(defs, "load_cases", {}).values():
            for sa in getattr(lc, "static_assignments", []) or []:
                ln = getattr(sa, "load_name", None)
                if ln:
                    used_load_patterns.add(ln)

        # --- Combination'ların kullandığı case/pattern'lar ---
        used_cases = set()
        for cb in getattr(defs, "combinations", {}).values():
            for it in getattr(cb, "items", []) or []:
                n = getattr(it, "case_or_pattern_name", None) if hasattr(it, "case_or_pattern_name") \
                    else (it.get("case_or_pattern_name") if isinstance(it, dict) else None)
                if n:
                    used_cases.add(n)

        return {
            "nodes": used_nodes,
            "sections": used_sections,
            "materials": used_materials,
            "frames": used_frame_labels,
            "patterns": used_load_patterns,
            "cases": used_cases,
        }

    # ==================================================================
    # 1. PROGRAM CONTROL
    # ==================================================================
    @classmethod
    def _program_control(cls, project) -> str:
        us = getattr(project, "unit_system", None)
        unit_name = getattr(us, "name", "N_MM") if us else "N_MM"
        if hasattr(unit_name, "name"):
            unit_name = unit_name.name
        sap_units = cls.UNIT_MAP.get(str(unit_name), "N, mm, C")
        return (
            'TABLE:  "PROGRAM CONTROL"\n'
            f'   ProgramName=SAP2000   Version=25.3.1   '
            f'CurrUnits="{sap_units}"   '
            f'SteelCode="AISC 360-10"   ConcCode="ACI 318-08/IBC2009"   '
            f'AlumCode="AA 2015"   ColdCode=AISI-ASD96   RegenHinge=No'
        )

    @classmethod
    def _active_dof(cls) -> str:
        return (
            'TABLE:  "ACTIVE DEGREES OF FREEDOM"\n'
            '   UX=Yes   UY=Yes   UZ=Yes   RX=Yes   RY=Yes   RZ=Yes'
        )

    # ==================================================================
    # 2. MATERIALS — sadece kullanılanlar
    # ==================================================================
    @classmethod
    def _materials(cls, defs, used) -> str:
        mats = getattr(defs, "materials", {}) or {}
        used_mats = used.get("materials", set())

        # Kullanılan malzemeleri filtrele
        filtered = {n: m for n, m in mats.items() if n in used_mats}
        if not filtered:
            # Hiç yoksa default steel ekle
            filtered = {"S275": None}

        general = ['TABLE:  "MATERIAL PROPERTIES 01 - GENERAL"']
        mech = ['TABLE:  "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"']
        steel = ['TABLE:  "MATERIAL PROPERTIES 03A - STEEL DATA"']

        for name, mat in filtered.items():
            if mat is None:
                # Varsayılan çelik
                general.append(
                    f'   Material={name}   Type=Steel   '
                    f'SymType=Isotropic   TempDepend=No   Color=Yellow'
                )
                mech.append(
                    f'   Material={name}   '
                    f'UnitWeight=7.6973E-05   UnitMass=7.849E-09   '
                    f'E1=210000   G12=80769.23   U12=0.3   A1=1.17E-05'
                )
                steel.append(
                    f'   Material={name}   Fy=275   Fu=430   '
                    f'EffFy=302.5   EffFu=473   '
                    f'SSCurveOpt=Simple   SSHysType=Kinematic   '
                    f'SHard=0.015   SMax=0.11   SRup=0.17   FinalSlope=-0.1   '
                    f'CoupModType="Von Mises"'
                )
                continue

            # mat_type güvenliği
            mat_type = getattr(mat, "mat_type", None)
            if mat_type is None:
                type_name = "STEEL"
            elif hasattr(mat_type, "name"):
                type_name = mat_type.name
            else:
                type_name = str(mat_type)

            sap_type = {
                "STEEL": "Steel", "CONCRETE": "Concrete",
                "ALUMINUM": "Aluminum", "TIMBER": "Timber",
                "MASONRY": "Masonry", "NODESIGN": "None",
                "COLDFORMED": "ColdFormed", "REBAR": "Rebar",
                "TENDON": "Tendon",
            }.get(str(type_name).upper(), "Steel")

            general.append(
                f'   Material={name}   Type={sap_type}   '
                f'SymType=Isotropic   TempDepend=No   Color=Yellow'
            )

            E = getattr(mat, "E1", 210000.0)
            G = getattr(mat, "G12", 80769.23)
            nu = getattr(mat, "nu12", 0.3)
            density = getattr(mat, "density", 7850.0)

            # kg/m³ → N/mm³ ve kg/mm³
            unit_weight = density * 9.81e-9
            unit_mass = density * 1e-12

            mech.append(
                f'   Material={name}   '
                f'UnitWeight={cls._g(unit_weight)}   '
                f'UnitMass={cls._g(unit_mass)}   '
                f'E1={cls._g(E)}   G12={cls._g(G)}   U12={cls._g(nu)}   '
                f'A1=1.17E-05'
            )

            if sap_type == "Steel":
                steel.append(
                    f'   Material={name}   Fy=275   Fu=430   '
                    f'EffFy=302.5   EffFu=473   '
                    f'SSCurveOpt=Simple   SSHysType=Kinematic   '
                    f'SHard=0.015   SMax=0.11   SRup=0.17   FinalSlope=-0.1   '
                    f'CoupModType="Von Mises"'
                )

        parts = ["\n".join(general), "\n".join(mech)]
        if len(steel) > 1:
            parts.append("\n".join(steel))
        return "\n\n".join(parts)

    # ==================================================================
    # 3. SECTIONS — sadece kullanılanlar
    # ==================================================================
    @classmethod
    def _sections(cls, defs, used) -> str:
        secs = getattr(defs, "sections", {}) or {}
        used_secs = used.get("sections", set())

        filtered = {n: s for n, s in secs.items() if n in used_secs}
        if not filtered:
            return ""

        lines = ['TABLE:  "FRAME SECTION PROPERTIES 01 - GENERAL"']

        for name, sec in filtered.items():
            mat = getattr(sec, "material", None)
            mat_name = getattr(mat, "name", "S275") if mat else "S275"

            pt = getattr(sec, "profile_type", None)
            pt_name = getattr(pt, "name", "I") if pt else "I"
            sap_shape = {
                "I": "I/Wide Flange", "RECT": "Rectangular",
                "CIRCLE": "Circle", "TUBE": "Tube", "PIPE": "Pipe",
                "C": "Channel", "CHANNEL": "Channel", "L": "Angle",
                "BOX": "Box/Tube", "T": "Tee", "CUSTOM": "General",
            }.get(str(pt_name), "I/Wide Flange")

            params = getattr(sec, "profile_params", {}) or {}
            t3 = params.get("h", params.get("d", 200.0))
            t2 = params.get("b", 200.0)
            tw = params.get("tw", 9.0)
            tf = params.get("tf", 15.0)

            lines.append(
                f'   SectionName={name}   Material={mat_name}   '
                f'Shape="{sap_shape}"   '
                f't3={cls._g(t3)}   t2={cls._g(t2)}   '
                f'tf={cls._g(tf)}   tw={cls._g(tw)}   '
                f't2b={cls._g(t2)}   tfb={cls._g(tf)}   '
                f'Color=Red   FromFile=No'
            )

        return "\n".join(lines)

    # ==================================================================
    # 4. LOAD PATTERNS — sadece kullanılanlar
    # ==================================================================
    @classmethod
    def _load_patterns(cls, defs, used, scene) -> str:
        patterns = getattr(defs, "load_patterns", {}) or {}
        used_pats = used.get("patterns", set())

        # Sahneden ve case'lerden gelen pattern'ları birleştir
        all_used = set(used_pats)

        # Case'lerin kullandığı pattern'lar
        for lc in getattr(defs, "load_cases", {}).values():
            for sa in getattr(lc, "static_assignments", []) or []:
                ln = getattr(sa, "load_name", None)
                if ln:
                    all_used.add(ln)

        # Definitions'da olan ama kullanılmayanları da atla
        filtered = {n: p for n, p in patterns.items() if n in all_used}

        # Hiç yoksa "DEAD" ekle
        if not filtered:
            filtered = {"DEAD": None}

        lines = ['TABLE:  "LOAD PATTERN DEFINITIONS"']

        for name, lp in filtered.items():
            if not name or str(name).lower() == "nan":
                continue

            if lp is None:
                lines.append(f'   LoadPat={name}   DesignType=Dead   SelfWtMult=1')
                continue

            dt_raw = getattr(lp, "design_type", "Other") or "Other"
            dt = cls.DESIGN_TYPE_MAP.get(str(dt_raw).upper(), str(dt_raw))
            sw = getattr(lp, "self_wt_mult", 0.0) or 0.0

            # Notional / Quake / Wind için ek alanlar
            extra = ""
            if dt == "Notional":
                base = "D" if "G" in str(name).upper() else "L"
                extra = f'   NotBasePat={base}   NotRatio=0.002   NotDir="Global X"'
            elif dt in ("Quake", "Wind"):
                extra = "   AutoLoad=None"

            lines.append(
                f'   LoadPat={name}   DesignType={dt}   '
                f'SelfWtMult={cls._g(sw)}{extra}'
            )

        return "\n".join(lines)

    # ==================================================================
    # 5. LOAD CASES — sadece kullanılanlar
    # ==================================================================
    @classmethod
    def _load_cases(cls, defs, used, scene) -> str:
        cases = getattr(defs, "load_cases", {}) or {}
        used_cases = used.get("cases", set())

        # Doğrudan kullanılan case'ler + statik atama içeren case'ler
        active_cases = set(used_cases)
        for name, lc in cases.items():
            if getattr(lc, "static_assignments", None):
                active_cases.add(name)

        # Case'lerin kullandığı pattern'ları da topla
        # (case isimleri pattern isimleriyle aynı olabilir)
        patterns_used = used.get("patterns", set())
        for pat_name in patterns_used:
            if pat_name in cases:
                active_cases.add(pat_name)

        filtered = {n: c for n, c in cases.items() if n in active_cases}

        if not filtered:
            return ""

        lines = ['TABLE:  "LOAD CASE DEFINITIONS"']

        for name, lc in filtered.items():
            if not name or str(name).lower() == "nan":
                continue

            ctype = getattr(lc, "case_type", "LinStatic") or "LinStatic"
            ic = getattr(lc, "initial_cond", "Zero")
            if ic is None or str(ic).lower() in ("nan", "none", ""):
                ic = "Zero"

            dt_raw = getattr(lc, "design_type", "Dead") or "Dead"
            dt = cls.DESIGN_TYPE_MAP.get(str(dt_raw).upper(), str(dt_raw))

            at = getattr(lc, "auto_type", "None") or "None"
            rc = "Yes" if getattr(lc, "run_case", True) else "No"

            lines.append(
                f'   Case={name}   Type={ctype}   '
                f'InitialCond={ic}   '
                f'DesTypeOpt="Prog Det"   DesignType={dt}   '
                f'DesActOpt="Prog Det"   DesignAct=Non-Composite   '
                f'AutoType={at}   RunCase={rc}'
            )

        return "\n".join(lines)

    # ==================================================================
    # 6. COMBINATIONS — sadece kullanılanlar
    # ==================================================================
    @classmethod
    def _combinations(cls, defs, used) -> str:
        combos = getattr(defs, "combinations", {}) or {}
        if not combos:
            return ""

        lines = ['TABLE:  "COMBINATION DEFINITIONS"']
        has_any = False

        for name, cb in combos.items():
            if not name or str(name).lower() == "nan":
                continue

            ctype = getattr(cb, "combo_type", "Linear Add") or "Linear Add"
            ctype_str = f'"{ctype}"' if " " in str(ctype) else str(ctype)
            items = getattr(cb, "items", []) or []
            if not items:
                continue

            valid_items = []
            for it in items:
                if hasattr(it, "case_or_pattern_name"):
                    cn = it.case_or_pattern_name
                    sf = it.scale_factor
                elif isinstance(it, dict):
                    cn = it.get("case_or_pattern_name", "")
                    sf = float(it.get("scale_factor", 1.0))
                else:
                    continue
                if cn and str(cn).lower() != "nan":
                    valid_items.append((cn, sf))

            if not valid_items:
                continue

            has_any = True
            for idx, (cn, sf) in enumerate(valid_items):
                if idx == 0:
                    lines.append(
                        f'   ComboName={name}   '
                        f'ComboType={ctype_str}   AutoDesign=No   '
                        f'CaseName={cn}   ScaleFactor={cls._g(sf)}'
                    )
                else:
                    lines.append(
                        f'   ComboName={name}   '
                        f'CaseName={cn}   ScaleFactor={cls._g(sf)}'
                    )

        return "\n".join(lines) if has_any else ""

    # ==================================================================
    # 7. JOINT COORDINATES — sadece kullanılan node'lar
    # ==================================================================
    @classmethod
    def _joint_coordinates(cls, scene, used) -> str:
        nodes = getattr(scene, "nodes", {}) or {}
        used_nodes = used.get("nodes", set())
        if not used_nodes:
            return ""

        lines = ['TABLE:  "JOINT COORDINATES"']

        for node in nodes.values():
            label = getattr(node, "label", None) or f"J{node.unique_id}"
            if label.startswith("W_NODE_"):
                continue
            if label not in used_nodes:
                continue

            x = getattr(node, "x", 0.0)
            y = getattr(node, "y", 0.0)
            z = getattr(node, "z", 0.0)

            lines.append(
                f'   Joint={label}   CoordSys=GLOBAL   CoordType=Cartesian   '
                f'XorR={cls._g(x)}   Y={cls._g(y)}   Z={cls._g(z)}   SpecialJt=No'
            )

        return "\n".join(lines)

    # ==================================================================
    # 8. JOINT RESTRAINTS — sadece kullanılan node'lar
    # ==================================================================
    @classmethod
    def _joint_restraints(cls, scene, used) -> str:
        nodes = getattr(scene, "nodes", {}) or {}
        used_nodes = used.get("nodes", set())

        lines = ['TABLE:  "JOINT RESTRAINT ASSIGNMENTS"']
        has_any = False

        for node in nodes.values():
            label = getattr(node, "label", None) or f"J{node.unique_id}"
            if label.startswith("W_NODE_"):
                continue
            if label not in used_nodes:
                continue

            r = getattr(node, "restraint", None)
            if r is None:
                continue
            if not any(getattr(r, k, False) for k in
                       ("ux", "uy", "uz", "rx", "ry", "rz")):
                continue

            has_any = True
            u1 = "Yes" if getattr(r, "ux", False) else "No"
            u2 = "Yes" if getattr(r, "uy", False) else "No"
            u3 = "Yes" if getattr(r, "uz", False) else "No"
            r1 = "Yes" if getattr(r, "rx", False) else "No"
            r2 = "Yes" if getattr(r, "ry", False) else "No"
            r3 = "Yes" if getattr(r, "rz", False) else "No"

            lines.append(
                f'   Joint={label}   '
                f'U1={u1}   U2={u2}   U3={u3}   '
                f'R1={r1}   R2={r2}   R3={r3}'
            )

        return "\n".join(lines) if has_any else ""

    # ==================================================================
    # 9. CONNECTIVITY — sadece geçerli frame'ler
    # ==================================================================
    @classmethod
    def _connectivity(cls, scene, used) -> str:
        frames = getattr(scene, "frames", {}) or {}
        used_frames = used.get("frames", set())
        if not used_frames:
            return ""

        lines = ['TABLE:  "CONNECTIVITY - FRAME"']

        for frame in frames.values():
            label = getattr(frame, "label", None) or f"F{frame.unique_id}"
            if label not in used_frames:
                continue

            ni = getattr(frame, "node_i", None)
            nj = getattr(frame, "node_j", None)
            if not ni or not nj:
                continue

            ni_label = getattr(ni, "label", None) or f"J{ni.unique_id}"
            nj_label = getattr(nj, "label", None) or f"J{nj.unique_id}"

            lines.append(
                f'   Frame={label}   JointI={ni_label}   JointJ={nj_label}   '
                f'IsCurved=No'
            )

        return "\n".join(lines)

    # ==================================================================
    # 10. FRAME SECTION ASSIGNMENTS
    # ==================================================================
    @classmethod
    def _frame_section_assignments(cls, scene, used) -> str:
        frames = getattr(scene, "frames", {}) or {}
        used_frames = used.get("frames", set())
        if not used_frames:
            return ""

        lines = ['TABLE:  "FRAME SECTION ASSIGNMENTS"']

        for frame in frames.values():
            label = getattr(frame, "label", None) or f"F{frame.unique_id}"
            if label not in used_frames:
                continue

            sec = getattr(frame, "section", None)
            sec_name = getattr(sec, "name", "DEFAULT") if sec else "DEFAULT"

            lines.append(
                f'   Frame={label}   AutoSelect=N.A.   '
                f'AnalSect={sec_name}   MatProp=Default'
            )

        return "\n".join(lines)

    # ==================================================================
    # 11. FRAME LOCAL AXES
    # ==================================================================
    @classmethod
    def _frame_local_axes(cls, scene, used) -> str:
        frames = getattr(scene, "frames", {}) or {}
        used_frames = used.get("frames", set())

        lines = ['TABLE:  "FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL"']
        has_any = False

        for frame in frames.values():
            label = getattr(frame, "label", None) or f"F{frame.unique_id}"
            if label not in used_frames:
                continue

            rot = getattr(frame, "rotation_deg", 0.0)
            if abs(rot) < 1e-9:
                continue

            has_any = True
            lines.append(f'   Frame={label}   Angle={cls._g(rot)}')

        return "\n".join(lines) if has_any else ""

    # ==================================================================
    # 12. FRAME LOADS - DISTRIBUTED
    # ==================================================================
    @classmethod
    def _frame_loads_distributed(cls, scene, used) -> str:
        frames = getattr(scene, "frames", {}) or {}
        used_frames = used.get("frames", set())

        lines = ['TABLE:  "FRAME LOADS - DISTRIBUTED"']
        has_any = False

        for frame in frames.values():
            label = getattr(frame, "label", None) or f"F{frame.unique_id}"
            if label not in used_frames:
                continue

            loads = getattr(frame, "dist_loads", []) or []
            if not loads:
                continue

            try:
                frame_len = float(frame.get_length() or 1.0)
            except Exception:
                frame_len = 1.0

            for load in loads:
                pts = list(getattr(load, "points", None) or [])
                if len(pts) < 2:
                    continue  # boş points'li yükleri atla

                pattern = getattr(load, "pattern_name", "")
                if not pattern or str(pattern).lower() == "nan":
                    continue

                coord_sys = cls._sap_coordsys(getattr(load, "coord_sys", "Local"))
                dir_raw = str(getattr(load, "load_dir", "2"))
                dir_name = cls.DIR_NAMES.get(dir_raw, dir_raw)
                is_relative = bool(getattr(load, "is_relative", True))

                for i in range(len(pts) - 1):
                    a, va = pts[i]
                    b, vb = pts[i + 1]
                    if b <= a:
                        continue

                    if is_relative:
                        rel_a, rel_b = a, b
                        abs_a, abs_b = a * frame_len, b * frame_len
                    else:
                        abs_a, abs_b = a, b
                        rel_a = a / frame_len if frame_len > 1e-9 else 0.0
                        rel_b = b / frame_len if frame_len > 1e-9 else 0.0

                    has_any = True
                    lines.append(
                        f'   Frame={label}'
                        f'   LoadPat={pattern}'
                        f'   CoordSys={coord_sys}'
                        f'   Type=Force'
                        f'   Dir={dir_name}'
                        f'   DistType=RelDist'
                        f'   RelDistA={cls._g(rel_a)}'
                        f'   RelDistB={cls._g(rel_b)}'
                        f'   AbsDistA={cls._g(abs_a)}'
                        f'   AbsDistB={cls._g(abs_b)}'
                        f'   FOverLA={cls._g(va)}'
                        f'   FOverLB={cls._g(vb)}'
                    )

        return "\n".join(lines) if has_any else ""

    # ==================================================================
    # YARDIMCILAR
    # ==================================================================
    @staticmethod
    def _g(v) -> str:
        if v is None:
            return "0"
        try:
            v = float(v)
        except (TypeError, ValueError):
            return str(v)
        if abs(v) < 1e-15:
            return "0"
        return f"{v:g}"

    @staticmethod
    def _sap_coordsys(cs) -> str:
        s = str(cs or "").strip().lower()
        if s in ("global", "g"):
            return "GLOBAL"
        return "Local"
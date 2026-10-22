# tools/s2k_exporter.py
"""
S2K Exporter — Cad4 projesini SAP2000 .s2k formatına çevirir.

Kullanım:
    from tools.s2k_exporter import S2KExporter
    text = S2KExporter.export(project)                    # tüm sahne
    text = S2KExporter.export(project, selected_elements) # seçili elemanlar

Kısmi export: SAP2000'de "Add to existing model" ile birleştirilebilir.
Aynı label'lı tanımlar çakışırsa SAP import dialog'unda Replace/Ignore seçilir.
"""
from typing import Set, Dict, Optional, List


class S2KExporter:

    # ==================================================================
    # SAP2000 Sabitleri
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
    def export(cls, project, selected_elements: Optional[List] = None) -> str:
        scene = project.scene
        used = cls._collect_used(scene, project, selected_elements)

        sections = [
            cls._program_control(project),
            cls._active_dof(),
            cls._materials(project, used),
            cls._sections(project, used),
            cls._link_props(project, used),
            cls._load_patterns(project, used, scene),
            cls._load_cases(project, used, scene),
            cls._combinations(project, used),
            cls._joint_coordinates(scene, used),
            cls._joint_restraints(scene, used),
            cls._frame_connectivity(scene, used),
            cls._frame_section_assignments(scene, used),
            cls._frame_local_axes(scene, used),
            cls._frame_loads_distributed(scene, used),
            cls._area_section_properties(scene, used),
            cls._area_connectivity(scene, used),
            cls._area_section_assignments(scene, used),
            cls._link_connectivity(scene, used),
            cls._link_assignments(scene, used),
        ]
        sections = [s for s in sections if s]
        return "\n\n".join(sections) + "\n\nEND TABLE DATA\n"

    @classmethod
    def save(cls, project, filepath: str,
             selected_elements: Optional[List] = None) -> str:
        text = cls.export(project, selected_elements)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(text)
        return filepath

    # ==================================================================
    # REFERANS ANALİZİ
    # ==================================================================
    @classmethod
    def _collect_used(cls, scene, project, selected_elements=None) -> Dict[str, Set]:
        """
        Hangi node / section / material / pattern kullanılıyor?
        selected_elements verilmişse sadece o elemanlar taranır.
        """
        used_nodes: Set[str] = set()
        used_sections: Set[str] = set()
        used_materials: Set[str] = set()
        used_frames: Set[str] = set()
        used_areas: Set[str] = set()
        used_links: Set[str] = set()
        used_link_props: Set[str] = set()
        used_patterns: Set[str] = set()

        # Seçim filtresi
        sel_ids: Optional[Set[int]] = None
        if selected_elements is not None:
            sel_ids = {getattr(e, "unique_id", -1) for e in selected_elements}

        def _include(el) -> bool:
            if sel_ids is None:
                return True
            return getattr(el, "unique_id", -1) in sel_ids

        # --- FRAME'ler ---
        for frame in getattr(scene, "frames", {}).values():
            if not _include(frame):
                continue

            ni = getattr(frame, "node_i", None)
            nj = getattr(frame, "node_j", None)
            if not ni or not nj:
                continue

            ni_label = getattr(ni, "label", None) or f"J{ni.unique_id}"
            nj_label = getattr(nj, "label", None) or f"J{nj.unique_id}"
            if ni_label.startswith("W_NODE_") or nj_label.startswith("W_NODE_"):
                continue

            label = getattr(frame, "label", None) or f"F{frame.unique_id}"
            used_frames.add(label)
            used_nodes.add(ni_label)
            used_nodes.add(nj_label)

            sec = getattr(frame, "section", None)
            if sec:
                sn = getattr(sec, "name", None)
                if sn:
                    used_sections.add(sn)
                mat = getattr(sec, "material", None)
                if mat:
                    mn = getattr(mat, "name", None)
                    if mn:
                        used_materials.add(mn)

            for dl in getattr(frame, "dist_loads", []) or []:
                pat = getattr(dl, "pattern_name", None)
                if pat:
                    used_patterns.add(pat)

            for pl in getattr(frame, "point_loads", []) or []:
                pat = getattr(pl, "pattern_name", None)
                if pat:
                    used_patterns.add(pat)

            for gl in getattr(frame, "gravity_loads", []) or []:
                pat = getattr(gl, "pattern_name", None)
                if pat:
                    used_patterns.add(pat)

            for tl in getattr(frame, "temp_loads", []) or []:
                pat = getattr(tl, "pattern_name", None)
                if pat:
                    used_patterns.add(pat)

        # --- AREA'lar ---
        for area in getattr(scene, "areas", {}).values():
            if not _include(area):
                continue

            label = getattr(area, "label", None) or f"A{area.unique_id}"
            used_areas.add(label)

            for nd in getattr(area, "nodes", []) or []:
                nl = getattr(nd, "label", None) or f"J{nd.unique_id}"
                if not nl.startswith("W_NODE_"):
                    used_nodes.add(nl)

            sn = getattr(area, "section_name", None)
            if sn:
                used_sections.add(sn)

            # Area material
            mat = getattr(area, "material", None)
            if mat:
                mn = getattr(mat, "name", None)
                if mn:
                    used_materials.add(mn)

            for attr in ("gravity_loads", "strain_loads", "surface_pressures",
                         "temp_loads", "uniform_loads", "uniform_to_frame_loads",
                         "wind_pressures"):
                for ld in getattr(area, attr, []) or []:
                    pat = getattr(ld, "pattern_name", None)
                    if pat:
                        used_patterns.add(pat)

        # --- LINK'ler ---
        for link in getattr(scene, "links", {}).values():
            if not _include(link):
                continue

            label = getattr(link, "label", None) or f"L{link.unique_id}"
            used_links.add(label)

            ni = getattr(link, "node_i", None)
            nj = getattr(link, "node_j", None)
            if ni and nj:
                for n in (ni, nj):
                    nl = getattr(n, "label", None) or f"J{n.unique_id}"
                    if not nl.startswith("W_NODE_"):
                        used_nodes.add(nl)

            prop = getattr(link, "propname", None)
            if prop:
                used_link_props.add(prop)

        # --- Restraint'li node'lar ---
        for node in getattr(scene, "nodes", {}).values():
            if not _include(node):
                # Node seçili değilse yine de restraint varsa kullanılıyor say
                # (frame/area/link tarafından zaten toplanmış olabilir)
                pass
            label = getattr(node, "label", None) or f"J{node.unique_id}"
            if label.startswith("W_NODE_"):
                continue
            r = getattr(node, "restraint", None)
            if r and any(getattr(r, k, False) for k in
                         ("ux", "uy", "uz", "rx", "ry", "rz")):
                if sel_ids is None or _include(node):
                    used_nodes.add(label)

        # --- Node nokta yükleri ---
        for node in getattr(scene, "nodes", {}).values():
            if not _include(node):
                continue
            label = getattr(node, "label", None) or f"J{node.unique_id}"
            if label.startswith("W_NODE_"):
                continue
            for pl in getattr(node, "loads", []) or []:
                pat = getattr(pl, "pattern_name", None)
                if pat:
                    used_patterns.add(pat)
                    used_nodes.add(label)

        # --- Case'lerin kullandığı pattern'lar ---
        for lc in getattr(project, "load_cases", {}).values():
            for sa in getattr(lc, "static_assignments", []) or []:
                ln = getattr(sa, "load_name", None)
                if ln:
                    used_patterns.add(ln)

        # --- Combo'ların kullandığı case/pattern'lar ---
        used_cases: Set[str] = set()
        for cb in getattr(project, "combinations", {}).values():
            for it in getattr(cb, "items", []) or []:
                n = getattr(it, "case_or_pattern_name", None)
                if n:
                    used_cases.add(n)
            used_cases.add(getattr(cb, "name", ""))

        # Case'lerden pattern isimleriyle eşleşenleri de case olarak say
        for pat in list(used_patterns):
            if pat in getattr(project, "load_cases", {}):
                used_cases.add(pat)

        return {
            "nodes": used_nodes,
            "sections": used_sections,
            "materials": used_materials,
            "frames": used_frames,
            "areas": used_areas,
            "links": used_links,
            "link_props": used_link_props,
            "patterns": used_patterns,
            "cases": used_cases,
        }

    # ==================================================================
    # PROGRAM CONTROL
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
            f'SteelCode="AISC 360-16"   ConcCode="ACI 318-19"   '
            f'AlumCode="AA 2015"   ColdCode=AISI-16   RegenHinge=Yes'
        )

    @classmethod
    def _active_dof(cls) -> str:
        return (
            'TABLE:  "ACTIVE DEGREES OF FREEDOM"\n'
            '   UX=Yes   UY=Yes   UZ=Yes   RX=Yes   RY=Yes   RZ=Yes'
        )

    # ==================================================================
    # MATERIALS
    # ==================================================================
    @classmethod
    def _materials(cls, project, used) -> str:
        mats = getattr(project, "materials", {}) or {}
        used_mats = used.get("materials", set())
        filtered = {n: m for n, m in mats.items() if n in used_mats}
        if not filtered:
            return ""

        general = ['TABLE:  "MATERIAL PROPERTIES 01 - GENERAL"']
        mech = ['TABLE:  "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"']
        steel = ['TABLE:  "MATERIAL PROPERTIES 03A - STEEL DATA"']
        concrete = ['TABLE:  "MATERIAL PROPERTIES 03B - CONCRETE DATA"']
        rebar = ['TABLE:  "MATERIAL PROPERTIES 03E - REBAR DATA"']
        tendon = ['TABLE:  "MATERIAL PROPERTIES 03F - TENDON DATA"']

        for name, mat in filtered.items():
            mat_type = getattr(mat, "mat_type", None)
            type_name = getattr(mat_type, "name", "STEEL") if mat_type else "STEEL"

            sap_type = {
                "STEEL": "Steel", "CONCRETE": "Concrete",
                "REBAR": "Rebar", "TENDON": "Tendon",
                "ALUMINUM": "Aluminum", "TIMBER": "Timber",
                "MASONRY": "Masonry", "NODESIGN": "None",
                "COLDFORMED": "ColdFormed",
            }.get(str(type_name).upper(), "Steel")

            general.append(
                f'   Material={name}   Type={sap_type}   '
                f'SymType=Isotropic   TempDepend=No   Color=Yellow'
            )

            E = getattr(mat, "E1", 210000.0)
            G = getattr(mat, "G12", 80769.23)
            nu = getattr(mat, "nu12", 0.3)
            density = getattr(mat, "density", 7850.0)

            # density: kg/m³ varsayımıyla N/mm³ ve kg/mm³
            unit_weight = float(density) * 9.81e-9
            unit_mass = float(density) * 1e-12

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
            elif sap_type == "Concrete":
                fc = getattr(mat, "fc", 30.0)
                concrete.append(
                    f'   Material={name}   Fc={cls._g(fc)}   eFc={cls._g(fc)}   '
                    f'LtWtConc=No   SSCurveOpt=Mander   SSHysType=Takeda   '
                    f'SFc=0.002   SCap=0.005   FinalSlope=-0.1   '
                    f'FAngle=0   DAngle=0   CoupModType="Modified Darwin-Pecknold"'
                )
            elif sap_type == "Rebar":
                fy = getattr(mat, "fy", 420.0)
                fu = getattr(mat, "fu", 600.0)
                rebar.append(
                    f'   Material={name}   Fy={cls._g(fy)}   Fu={cls._g(fu)}   '
                    f'EffFy={cls._g(float(fy) * 1.1)}   '
                    f'EffFu={cls._g(float(fu) * 1.1)}   '
                    f'SSCurveOpt=Simple   SSHysType=Kinematic   '
                    f'SHard=0.01   SCap=0.09   FinalSlope=-0.1   '
                    f'UseCTDef=No   CoupModType="Von Mises"'
                )
            elif sap_type == "Tendon":
                fy = getattr(mat, "fy", 1700.0)
                fu = getattr(mat, "fu", 1900.0)
                tendon.append(
                    f'   Material={name}   Fy={cls._g(fy)}   Fu={cls._g(fu)}   '
                    f'SSCurveOpt="270 ksi"   SSHysType=Kinematic   '
                    f'FinalSlope=-0.1   CoupModType="Von Mises"'
                )

        parts = ["\n".join(general), "\n".join(mech)]
        if len(steel) > 1:
            parts.append("\n".join(steel))
        if len(concrete) > 1:
            parts.append("\n".join(concrete))
        if len(rebar) > 1:
            parts.append("\n".join(rebar))
        if len(tendon) > 1:
            parts.append("\n".join(tendon))
        return "\n\n".join(parts)

    # ==================================================================
    # SECTIONS
    # ==================================================================
    @classmethod
    def _sections(cls, project, used) -> str:
        secs = getattr(project, "sections", {}) or {}
        used_secs = used.get("sections", set())
        filtered = {n: s for n, s in secs.items() if n in used_secs}
        if not filtered:
            return ""

        lines = ['TABLE:  "FRAME SECTION PROPERTIES 01 - GENERAL"']

        for name, sec in filtered.items():
            mat = getattr(sec, "material", None)
            mat_name = getattr(mat, "name", "S275") if mat else "S275"

            pt = getattr(sec, "profile_type", None)
            pt_name = getattr(pt, "name", "RECT") if pt else "RECT"
            p = getattr(sec, "profile_params", {}) or {}

            h = p.get("h", p.get("d", 200.0))
            b = p.get("b", 200.0)
            tw = p.get("tw", p.get("t", 9.0))
            tf = p.get("tf", 15.0)

            if pt_name == "RECT":
                lines.append(
                    f'   SectionName={name}   Material={mat_name}   '
                    f'Shape=Rectangular   t3={cls._g(h)}   t2={cls._g(b)}   '
                    f'Color=Red   FromFile=No'
                )
            elif pt_name == "CIRCLE":
                lines.append(
                    f'   SectionName={name}   Material={mat_name}   '
                    f'Shape=Circle   t3={cls._g(h)}   '
                    f'Color=Red   FromFile=No'
                )
            elif pt_name == "PIPE":
                lines.append(
                    f'   SectionName={name}   Material={mat_name}   '
                    f'Shape=Pipe   t3={cls._g(h)}   tw={cls._g(tw)}   '
                    f'Color=Red   FromFile=No'
                )
            elif pt_name in ("TUBE", "BOX"):
                lines.append(
                    f'   SectionName={name}   Material={mat_name}   '
                    f'Shape=Box/Tube   t3={cls._g(h)}   t2={cls._g(b)}   '
                    f'tw={cls._g(tw)}   tf={cls._g(tw)}   '
                    f'Color=Red   FromFile=No'
                )
            elif pt_name == "I":
                lines.append(
                    f'   SectionName={name}   Material={mat_name}   '
                    f'Shape="I/Wide Flange"   t3={cls._g(h)}   t2={cls._g(b)}   '
                    f'tw={cls._g(tw)}   tf={cls._g(tf)}   '
                    f't2b={cls._g(b)}   tfb={cls._g(tf)}   '
                    f'Color=Red   FromFile=No'
                )
            elif pt_name == "T":
                lines.append(
                    f'   SectionName={name}   Material={mat_name}   '
                    f'Shape=Tee   t3={cls._g(h)}   t2={cls._g(b)}   '
                    f'tw={cls._g(tw)}   tf={cls._g(tf)}   '
                    f'Color=Red   FromFile=No'
                )
            elif pt_name in ("C", "CHANNEL"):
                lines.append(
                    f'   SectionName={name}   Material={mat_name}   '
                    f'Shape=Channel   t3={cls._g(h)}   t2={cls._g(b)}   '
                    f'tw={cls._g(tw)}   tf={cls._g(tf)}   '
                    f'Color=Red   FromFile=No'
                )
            elif pt_name == "L":
                lines.append(
                    f'   SectionName={name}   Material={mat_name}   '
                    f'Shape=Angle   t3={cls._g(h)}   t2={cls._g(b)}   '
                    f'tw={cls._g(tw)}   tf={cls._g(tw)}   '
                    f'Color=Red   FromFile=No'
                )
            else:
                # CUSTOM / SD → General (analiz özellikleri ile)
                area = p.get("Area", 0.0)
                i33 = p.get("I33", 0.0)
                i22 = p.get("I22", 0.0)
                j = p.get("J", 0.0)
                lines.append(
                    f'   SectionName={name}   Material={mat_name}   '
                    f'Shape="General"   t3=1   t2=1   '
                    f'Area={cls._g(area)}   I33={cls._g(i33)}   '
                    f'I22={cls._g(i22)}   J={cls._g(j)}   '
                    f'Color=Red   FromFile=No'
                )

        return "\n".join(lines)

    # ==================================================================
    # LINK PROPERTIES
    # ==================================================================
    @classmethod
    def _link_props(cls, project, used) -> str:
        props = getattr(project, "link_props", {}) or {}
        used_props = used.get("link_props", set())
        filtered = {n: p for n, p in props.items() if n in used_props}
        if not filtered:
            return ""

        lines = ['TABLE:  "LINK PROPERTY DEFINITIONS 01 - GENERAL"']
        for name, prop in filtered.items():
            pt = getattr(prop, "prop_type", None)
            pt_name = getattr(pt, "name", "LINEAR") if pt else "LINEAR"

            # Basit linear: tüm DOF serbest
            lines.append(
                f'   LinkProp={name}   LinkType={pt_name}   '
                f'DOF1=Yes   DOF2=Yes   DOF3=Yes   '
                f'DOF4=Yes   DOF5=Yes   DOF6=Yes'
            )
        return "\n".join(lines)

    # ==================================================================
    # LOAD PATTERNS
    # ==================================================================
    @classmethod
    def _load_patterns(cls, project, used, scene) -> str:
        patterns = getattr(project, "load_patterns", {}) or {}
        used_pats = used.get("patterns", set())

        filtered = {n: p for n, p in patterns.items() if n in used_pats}
        if not filtered:
            return ""

        lines = ['TABLE:  "LOAD PATTERN DEFINITIONS"']
        for name, lp in filtered.items():
            if not name or str(name).lower() == "nan":
                continue

            dt_raw = getattr(lp, "design_type", "Dead") or "Dead"
            dt = cls.DESIGN_TYPE_MAP.get(str(dt_raw).upper(), str(dt_raw))
            sw = getattr(lp, "self_wt_mult", 0.0) or 0.0

            extra = ""
            if dt == "Notional":
                base = "D" if "G" in str(name).upper() else "L"
                extra = (f'   NotBasePat={base}   NotRatio=0.002   '
                         f'NotDir="Global X"')
            elif dt in ("Quake", "Wind"):
                extra = "   AutoLoad=None"

            lines.append(
                f'   LoadPat={name}   DesignType={dt}   '
                f'SelfWtMult={cls._g(sw)}{extra}'
            )

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================================================================
    # LOAD CASES
    # ==================================================================
    @classmethod
    def _load_cases(cls, project, used, scene) -> str:
        cases = getattr(project, "load_cases", {}) or {}
        used_cases = used.get("cases", set())

        active = set()
        for name, lc in cases.items():
            if name in used_cases:
                active.add(name)
            if getattr(lc, "static_assignments", None):
                # Statik atamaları olan case'ler aktif sayılır
                # (pattern'lar zaten kullanılıyorsa)
                for sa in lc.static_assignments:
                    ln = getattr(sa, "load_name", None)
                    if ln and ln in used.get("patterns", set()):
                        active.add(name)
                        break

        filtered = {n: c for n, c in cases.items() if n in active}
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

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================================================================
    # COMBINATIONS
    # ==================================================================
    @classmethod
    def _combinations(cls, project, used) -> str:
        combos = getattr(project, "combinations", {}) or {}
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

            valid = []
            for it in items:
                cn = getattr(it, "case_or_pattern_name", None)
                sf = getattr(it, "scale_factor", 1.0)
                if cn and str(cn).lower() != "nan":
                    valid.append((cn, sf))
            if not valid:
                continue

            has_any = True
            for idx, (cn, sf) in enumerate(valid):
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
    # JOINT COORDINATES
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
            if label.startswith("W_NODE_") or label not in used_nodes:
                continue

            x = getattr(node, "x", 0.0)
            y = getattr(node, "y", 0.0)
            z = getattr(node, "z", 0.0)
            lines.append(
                f'   Joint={label}   CoordSys=GLOBAL   CoordType=Cartesian   '
                f'XorR={cls._g(x)}   Y={cls._g(y)}   Z={cls._g(z)}   SpecialJt=No'
            )

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================================================================
    # JOINT RESTRAINTS
    # ==================================================================
    @classmethod
    def _joint_restraints(cls, scene, used) -> str:
        nodes = getattr(scene, "nodes", {}) or {}
        used_nodes = used.get("nodes", set())

        lines = ['TABLE:  "JOINT RESTRAINT ASSIGNMENTS"']
        has_any = False

        for node in nodes.values():
            label = getattr(node, "label", None) or f"J{node.unique_id}"
            if label.startswith("W_NODE_") or label not in used_nodes:
                continue
            r = getattr(node, "restraint", None)
            if r is None:
                continue
            if not any(getattr(r, k, False) for k in
                       ("ux", "uy", "uz", "rx", "ry", "rz")):
                continue

            has_any = True
            vals = [
                "Yes" if getattr(r, k, False) else "No"
                for k in ("ux", "uy", "uz", "rx", "ry", "rz")
            ]
            lines.append(
                f'   Joint={label}   '
                f'U1={vals[0]}   U2={vals[1]}   U3={vals[2]}   '
                f'R1={vals[3]}   R2={vals[4]}   R3={vals[5]}'
            )

        return "\n".join(lines) if has_any else ""

    # ==================================================================
    # FRAME CONNECTIVITY
    # ==================================================================
    @classmethod
    def _frame_connectivity(cls, scene, used) -> str:
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

            j1 = getattr(ni, "label", None) or f"J{ni.unique_id}"
            j2 = getattr(nj, "label", None) or f"J{nj.unique_id}"
            lines.append(
                f'   Frame={label}   JointI={j1}   JointJ={j2}   IsCurved=No'
            )

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================================================================
    # FRAME SECTION ASSIGNMENTS
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

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================================================================
    # FRAME LOCAL AXES
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

            rot = getattr(frame, "rotation_deg", 0.0) or 0.0
            if abs(rot) < 1e-9:
                continue

            has_any = True
            lines.append(f'   Frame={label}   Angle={cls._g(rot)}')

        return "\n".join(lines) if has_any else ""

    # ==================================================================
    # FRAME LOADS - DISTRIBUTED
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

            try:
                frame_len = float(frame.get_length() or 1.0)
            except Exception:
                frame_len = 1.0

            for load in getattr(frame, "dist_loads", []) or []:
                pattern = getattr(load, "pattern_name", "")
                if not pattern or str(pattern).lower() == "nan":
                    continue

                coord_sys = cls._sap_coordsys(getattr(load, "coord_sys", "Local"))
                dir_raw = str(getattr(load, "load_dir", "2"))
                dir_name = cls.DIR_NAMES.get(dir_raw, dir_raw)
                is_rel = bool(getattr(load, "is_relative", True))

                segs = list(getattr(load, "segments", []) or [])
                if not segs:
                    continue

                for seg in segs:
                    a, b = seg.x1, seg.x2
                    va, vb = seg.q1, seg.q2
                    if b <= a:
                        continue

                    if is_rel:
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
    # AREA CONNECTIVITY
    # ==================================================================
    @classmethod
    def _area_connectivity(cls, scene, used) -> str:
        areas = getattr(scene, "areas", {}) or {}
        used_areas = used.get("areas", set())
        if not used_areas:
            return ""

        lines = ['TABLE:  "CONNECTIVITY - AREA"']
        for area in areas.values():
            label = getattr(area, "label", None) or f"A{area.unique_id}"
            if label not in used_areas:
                continue

            nodes = getattr(area, "nodes", []) or []
            if len(nodes) < 3:
                continue

            js = [
                getattr(nd, "label", None) or f"J{nd.unique_id}"
                for nd in nodes[:4]
            ]
            while len(js) < 4:
                js.append(js[-1])

            lines.append(
                f'   Area={label}   '
                f'Joint1={js[0]}   Joint2={js[1]}   '
                f'Joint3={js[2]}   Joint4={js[3]}'
            )

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================================================================
    # AREA SECTION PROPERTIES
    # ==================================================================
    @classmethod
    def _area_section_properties(cls, scene, used) -> str:
        """
        Sahnedeki area'ların 'section_name'lerinden benzersiz olanları
        AREA SECTION PROPERTIES tablosuna yaz. Her section için
        material ve thickness ilk rastlanan area'dan alınır.
        """
        areas = getattr(scene, "areas", {}) or {}
        used_areas = used.get("areas", set())
        if not used_areas:
            return ""

        # section_name → (material_name, thickness)
        sections: Dict[str, dict] = {}
        for area in areas.values():
            label = getattr(area, "label", None) or f"A{area.unique_id}"
            if label not in used_areas:
                continue

            sec_name = getattr(area, "section_name", "") or "PANEL1"
            if sec_name in sections:
                continue

            mat = getattr(area, "material", None)
            mat_name = getattr(mat, "name", "") if mat else ""
            thickness = getattr(area, "thickness", 0.0) or 0.0

            sections[sec_name] = {
                "material": mat_name,
                "thickness": thickness,
            }

        if not sections:
            return ""

        lines = ['TABLE:  "AREA SECTION PROPERTIES"']
        for sec_name, info in sorted(sections.items()):
            mat_name = info["material"] or "C30/37"
            th = info["thickness"]
            # Thickness mm cinsinden varsayılıyor (scene birimleri ile uyumlu)
            lines.append(
                f'   Section={sec_name}   Material={mat_name}   '
                f'AreaType=Shell   Type=Shell-Thin   '
                f'Thickness={cls._g(th)}'
            )

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================================================================
    # AREA SECTION ASSIGNMENTS
    # ==================================================================
    @classmethod
    def _area_section_assignments(cls, scene, used) -> str:
        areas = getattr(scene, "areas", {}) or {}
        used_areas = used.get("areas", set())
        if not used_areas:
            return ""

        lines = ['TABLE:  "AREA SECTION ASSIGNMENTS"']
        for area in areas.values():
            label = getattr(area, "label", None) or f"A{area.unique_id}"
            if label not in used_areas:
                continue

            sec_name = getattr(area, "section_name", "") or "PANEL1"
            lines.append(
                f'   Area={label}   Section={sec_name}   MatProp=Default'
            )

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================================================================
    # LINK CONNECTIVITY
    # ==================================================================
    @classmethod
    def _link_connectivity(cls, scene, used) -> str:
        links = getattr(scene, "links", {}) or {}
        used_links = used.get("links", set())
        if not used_links:
            return ""

        lines = ['TABLE:  "CONNECTIVITY - LINK"']
        for link in links.values():
            label = getattr(link, "label", None) or f"L{link.unique_id}"
            if label not in used_links:
                continue

            ni = getattr(link, "node_i", None)
            nj = getattr(link, "node_j", None)
            if not ni or not nj:
                continue

            j1 = getattr(ni, "label", None) or f"J{ni.unique_id}"
            j2 = getattr(nj, "label", None) or f"J{nj.unique_id}"
            lines.append(
                f'   Link={label}   JointI={j1}   JointJ={j2}   IsCurved=No'
            )

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================================================================
    # LINK PROPERTY ASSIGNMENTS
    # ==================================================================
    @classmethod
    def _link_assignments(cls, scene, used) -> str:
        links = getattr(scene, "links", {}) or {}
        used_links = used.get("links", set())
        if not used_links:
            return ""

        lines = ['TABLE:  "LINK PROPERTY ASSIGNMENTS"']
        for link in links.values():
            label = getattr(link, "label", None) or f"L{link.unique_id}"
            if label not in used_links:
                continue

            prop = getattr(link, "propname", "DefaultLink") or "DefaultLink"
            lines.append(f'   Link={label}   LinkProp={prop}')

        return "\n".join(lines) if len(lines) > 1 else ""

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
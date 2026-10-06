#domain/sect_mat.py

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
from tools.sap_connect import cSap
from domain.definition import LinkPropType, LinkProperty, Restraint, AreaSection, Material, PropAreaType, PropType, Section, SectionType, SymType, MatType
from domain.element import Element, Node, Link, Area, Frame


# ============================================================================
# HELPERS
# ============================================================================

def sap_color_to_rgb(color: int) -> Tuple[float, float, float]:
    """
    SAP2000 integer renk değerini 0..1 aralığında RGB tuple'a çevirir.

    Örnek:
        65280    -> (0.0, 1.0, 0.0)
        8421504  -> (0.502, 0.502, 0.502)
    """
    color = int(color)

    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF

    return r / 255.0, g / 255.0, b / 255.0


def get_materials(sap) -> Dict[str, Material]:
    """SAP2000 malzemelerini CAD4 Material nesnelerine çevirir."""

    sap_model = sap.SapModel

    number_names, names, ret = sap_model.PropMaterial.GetNameList()

    if ret != 0:
        raise RuntimeError(
            f"PropMaterial.GetNameList failed. ret={ret}"
        )

    materials: Dict[str, Material] = {}

    for name in names:

        # ------------------------------------------------------------------
        # Material basic information
        # ------------------------------------------------------------------

        mat_type_raw, color_raw, _, _, ret = (
            sap_model.PropMaterial.GetMaterial(name)
        )

        if ret != 0:
            print(f"WARNING: GetMaterial failed: {name}, ret={ret}")
            continue

        # ------------------------------------------------------------------
        # Symmetry type
        # ------------------------------------------------------------------

        mat_type_raw, sym_type_raw, ret = (
            sap_model.PropMaterial.GetTypeOAPI(name)
        )

        if ret != 0:
            print(f"WARNING: GetTypeOAPI failed: {name}, ret={ret}")
            continue

        try:
            mat_type = MatType(mat_type_raw)
        except ValueError:
            print(
                f"WARNING: Unknown material type "
                f"{mat_type_raw} for '{name}'"
            )
            mat_type = MatType.NODESIGN

        try:
            sym_type = SymType(sym_type_raw)
        except ValueError:
            print(
                f"WARNING: Unknown symmetry type "
                f"{sym_type_raw} for '{name}'"
            )
            continue

        # ------------------------------------------------------------------
        # Weight / mass density
        # ------------------------------------------------------------------

        weight, mass, ret = (
            sap_model.PropMaterial.GetWeightAndMass(name)
        )

        if ret != 0:
            print(
                f"WARNING: GetWeightAndMass failed: "
                f"{name}, ret={ret}"
            )
            mass = 0.0

        # ------------------------------------------------------------------
        # Mechanical properties
        # ------------------------------------------------------------------

        E1 = E2 = E3 = 0.0
        G12 = G13 = G23 = 0.0
        nu12 = nu13 = nu23 = 0.0

        if sym_type == SymType.ISOTROPIC:

            E, nu, alpha, G, ret = (
                sap_model.PropMaterial.GetMPIsotropic(name)
            )

            if ret != 0:
                print(
                    f"WARNING: GetMPIsotropic failed: "
                    f"{name}, ret={ret}"
                )
                continue

            E1 = E2 = E3 = float(E)
            G12 = G13 = G23 = float(G)
            nu12 = nu13 = nu23 = float(nu)

        elif sym_type == SymType.ORTHOTROPIC:

            E, nu, alpha, G, ret = (
                sap_model.PropMaterial.GetMPOrthotropic(name)
            )

            if ret != 0:
                print(
                    f"WARNING: GetMPOrthotropic failed: "
                    f"{name}, ret={ret}"
                )
                continue

            E1, E2, E3 = map(float, E[:3])
            nu12, nu13, nu23 = map(float, nu[:3])
            G12, G13, G23 = map(float, G[:3])

        elif sym_type == SymType.ANISOTROPIC:

            E, nu, alpha, G, ret = (
                sap_model.PropMaterial.GetMPAnisotropic(name)
            )

            if ret != 0:
                print(
                    f"WARNING: GetMPAnisotropic failed: "
                    f"{name}, ret={ret}"
                )
                continue

            # CAD4 şu anda tam anizotropik matris tutmuyor.
            # İlk üç normal modül ve ilk üç Poisson/kayma değeri
            # kullanılabilir kısmı temsil ediyor.
            E1, E2, E3 = map(float, E[:3])
            nu12, nu13, nu23 = map(float, nu[:3])
            G12, G13, G23 = map(float, G[:3])

        elif sym_type == SymType.UNIAXIAL:

            E, alpha, ret = (
                sap_model.PropMaterial.GetMPUniaxial(name)
            )

            if ret != 0:
                print(
                    f"WARNING: GetMPUniaxial failed: "
                    f"{name}, ret={ret}"
                )
                continue

            E1 = float(E)

        # ------------------------------------------------------------------
        # Color
        # ------------------------------------------------------------------

        color = sap_color_to_rgb(color_raw)

        # ------------------------------------------------------------------
        # Material object
        # ------------------------------------------------------------------

        materials[name] = Material(
            name=name,
            mat_type=mat_type,
            color=color,

            E1=E1,
            E2=E2,
            E3=E3,

            G12=G12,
            G13=G13,
            G23=G23,

            nu12=nu12,
            nu13=nu13,
            nu23=nu23,

            # Weight değil, mass density.
            density=float(mass),
        )

    return materials


# ============================================================================
# SECTION IMPORT
# ============================================================================

def get_all_sections(
    sap,
    materials: Optional[Dict[str, Material]] = None,
) -> list[Section]:

    sap_model = sap.SapModel

    if materials is None:
        materials = get_materials(sap)

    number_names, names, ret = sap_model.PropFrame.GetNameList()

    if ret != 0:
        raise RuntimeError(
            f"PropFrame.GetNameList failed. ret={ret}"
        )

    sections: Dict[Section] = {}

    for name in names:

        # --------------------------------------------------------------
        # SAP section type
        # --------------------------------------------------------------

        prop_type_raw, ret = sap_model.PropFrame.GetTypeOAPI(name)

        if ret != 0:
            print(
                f"WARNING: GetTypeOAPI failed: "
                f"{name}, ret={ret}"
            )
            continue

        try:
            prop_type = PropType(prop_type_raw)
        except ValueError:
            print(
                f"WARNING: Unknown PropType={prop_type_raw} "
                f"for section '{name}'"
            )
            continue

        # --------------------------------------------------------------
        # Derived section properties
        # --------------------------------------------------------------

        (
            area,
            As2,
            As3,
            torsion,
            I22,
            I33,
            S22,
            S33,
            Z22,
            Z33,
            R22,
            R33,
            ret,
        ) = sap_model.PropFrame.GetSectProps(name)

        if ret != 0:
            print(
                f"WARNING: GetSectProps failed: "
                f"{name}, ret={ret}"
            )

        # --------------------------------------------------------------
        # Section-specific data
        # --------------------------------------------------------------

        section = None

        # ==============================================================
        # I
        # ==============================================================

        if prop_type == PropType.I:

            (
                FileName,
                MatProp,
                t3,
                t2,
                tf,
                tw,
                t2b,
                tfb,
                FilletRadius,
                Color,
                *_,
            ) = sap_model.PropFrame.GetISection_1(name)

            section = Section(
                name=name,
                profile_type=SectionType.I,
                profile_params={
                    "t3": float(t3),
                    "t2": float(t2),
                    "tf": float(tf),
                    "tw": float(tw),
                    "t2b": float(t2b),
                    "tfb": float(tfb),
                    "fillet_radius": float(FilletRadius),
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # CHANNEL
        # ==============================================================

        elif prop_type == PropType.Channel:

            (
                FileName,
                MatProp,
                t3,
                t2,
                tf,
                tw,
                FilletRadius,
                MirrorAbout2,
                Color,
                *_,
            ) = sap_model.PropFrame.GetChannel_2(name)

            section = Section(
                name=name,
                profile_type=SectionType.CHANNEL,
                profile_params={
                    "t3": float(t3),
                    "t2": float(t2),
                    "tf": float(tf),
                    "tw": float(tw),
                    "fillet_radius": float(FilletRadius),
                    "mirror_about_2": bool(MirrorAbout2),
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # T
        # ==============================================================

        elif prop_type == PropType.T:

            (
                FileName,
                MatProp,
                t3,
                t2,
                tf,
                tw,
                FilletRadius,
                MirrorAbout3,
                Color,
                *_,
            ) = sap_model.PropFrame.GetTee_1(name)

            section = Section(
                name=name,
                profile_type=SectionType.T,
                profile_params={
                    "t3": float(t3),
                    "t2": float(t2),
                    "tf": float(tf),
                    "tw": float(tw),
                    "fillet_radius": float(FilletRadius),
                    "mirror_about_3": bool(MirrorAbout3),
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # ANGLE
        # ==============================================================

        elif prop_type == PropType.Angle:

            (
                FileName,
                MatProp,
                t3,
                t2,
                tf,
                tw,
                FilletRadius,
                Color,
                *_,
            ) = sap_model.PropFrame.GetAngle_1(name)

            section = Section(
                name=name,
                profile_type=SectionType.L,
                profile_params={
                    "t3": float(t3),
                    "t2": float(t2),
                    "tf": float(tf),
                    "tw": float(tw),
                    "fillet_radius": float(FilletRadius),
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # DOUBLE ANGLE
        # ==============================================================

        elif prop_type == PropType.DblAngle:

            (
                FileName,
                MatProp,
                t3,
                t2,
                tf,
                tw,
                dis,
                FilletRadius,
                MirrorAbout3,
                Color,
                *_,
            ) = sap_model.PropFrame.GetDblAngle_2(name)

            section = Section(
                name=name,
                profile_type=SectionType.L,
                profile_params={
                    "t3": float(t3),
                    "t2": float(t2),
                    "tf": float(tf),
                    "tw": float(tw),
                    "distance": float(dis),
                    "fillet_radius": float(FilletRadius),
                    "mirror_about_3": bool(MirrorAbout3),
                    "double_angle": True,
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # BOX / TUBE
        # ==============================================================

        elif prop_type == PropType.Box:

            (
                FileName,
                MatProp,
                t3,
                t2,
                tf,
                tw,
                Radius,
                Color,
                *_,
            ) = sap_model.PropFrame.GetTube_1(name)

            section = Section(
                name=name,
                profile_type=SectionType.BOX,
                profile_params={
                    "t3": float(t3),
                    "t2": float(t2),
                    "tf": float(tf),
                    "tw": float(tw),
                    "radius": float(Radius),
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # PIPE
        # ==============================================================

        elif prop_type == PropType.Pipe:

            (
                FileName,
                MatProp,
                t3,
                tw,
                Color,
                *_,
            ) = sap_model.PropFrame.GetPipe(name)

            section = Section(
                name=name,
                profile_type=SectionType.PIPE,
                profile_params={
                    "t3": float(t3),
                    "tw": float(tw),
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # RECTANGLE
        # ==============================================================

        elif prop_type == PropType.Rectangular:

            (
                FileName,
                MatProp,
                t3,
                t2,
                Color,
                *_,
            ) = sap_model.PropFrame.GetRectangle(name)

            section = Section(
                name=name,
                profile_type=SectionType.RECT,
                profile_params={
                    "t3": float(t3),
                    "t2": float(t2),
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # CIRCLE
        # ==============================================================

        elif prop_type == PropType.Circle:

            (
                FileName,
                MatProp,
                t3,
                Color,
                *_,
            ) = sap_model.PropFrame.GetCircle(name)

            section = Section(
                name=name,
                profile_type=SectionType.CIRCLE,
                profile_params={
                    "t3": float(t3),
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # GENERAL
        # ==============================================================

        elif prop_type == PropType.General:

            (
                FileName,
                MatProp,
                t3,
                t2,
                Area_,
                As2_,
                As3_,
                Torsion_,
                I22_,
                I33_,
                S22_,
                S33_,
                Z22_,
                Z33_,
                R22_,
                R33_,
                Color,
                *_,
            ) = sap_model.PropFrame.GetGeneral(name)

            section = Section(
                name=name,
                profile_type=SectionType.CUSTOM,
                profile_params={
                    "t3": float(t3),
                    "t2": float(t2),
                    "area": float(Area_),
                    "as2": float(As2_),
                    "as3": float(As3_),
                    "torsion": float(Torsion_),
                    "i22": float(I22_),
                    "i33": float(I33_),
                    "s22": float(S22_),
                    "s33": float(S33_),
                    "z22": float(Z22_),
                    "z33": float(Z33_),
                    "r22": float(R22_),
                    "r33": float(R33_),
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # DOUBLE CHANNEL
        # ==============================================================

        elif prop_type == PropType.DbChannel:

            (
                FileName,
                MatProp,
                t3,
                t2,
                tf,
                tw,
                dis,
                FilletRadius,
                Color,
                *_,
            ) = sap_model.PropFrame.GetDblChannel_1(name)

            section = Section(
                name=name,
                profile_type=SectionType.CHANNEL,
                profile_params={
                    "t3": float(t3),
                    "t2": float(t2),
                    "tf": float(tf),
                    "tw": float(tw),
                    "distance": float(dis),
                    "fillet_radius": float(FilletRadius),
                    "double_channel": True,
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # AUTO SELECT
        # ==============================================================

        elif prop_type == PropType.Auto:

            (
                NumberItems,
                SectName,
                AutoStartSection,
                Notes,
                GUID,
                *_,
            ) = sap_model.PropFrame.GetAutoSelectSteel(name)

            # Auto Select gerçek bir fiziksel kesit değildir.
            # Bu nedenle CAD4 Section listesine geometrik bir Section
            # olarak eklemiyoruz.
            print(
                f"INFO: Auto Select skipped: {name} "
                f"({NumberItems} sections)"
            )

            continue

        # ==============================================================
        # SECTION DESIGNER
        # ==============================================================

        elif prop_type == PropType.SD:

            (
                MatProp,
                NumberItems,
                ShapeName,
                MyType,
                DesignType,
                Color,
                *_,
            ) = sap_model.PropFrame.GetSDSection(name)

            section = Section(
                name=name,
                profile_type=SectionType.CUSTOM,
                profile_params={
                    "number_items": float(NumberItems),
                    "shape_names": ShapeName,
                    "shape_types": MyType,
                    "design_type": DesignType,
                    "section_designer": True,
                },
                material=materials.get(MatProp),
                color=sap_color_to_rgb(Color),
            )

        # ==============================================================
        # OTHER SAP TYPES
        # ==============================================================

        else:

            print(
                f"WARNING: Section type not implemented: "
                f"{name} -> {prop_type.name}"
            )

            # Fiziksel geometrisini bilmiyorsak yanlış bir Section
            # üretmeyelim.
            continue

        # --------------------------------------------------------------
        # Add section
        # --------------------------------------------------------------

        if section is not None:
            sections[section.name] = section

    return sections

def get_area_sections(
    sap,
    materials: Optional[Dict[str, Material]] = None,
) -> Dict[str, AreaSection]:

    sap_model = sap.SapModel

    if materials is None:
        materials = get_materials(sap)

    number_names, names, ret = (
        sap_model.PropArea.GetNameList()
    )

    if ret != 0:
        raise RuntimeError(
            f"PropArea.GetNameList failed. ret={ret}"
        )

    area_sections: Dict[str, AreaSection] = {}

    for name in names:

        # ----------------------------------------------------------
        # Modifiers
        # ----------------------------------------------------------

        values, ret = (
            sap_model.PropArea.GetModifiers(name)
        )

        if ret != 0:
            print(
                f"WARNING: GetModifiers failed: "
                f"{name}, ret={ret}"
            )
            continue

        # ----------------------------------------------------------
        # Property type
        # ----------------------------------------------------------

        prop_type_raw, ret = (
            sap_model.PropArea.GetTypeOAPI(name)
        )

        if ret != 0:
            print(
                f"WARNING: GetTypeOAPI failed: "
                f"{name}, ret={ret}"
            )
            continue

        try:
            prop_type = PropAreaType(prop_type_raw)
        except ValueError:
            print(
                f"WARNING: Unknown PropAreaType="
                f"{prop_type_raw} for '{name}'"
            )
            continue

        # ----------------------------------------------------------
        # Defaults
        # ----------------------------------------------------------

        thickness = 0.0
        mat_prop = None
        params = {}

        # ----------------------------------------------------------
        # SHELL
        # ----------------------------------------------------------

        if prop_type_raw in (0, 1):

            result = sap_model.PropArea.GetShell_1(name)

            (
                ShellType,
                IncludeDrillingDOF,
                MatProp,
                MatAng,
                Thickness,
                Bending,
                Color,
                *_,
            ) = result

            mat_prop = MatProp
            thickness = float(Thickness)

            params = {
                "shell_type": ShellType,
                "include_drilling_dof": IncludeDrillingDOF,
                "material_angle": MatAng,
                "bending": Bending,
                "color": Color,
            }

        # ----------------------------------------------------------
        # PLANE
        # ----------------------------------------------------------

        elif prop_type_raw == 2:

            result = sap_model.PropArea.GetPlane(name)

            (
                MyType,
                MatProp,
                MatAng,
                Thickness,
                Incompatible,
                Color,
                *_,
            ) = result

            mat_prop = MatProp
            thickness = float(Thickness)

            params = {
                "plane_type": MyType,
                "material_angle": MatAng,
                "incompatible": Incompatible,
                "color": Color,
            }

        # ----------------------------------------------------------
        # ASOLID
        # ----------------------------------------------------------

        elif prop_type_raw == 3:

            result = sap_model.PropArea.GetAsolid(name)

            (
                MatProp,
                MatAng,
                Arc,
                Incompatible,
                CSys,
                Color,
                *_,
            ) = result

            mat_prop = MatProp

            params = {
                "material_angle": MatAng,
                "arc": Arc,
                "incompatible": Incompatible,
                "coordinate_system": CSys,
                "color": Color,
            }

        else:
            print(
                f"WARNING: Area property type not implemented: "
                f"{name} -> {prop_type}"
            )
            continue

        # ----------------------------------------------------------
        # Material
        # ----------------------------------------------------------

        material = materials.get(mat_prop)

        if material is None and mat_prop:
            print(
                f"WARNING: Material '{mat_prop}' "
                f"not found for area '{name}'"
            )

        # ----------------------------------------------------------
        # Modifier values
        # ----------------------------------------------------------

        if len(values) < 10:
            print(
                f"WARNING: Invalid modifier count for "
                f"'{name}': {len(values)}"
            )
            continue

        area_section = AreaSection(
            name=name,
            prop_type=prop_type,
            material=material,
            thickness=thickness,

            membrane_f11=float(values[0]),
            membrane_f22=float(values[1]),
            membrane_f12=float(values[2]),

            bending_m11=float(values[3]),
            bending_m22=float(values[4]),
            bending_m12=float(values[5]),

            shear_v13=float(values[6]),
            shear_v23=float(values[7]),

            mass=float(values[8]),
            weight=float(values[9]),

            params=params,
        )

        area_sections[name] = area_section

    return area_sections



def get_link_properties(sap) -> Dict[str, LinkProperty]:
    """
    SAP2000 PropLink tanımlarını okur.
    """

    sap_model = sap.SapModel

    NumberNames, MyName, ret = sap_model.PropLink.GetNameList()

    link_props = {}

    for name in MyName:

        PropType, ret = sap_model.PropLink.GetTypeOAPI(name)

        dof = ()
        fixed = ()
        ke = ()
        ce = ()
        params = {}

        if PropType == 1:
            ret = sap_model.PropLink.GetLinear(name)

            (
                DOF,
                Fixed,
                Ke,
                Ce,
                dj2,
                dj3,
                KeCoupled,
                CeCoupled,
                _,
                _,
                _,
            ) = ret

            params = {
                "dj2": dj2,
                "dj3": dj3,
                "ke_coupled": KeCoupled,
                "ce_coupled": CeCoupled,
            }

        elif PropType == 2:
            ret = sap_model.PropLink.GetDamper(name)

            (
                DOF,
                Fixed,
                NonLinear,
                Ke,
                Ce,
                k,
                c,
                cexp,
                dj2,
                dj3,
                _,
                _,
                _,
            ) = ret

            params = {
                "nonlinear": NonLinear,
                "k": k,
                "c": c,
                "cexp": cexp,
                "dj2": dj2,
                "dj3": dj3,
            }

        elif PropType == 3:
            ret = sap_model.PropLink.GetGap(name)

            (
                DOF,
                Fixed,
                NonLinear,
                Ke,
                Ce,
                k,
                dis,
                dj2,
                dj3,
                _,
                _,
                _,
            ) = ret

            params = {
                "nonlinear": NonLinear,
                "k": k,
                "dis": dis,
                "dj2": dj2,
                "dj3": dj3,
            }

        elif PropType == 4:
            ret = sap_model.PropLink.GetHook(name)

            (
                DOF,
                Fixed,
                NonLinear,
                Ke,
                Ce,
                k,
                dis,
                dj2,
                dj3,
                _,
                _,
                _,
            ) = ret

            params = {
                "nonlinear": NonLinear,
                "k": k,
                "dis": dis,
                "dj2": dj2,
                "dj3": dj3,
            }

        elif PropType == 5:
            ret = sap_model.PropLink.GetPlasticWen(name)

            (
                DOF,
                Fixed,
                NonLinear,
                Ke,
                Ce,
                k,
                Yield,
                Ratio,
                exp,
                dj2,
                dj3,
                _,
                _,
                _,
            ) = ret

            params = {
                "nonlinear": NonLinear,
                "k": k,
                "yield": Yield,
                "ratio": Ratio,
                "exp": exp,
                "dj2": dj2,
                "dj3": dj3,
            }

        elif PropType == 6:
            ret = sap_model.PropLink.GetRubberIsolator(name)

            (
                DOF,
                Fixed,
                NonLinear,
                Ke,
                Ce,
                k,
                Yield,
                Ratio,
                dj2,
                dj3,
                _,
                _,
                _,
            ) = ret

            params = {
                "nonlinear": NonLinear,
                "k": k,
                "yield": Yield,
                "ratio": Ratio,
                "dj2": dj2,
                "dj3": dj3,
            }

        elif PropType == 7:
            ret = sap_model.PropLink.GetFrictionIsolator(name)

            (
                DOF,
                Fixed,
                NonLinear,
                Ke,
                Ce,
                k,
                Slow,
                Fast,
                Rate,
                Radius,
                Damping,
                dj2,
                dj3,
                _,
                _,
                _,
            ) = ret

            params = {
                "nonlinear": NonLinear,
                "k": k,
                "slow": Slow,
                "fast": Fast,
                "rate": Rate,
                "radius": Radius,
                "damping": Damping,
                "dj2": dj2,
                "dj3": dj3,
            }

        elif PropType == 8:
            ret = sap_model.PropLink.GetMultiLinearElastic(name)

            (
                DOF,
                Fixed,
                NonLinear,
                Ke,
                Ce,
                dj2,
                dj3,
                _,
                _,
                _,
            ) = ret

            params = {
                "nonlinear": NonLinear,
                "dj2": dj2,
                "dj3": dj3,
            }

        elif PropType == 9:
            ret = sap_model.PropLink.GetMultiLinearPlastic(name)

            (
                DOF,
                Fixed,
                NonLinear,
                Ke,
                Ce,
                dj2,
                dj3,
                _,
                _,
                _,
            ) = ret

            params = {
                "nonlinear": NonLinear,
                "dj2": dj2,
                "dj3": dj3,
            }

        elif PropType == 10:
            ret = sap_model.PropLink.GetTCFrictionIsolator(name)

            (
                DOF,
                Fixed,
                NonLinear,
                Ke,
                Ce,
                k,
                Slow,
                Fast,
                Rate,
                Radius,
                SlowT,
                FastT,
                RateT,
                kt,
                dis,
                dist,
                Damping,
                dj2,
                dj3,
                _,
                _,
                _,
            ) = ret

            params = {
                "nonlinear": NonLinear,
                "k": k,
                "slow": Slow,
                "fast": Fast,
                "rate": Rate,
                "radius": Radius,
                "slow_t": SlowT,
                "fast_t": FastT,
                "rate_t": RateT,
                "kt": kt,
                "dis": dis,
                "dist": dist,
                "damping": Damping,
                "dj2": dj2,
                "dj3": dj3,
            }

        else:
            print(f"Unsupported LinkPropType: {PropType} ({name})")
            continue

        link_props[name] = LinkProperty(
            name=name,
            prop_type=LinkPropType(PropType),
            dof=tuple(DOF),
            fixed=tuple(Fixed),
            ke=tuple(Ke),
            ce=tuple(Ce),
            params=params,
        )

    return link_props

def get_links(sap, link_props=None):
    if link_props is None:
        link_props = get_link_properties(sap)

    sap_model = sap.SapModel

    selected = sap.get_selected_objects()
    links = [o for o in selected if o["type"] == "Link"]

    result = []

    for item in links:
        name = item["name"]

        PropName, ret = sap_model.LinkObj.GetProperty(name)
        Point1, Point2, ret = sap_model.LinkObj.GetPoints(name)

        x, y, z, ret = sap_model.PointObj.GetCoordCartesian(Point1)
        node_i = Node(x, y, z, Point1)

        x, y, z, ret = sap_model.PointObj.GetCoordCartesian(Point2)
        node_j = Node(x, y, z, Point2)

        link = Link(
            node_i=node_i,
            node_j=node_j,
            propname=PropName,
            label=name,
        )

        result.append(link)

    return result

def get_nodes(sap) -> dict[str, Node]:
    sap_model = sap.SapModel

    selected = sap.get_selected_objects()
    points = [o for o in selected if o["type"] == "Point"]

    nodes = {}

    for point in points:
        name = point["name"]

        x, y, z, ret = sap_model.PointObj.GetCoordCartesian(name)

        value, ret = sap_model.PointObj.GetRestraint(name)
        restraint = Restraint.from_list(value)

        mass, ret = sap_model.PointObj.GetMass(name)

        spring, ret = sap_model.PointObj.GetSpring(name)

        nodes[name] = Node(
            x=x,
            y=y,
            z=z,
            label=name,
            restraint=restraint,
            mass=mass,
            spring=spring,
        )

    return nodes







# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    from tools.sap_connect import cSap
    sap = cSap()

    materials = get_materials(sap)
    sections = get_all_sections(sap, materials)

    # Section'ları isimlerine göre indeksle
    section_map = {
        section.name: section
        for section in sections
    }

    link_props = get_link_properties(sap)

    node_data = get_nodes(sap)

    print("\n----- NODES -----")

    for name, data in node_data.items():
        print(
            name,
            data.x,
            data.y,
            data.z,
            "restraint=", data.restraint,
            "mass=", data.mass,
            "spring=", data.spring,
        )

    print("\n----- LINK PROPERTIES -----")
    for name, prop in link_props.items():
        print(name, prop)


    links = get_links(sap, link_props)

    print("\n----- SELECTED LINKS -----")

    for link in links:
        prop = link_props.get(link.propname)

        print(
            f"{link.label}: "
            f"{link.node_i.label} -> {link.node_j.label}, "
            f"Property={link.propname}, "
            f"Type={prop.prop_type if prop else None}"
        )
    selected = sap.get_selected_objects()


    frames = [
        obj
        for obj in selected
        if obj["type"] == "Frame"
    ]

    print()
    print("SELECTED FRAMES")
    print("-" * 70)

    for frame in frames:

        frame_name = frame["name"]

        # SAP'den Frame'in section property adını al
        section_name, SAuto, ret = sap.SapModel.FrameObj.GetSection(frame_name)

        if ret != 0:
            print(
                f"Frame : {frame_name}"
                f" -> GetSection failed, ret={ret}"
            )
            continue

        print(f"Frame   : {frame_name}")
        print(f"Section : {section_name}")

        section = section_map.get(section_name)

        if section is None:
            print(
                f"  Section '{section_name}' "
                f"listede bulunamadı."
            )
            continue

        print(f"  Type       : {section.profile_type}")
        print(f"  Parameters : {section.profile_params}")

        if section.material:
            print(f"  Material   : {section.material.name}")

        print(f"  Color      : {section.color}")
        print()


    area_sections = get_area_sections(
        sap,
        materials=materials,
    )

    print("\n----- ALL AREA SECTIONS -----")

    for name, section in area_sections.items():

        print(
            f"{name}: "
            f"type={section.prop_type}, "
            f"thickness={section.thickness}, "
            f"material="
            f"{section.material.name if section.material else None}"
        )

        print(
            f"  modifiers={section.modifiers}"
        )

    print("\n----- SELECTED AREAS -----")

    

    areas = [
        obj
        for obj in selected
        if obj["type"] == "Area"
    ]

    for area in areas:

        area_name = area["name"]

        prop_name, ret = (
            sap.SapModel.AreaObj.GetProperty(area_name)
        )

        if ret != 0:
            print(
                f"{area_name}: GetProperty failed, "
                f"ret={ret}"
            )
            continue

        section = area_sections.get(prop_name)

        print()
        print(f"Area    : {area_name}")
        print(f"Property: {prop_name}")

        if section is None:
            print("  Area section bulunamadı.")
            continue

        print(f"  Type      : {section.prop_type}")
        print(f"  Thickness : {section.thickness}")
        print(
            f"  Material  : "
            f"{section.material.name if section.material else None}"
        )
        print(f"  Modifiers : {section.modifiers}")
# tools/debug_modal_full.py
"""
Modal debug — katman katman teşhis + SAP2000 karşılaştırma.

Kullanım:
    python -m tools.debug_modal_full [s2k_dosyası] [sap2000_rapor.txt]

Örnek:
    python -m tools.debug_modal_full tests/simple_ba1.s2k tests/sap2000_simple_ba1.txt

Bölümler
--------
1. Model özeti
2. DOF atama ve mesnetler
3. Kütle (mass_assembly) + SAP2000 joint mass karşılaştırma
4. Rijitlik (stiffness_assembly) + lokal frame testi
5. Mesnetli DOF'lar
6. Modal çözüm + K/M teşhisi + SAP2000 period karşılaştırma
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.project import Project
from core.analysis.mass_assembly import build_mass
from core.analysis.stiffness_assembly import (
    build_stiffness,
    local_stiffness,
    transformation_matrix,
)
from core.analysis.solver import StructuralSolver
from core.analysis.structuralanalysis import _collect_fixed_dofs


# ============================================================================
# YARDIMCILAR
# ============================================================================
def section(title: str) -> None:
    print(f"\n--- {title} ---")


def hdr(s: str, width: int = 28) -> str:
    return f"  {s:<{width}}"


def safe(fn, label: str):
    """Bölümü izole çalıştır; hata olsa da diğer bölümler devam etsin."""
    try:
        fn()
    except Exception:
        print(f"  [{label}] HATA:")
        traceback.print_exc()


# ============================================================================
# 1) MODEL ÖZETİ
# ============================================================================
def report_model(scn) -> None:
    section("Model")
    print(hdr(f"Node: {len(scn.nodes)}"))
    print(hdr(f"Frame: {len(scn.frames)}"))
    print(hdr(f"Area: {len(scn.areas)}"))


# ============================================================================
# 2) DOF ATAMA ve MESNETLER
# ============================================================================
def report_dofs_and_restraints(scn) -> None:
    section("DOF atama ve mesnetler")

    n_with = n_none = 0
    fixed_all = free_all = partial = 0

    for n in scn.nodes.values():
        dofs = getattr(n, "dof_indices", None)
        if dofs is None or all(d is None for d in dofs):
            n_none += 1
        else:
            n_with += 1

        r = getattr(n, "restraint", None)
        if r is None:
            free_all += 1
            continue
        cnt = sum(1 for d in ("ux", "uy", "uz", "rx", "ry", "rz")
                  if getattr(r, d, False))
        if cnt == 6:
            fixed_all += 1
        elif cnt == 0:
            free_all += 1
        else:
            partial += 1

    print(hdr(f"Dolu DOF: {n_with}"))
    print(hdr(f"Boş DOF: {n_none}"))
    print(hdr(f"Tamamen sabit: {fixed_all}"))
    print(hdr(f"Tamamen serbest: {free_all}"))
    print(hdr(f"Kısmi: {partial}"))


# ============================================================================
# 3) KÜTLE (+ SAP2000 karşılaştırma)
# ============================================================================
def report_mass(scn, p, sap_file: str | None = None):
    section("Kütle (mass_assembly)")

    mass = build_mass(scn, p, n_live=0.3)

    print(hdr(f"self: {mass.total_self_kg:.2f} kg"))
    print(hdr(f"dead: {mass.total_dead_kg:.2f} kg"))
    print(hdr(f"live: {mass.total_live_kg:.2f} kg"))
    print(hdr(f"toplam: {mass.total_kg:.2f} kg"))
    print(hdr(f"node_masses: {sum(mass.node_masses.values()):.2f} kg"))
    print(hdr(f"M diag[::6] ilk5: {np.diag(mass.M_global)[::6][:5]}"))
    print(hdr(f"Sıfır kütleli node: {sum(1 for m in mass.node_masses.values() if m <= 0)}"))

    if sap_file:
        from tools.sap2000_mass_compare import compare_with_sap2000
        compare_with_sap2000(sap_file, scn, mass)

    return mass


# ============================================================================
# 4) RİJİTLİK
# ============================================================================
def report_stiffness(scn, p):
    section("Rijitlik (stiffness_assembly)")

    stiff = build_stiffness(scn, p)
    K = stiff.K_global

    print(hdr(f"frame_count: {stiff.frame_count}"))
    print(hdr(f"skipped: {len(stiff.skipped)}"))
    print(hdr(f"warnings: {len(stiff.warnings)}"))
    print(hdr(f"K simetri: {np.allclose(K, K.T)}"))
    print(hdr(f"K diag[::6] ilk5: {np.diag(K)[::6][:5]}"))
    print(hdr(f"K max: {np.max(np.abs(K)):.2e}"))
    print(hdr(f"K min diag: {np.min(np.diag(K)):.2e}"))

    # Düğüm 0 köşegenleri
    print(hdr(f"K[0,0] UX: {K[0,0]:.0f}"))
    print(hdr(f"K[1,1] UY: {K[1,1]:.0f}"))
    print(hdr(f"K[2,2] UZ: {K[2,2]:.0f}"))
    print(hdr(f"K[3,3] RX: {K[3,3]:.2e}"))
    print(hdr(f"K[4,4] RY: {K[4,4]:.2e}"))
    print(hdr(f"K[5,5] RZ: {K[5,5]:.2e}"))

    return stiff


# ============================================================================
# 5) LOKAL FRAME
# ============================================================================
def report_local_frame(scn) -> None:
    section("Lokal frame matrisi (ilk frame)")

    f = list(scn.frames.values())[0]
    sec = f.section
    mat = sec.material
    pp = sec.profile_params

    L = f.get_length()
    E, G = mat.E1, mat.G12

    A   = pp.get("Area", 0.0) * pp.get("AMod", 1.0)
    J   = pp.get("J", 0.0)    * pp.get("JMod", 1.0)
    I33 = pp.get("I33", 0.0)  * pp.get("I3Mod", 1.0)
    I22 = pp.get("I22", 0.0)  * pp.get("I2Mod", 1.0)
    AS2 = pp.get("AS2", A)    * pp.get("A2Mod", 1.0)
    AS3 = pp.get("AS3", A)    * pp.get("A3Mod", 1.0)

    print(hdr(f"label={f.label}  L={L:.0f} mm"))
    print(hdr(f"section={sec.name}"))
    print(hdr(f"E={E:.0f} MPa  G={G:.0f} MPa"))
    print(hdr(f"A={A:.0f} mm²"))
    print(hdr(f"I33={I33:.3e}  I22={I22:.3e}  J={J:.3e}"))
    print(hdr(f"release_i={getattr(f, 'release_i', None)}"))
    print(hdr(f"release_j={getattr(f, 'release_j', None)}"))

    k_loc = local_stiffness(
        E, G, A, J, I33, I22, AS2, AS3, L,
        getattr(f, "release_i", None),
        getattr(f, "release_j", None),
    )

    tests = [
        ("k[0,0]  EA/L",      k_loc[0, 0], E * A / L),
        ("k[3,3]  GJ/L",      k_loc[3, 3], G * J / L),
        ("k[1,1]  12EI33/L³", k_loc[1, 1], 12 * E * I33 / L**3),
        ("k[2,2]  12EI22/L³", k_loc[2, 2], 12 * E * I22 / L**3),
        ("k[5,5]  4EI33/L",   k_loc[5, 5], 4 * E * I33 / L),
        ("k[4,4]  4EI22/L",   k_loc[4, 4], 4 * E * I22 / L),
    ]
    for name, got, exp in tests:
        ratio = got / exp if exp else float("nan")
        print(hdr(f"{name}: {got:.3e}  (bekl. {exp:.3e}, oran {ratio:.3f})"))

    evals = np.linalg.eigvalsh(k_loc)
    print(hdr(f"k_loc özdeğer min: {evals.min():.3e}"))
    print(hdr(f"k_loc negatif özdeğer: {int((evals < -1e-6).sum())}"))

    p1 = (f.node_i.x, f.node_i.y, f.node_i.z)
    p2 = (f.node_j.x, f.node_j.y, f.node_j.z)
    T, _ = transformation_matrix(p1, p2, getattr(f, "rotation_deg", 0.0) or 0.0)

    print(hdr(f"T @ T.T = I: {np.allclose(T @ T.T, np.eye(12))}"))
    print(hdr(f"det(T): {np.linalg.det(T):.6f}"))

    k_glob = T.T @ k_loc @ T
    print(hdr(f"k_glob[0,0]: {k_glob[0,0]:.2f}"))


# ============================================================================
# 6) MESNETLİ DOF'LAR
# ============================================================================
def report_fixed_dofs(scn):
    section("Mesnetli DOF'lar")

    fixed = _collect_fixed_dofs(scn)
    print(hdr(f"fixed_dofs: {len(fixed)}"))
    print(hdr(f"ilk 10: {fixed[:10]}"))

    print("  Tamamen sabit düğümler:")
    for key, n in scn.nodes.items():
        r = getattr(n, "restraint", None)
        if r and all(getattr(r, d, False) for d in ("ux", "uy", "uz", "rx", "ry", "rz")):
            print(f"    {key}: ({n.x:.0f}, {n.y:.0f}, {n.z:.0f})")

    return fixed


# ============================================================================
# 7) MODAL + K/M TEŞHİSİ (+ SAP2000 period karşılaştırma)
# ============================================================================
def report_modal(scn, stiff, mass, fixed_dofs, sap_file: str | None = None):
    section("Modal çözüm (solver)")

    solver = StructuralSolver(
        K_global=stiff.K_global,
        M_global=mass.M_global,
        fixed_dofs=fixed_dofs,
        num_dofs=len(scn.nodes) * 6,
    )

    # --- Reduced K/M teşhisi ---
    K_red, M_red = solver._reduced()
    m_diag = np.diag(M_red)
    massive = np.where(m_diag > 1e-9)[0]

    K_mm = K_red[np.ix_(massive, massive)]
    K_evals = np.linalg.eigvalsh(K_red)

    print(hdr(f"K_mm boyut: {K_mm.shape}"))
    print(hdr(f"K_mm özdeğer min: {np.linalg.eigvalsh(K_mm).min():.3e}"))
    print(hdr(f"K_mm özdeğer max: {np.linalg.eigvalsh(K_mm).max():.3e}"))
    print(hdr(f"K_red boyut: {K_red.shape}"))
    print(hdr(f"K_red özdeğer min: {K_evals.min():.3e}"))
    print(hdr(f"K_red özdeğer max: {K_evals.max():.3e}"))
    print(hdr(f"K_red negatif: {int((K_evals < -1e-6).sum())}"))
    print(hdr(f"M_red köşegen min: {m_diag.min():.3e}"))
    print(hdr(f"M_red köşegen max: {m_diag.max():.3e}"))
    print(hdr(f"M_red sıfır sayısı: {int((m_diag <= 1e-12).sum())}"))

    # --- Modal çözüm ---
    modal = solver.modal_solve(n_modes=6, debug=True)

    print(hdr(f"n_modes: {modal.n_modes}"))
    for i in range(modal.n_modes):
        print(hdr(f"mod {i+1}: T={modal.periods[i]:.4f}s, f={modal.frequencies[i]:.4f} Hz"))

    print(hdr(f"modal_dofs: {len(modal.modal_dofs)}"))
    print(hdr(f"total_mass_x: {modal.total_mass_x:.2f} kg"))

    # --- SAP2000 period karşılaştırma ---
    if sap_file:
        from tools.sap2000_mass_compare import compare_modal_periods
        compare_modal_periods(sap_file, modal)

    # --- Ek: K[0:6, 6:12] ve spy ---
    print("\n--- Düğüm 1-2 bağlantı (K[0:6, 6:12]) ---")
    np.set_printoptions(precision=2, suppress=False, linewidth=250)
    print(stiff.K_global[0:6, 6:12])

    print("\n--- K spy yoğunluğu ---")
    K = stiff.K_global
    off = (np.abs(K - np.diag(np.diag(K))) > 1e-6).sum()
    print(f"Off-diagonal sıfır olmayan: {off} / {K.size}  ({off/K.size*100:.2f}%)")

    return modal


# ============================================================================
# MAIN
# ============================================================================
def main():
    from core.units import G_M_S2, KG_PER_TON
    print(f"from core.units import.... G_M_S2: {G_M_S2} KG_PER_TON: {KG_PER_TON}")

    s2k_path = sys.argv[1] if len(sys.argv) > 1 else "tests/simple_ba1.s2k"
    sap_file = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"\n{'='*70}\nDosya: {s2k_path}\n{'='*70}")
    if sap_file:
        print(f"SAP2000 raporu: {sap_file}")
        if not Path(sap_file).exists():
            print(f"⚠️  SAP2000 raporu yok: {sap_file} — karşılaştırma atlanacak")
            sap_file = None

    from tools.s2k import S2KLoader
    p = S2KLoader(s2k_path).load()
    scn = p.scene

    # Bölümler — sıralı, tek geçiş
    safe(lambda: report_model(scn), "model")
    safe(lambda: report_dofs_and_restraints(scn), "dofs")

    mass_holder = {}
    stiff_holder = {}
    fixed_holder = {}

    def _mass():
        mass_holder["m"] = report_mass(scn, p, sap_file=sap_file)
    safe(_mass, "mass")

    def _stiff():
        stiff_holder["s"] = report_stiffness(scn, p)
    safe(_stiff, "stiffness")

    safe(lambda: report_local_frame(scn), "local_frame")

    def _fixed():
        fixed_holder["f"] = report_fixed_dofs(scn)
    safe(_fixed, "fixed_dofs")

    def _modal():
        report_modal(scn, stiff_holder["s"], mass_holder["m"],
                     fixed_holder["f"], sap_file=sap_file)
    safe(_modal, "modal")

    print(f"\n{'='*70}\nBitti\n{'='*70}")


if __name__ == "__main__":
    main()
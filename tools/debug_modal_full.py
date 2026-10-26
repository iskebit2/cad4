# tools/debug_modal_full.py

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.units import MEGAGRAM
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
    try:
        fn()
    except Exception:
        print(f"  [{label}] HATA:")
        traceback.print_exc(limit=5)   # limit ekle
        # veya tam traceback için:
        import traceback as tb
        tb.print_exc()


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

    print(f"area_count: {stiff.area_count}")
    print(f"skipped: {stiff.skipped}")
    

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

    # test2
    print("-"*30)
    print("test")
    print(f"\n   report_local_frame     ---> params... Sction: {sec.name} A: {A} AS2: {AS2} AS3: {AS3} I33: {I33} I22: {I22} J: {J}")
    phi3 = 12 * E * I33 / (G * AS2 * L**2) if G > 0 and AS2 > 0 and I33 > 0 else 0.0
    phi2 = 12 * E * I22 / (G * AS3 * L**2) if G > 0 and AS3 > 0 and I22 > 0 else 0.0
    tests = [
    ("EA/L",       k_loc[0, 0], E * A / L),
    ("GJ/L",       k_loc[3, 3], G * J / L),
    ("12EI33/L³",  k_loc[1, 1], 12 * E * I33 / (L**3 * (1 + phi3))),
    ("12EI22/L³",  k_loc[2, 2], 12 * E * I22 / (L**3 * (1 + phi2))),
    ("4EI33/L",    k_loc[5, 5], (4 + phi3) * E * I33 / (L * (1 + phi3))),
    ("4EI22/L",    k_loc[4, 4], (4 + phi2) * E * I22 / (L * (1 + phi2))),
]
    for name, got, exp in tests:
        ratio = got / exp if exp else float("nan")
        print(hdr(f"{name}: {got:.3e}  (bekl. {exp:.3e}, oran {ratio:.3f})"))
    print("-"*30)
    #

    evals = np.linalg.eigvalsh(k_loc)
    print(hdr(f"k_loc özdeğer min: {evals.min():.3e}"))
    print(hdr(f"k_loc negatif özdeğer: {int((evals < -1e-6).sum())}"))
    print("-"*30)

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
    section("Modal çözüm (solver) — Guyan")

    solver = StructuralSolver(
        K_global=stiff.K_global,
        M_global=mass.M_global,
        fixed_dofs=fixed_dofs,
        num_dofs=len(scn.nodes) * 6,
    )

    # ------------------------------------------------------------------
    # 1) Reduced (mesnetli) sistem — Guyan öncesi
    # ------------------------------------------------------------------
    K_red, M_red = solver._reduced()
    m_diag = np.diag(M_red)

    # Kütleli (master) ve kütlesiz (slave) DOF ayrımı
    master_mask = m_diag > 1e-9
    n_master = int(master_mask.sum())
    n_slave = int((~master_mask).sum())

    print(hdr(f"K_red boyut: {K_red.shape}"))
    print(hdr(f"Master (kütleli) DOF: {n_master}"))
    print(hdr(f"Slave (kütlesiz) DOF: {n_slave}"))

    if n_master > 0:
        K_mm = K_red[np.ix_(master_mask, master_mask)]
        print(hdr(f"K_mm boyut: {K_mm.shape}"))
        print(hdr(f"K_mm max köşegen: {np.max(np.diag(K_mm)):.3e}"))

    K_evals = np.linalg.eigvalsh(K_red)
    print(hdr(f"K_red özdeğer min: {K_evals.min():.3e}"))
    print(hdr(f"K_red özdeğer max: {K_evals.max():.3e}"))
    print(hdr(f"K_red negatif: {int((K_evals < -1e-6).sum())}"))
    print(hdr(f"M_red köşegen min: {m_diag.min():.3e}"))
    print(hdr(f"M_red köşegen max: {m_diag.max():.3e}"))
    print(hdr(f"M_red sıfır sayısı: {int((m_diag <= 1e-12).sum())}"))

    # ------------------------------------------------------------------
    # 2) Guyan kondensasyonu (solver içinde yapılıyorsa burada da yap)
    # ------------------------------------------------------------------
    # NOT: solver.modal_solve() içinde Guyan uygulanıyorsa, burada
    # ayrıca yapmayın. Sadece teşhis için K_gg / K_gs / K_ss boyutlarını
    # ve kondanse matrisin durumunu raporlayın.
    try:
        K_gg, M_gg = solver._guyan_reduced()   # solver'da böyle bir API varsa
        print(hdr(f"Guyan sonrası K_gg boyut: {K_gg.shape}"))
        print(hdr(f"Guyan K_gg özdeğer min: {np.linalg.eigvalsh(K_gg).min():.3e}"))
        print(hdr(f"Guyan K_gg özdeğer max: {np.linalg.eigvalsh(K_gg).max():.3e}"))
        print(hdr(f"Guyan K_gg negatif: {int((np.linalg.eigvalsh(K_gg) < -1e-6).sum())}"))
        print(hdr(f"Guyan M_gg köşegen min: {np.diag(M_gg).min():.3e}"))
        print(hdr(f"Guyan M_gg köşegen max: {np.diag(M_gg).max():.3e}"))
        print(hdr(f"Guyan M_gg sıfır sayısı: {int((np.diag(M_gg) <= 1e-12).sum())}"))
    except AttributeError:
        print(hdr("Guyan API bulunamadı (solver._guyan_reduced yok)"))

    # ------------------------------------------------------------------
    # 3) Modal çözüm
    # ------------------------------------------------------------------
    modal = solver.modal_solve(n_modes=6, debug=True)

    print(hdr(f"n_modes: {modal.n_modes}"))
    for i in range(modal.n_modes):
        print(hdr(f"mod {i+1}: T={modal.periods[i]:.4f}s, f={modal.frequencies[i]:.4f} Hz"))

    print(hdr(f"modal_dofs: {len(modal.modal_dofs)}"))
    print(hdr(f"total_mass_x: {modal.total_mass_x:.2f} kg"))
    print(hdr(f"total_mass_y: {modal.total_mass_y:.2f} kg"))
    print(hdr(f"total_mass_z: {modal.total_mass_z:.2f} kg"))

    # Modal kütle dengesi
    em_x = float(np.sum(modal.effective_mass_x))
    em_y = float(np.sum(modal.effective_mass_y))
    em_z = float(np.sum(modal.effective_mass_z))
    print(hdr(f"Σ effective_mass_x: {em_x:.2f} kg"))
    print(hdr(f"Σ effective_mass_y: {em_y:.2f} kg"))
    print(hdr(f"Σ effective_mass_z: {em_z:.2f} kg"))
    if modal.total_mass_x > 0:
        print(hdr(f"Katılım oranı X: {em_x / modal.total_mass_x:.4f}"))
    if modal.total_mass_y > 0:
        print(hdr(f"Katılım oranı Y: {em_y / modal.total_mass_y:.4f}"))
    if modal.total_mass_z > 0:
        print(hdr(f"Katılım oranı Z: {em_z / modal.total_mass_z:.4f}"))

    # Z DOF kontrolü
    z_mask = (np.asarray(modal.modal_dofs) % 6) == 2
    z_rows = np.where(z_mask)[0]
    print(f"Z DOF sayısı: {z_mask.sum()}")
    print(f"Z DOF endeksleri: {np.asarray(modal.modal_dofs)[z_mask][:10]}")

    z_dofs = [8, 14, 20, 44, 50, 56, 74, 80, 86, 92]
    K_z = stiff.K_global[np.ix_(z_dofs, z_dofs)]
    off_diag = K_z - np.diag(np.diag(K_z))
    print("K_z boyut:", K_z.shape)
    print("K_z köşegen dışı max:", np.abs(off_diag).max())
    print("K_z köşegen dışı sıfır olmayan:", (np.abs(off_diag) > 1e-6).sum())


    phi = modal.mode_shapes
    for m in range(modal.n_modes):
        z_component = np.abs(phi[z_rows, m]).max()
        print(f"Mod {m+1}: Z max |φ| = {z_component:.3e}, Z toplam |φ| = {np.abs(phi[z_rows, m]).sum():.3e}")

    # ------------------------------------------------------------------
    # 4) SAP2000 period karşılaştırma
    # ------------------------------------------------------------------
    if sap_file:
        from tools.sap2000_mass_compare import compare_modal_periods
        compare_modal_periods(sap_file, modal)

    # ------------------------------------------------------------------
    # 5) K yapısal teşhis (küçük modellerde anlamlı)
    # ------------------------------------------------------------------
    K = stiff.K_global
    if K.shape[0] <= 24:
        print("\n--- Düğüm 1-2 bağlantı (K[0:6, 6:12]) ---")
        np.set_printoptions(precision=2, suppress=False, linewidth=250)
        print(K[0:6, 6:12])

    print("\n--- K spy yoğunluğu ---")
    off = (np.abs(K - np.diag(np.diag(K))) > 1e-6).sum()
    print(f"Off-diagonal sıfır olmayan: {off} / {K.size}  ({off/K.size*100:.2f}%)")

    # ------------------------------------------------------------------
    # 6) Kütle tutarlılık kontrolü (mass_assembly ile çapraz)
    # ------------------------------------------------------------------
    # --- Kütle tutarlılığı (consistent-aware) ---
    print("\n--- Kütle tutarlılığı ---")
    from core.analysis.validation import _total_mass_consistent

    M_total_ton = _total_mass_consistent(mass.M_global)   # Σ_ij M_ij (UX bloğu)
    node_total_ton = sum(mass.node_masses.values()) / MEGAGRAM
    print(hdr(f"Σ M_ij (UX, ton): {M_total_ton:.4f}"))
    print(hdr(f"node_masses (ton): {node_total_ton:.4f}"))
    if node_total_ton > 0:
        rel = abs(M_total_ton - node_total_ton) / node_total_ton
        print(hdr(f"Göreli fark: {rel:.3e}"))
        if rel > 1e-3:
            print(hdr("⚠️  KÜTLE KORUNUMU BOZUK — consistent montajda eksiklik olabilir"))
        else:
            print(hdr("✅ Kütle korunumu tam"))

    return modal


# ============================================================================
# MAIN
# ============================================================================
def main():
    from core.units import G_M_S2, MEGAGRAM
    print(f"from core.units import....1 m/s² = 1000 mm/s².... \nG_M_S2: {G_M_S2} MEGAGRAM: {MEGAGRAM}")

    s2k_path = sys.argv[1] if len(sys.argv) > 1 else "tests/simple_ba1s.$2k"
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
    node1 = list(scn.nodes.values())[0]
    count = 0
    for f in scn.frames.values():
        if f.node_i is node1 or f.node_j is node1:
            count += 1
            dx = f.node_j.x - f.node_i.x
            dy = f.node_j.y - f.node_i.y
            dz = f.node_j.z - f.node_i.z
            L = f.get_length()
            print(f"Frame {f.label}: dx={dx:.0f}, dy={dy:.0f}, dz={dz:.0f}, L={L:.0f}")
    print(f"Düğüm 1'e bağlı frame sayısı: {count}")
    # Mesnetli düğümlerin restraint'leri
    for key, n in scn.nodes.items():
        r = getattr(n, "restraint", None)
        if r and all(getattr(r, d, False) for d in ("ux","uy","uz","rx","ry","rz")):
            print(f"Node {key}: tamamen sabit")
        elif r:
            partial = [d for d in ("ux","uy","uz","rx","ry","rz") if getattr(r, d, False)]
            print(f"Node {key}: kısmi mesnet {partial}")

        
    # Bölümler — sıralı, tek geçiş
    # safe(lambda: report_model(scn), "model")
    # safe(lambda: report_dofs_and_restraints(scn), "dofs")

    mass_holder = {}
    stiff_holder = {}
    fixed_holder = {}

    def _mass():
        mass_holder["m"] = report_mass(scn, p, sap_file=sap_file)
    safe(_mass, "mass")

    def _stiff():
        stiff_holder["s"] = report_stiffness(scn, p)
    safe(_stiff, "stiffness")

    # safe(lambda: report_local_frame(scn), "local_frame")

    def _fixed():
        fixed_holder["f"] = report_fixed_dofs(scn)
    safe(_fixed, "fixed_dofs")
    # debug script sonunda geçici
    stiff = report_stiffness(scn, p)

    def _modal():
        report_modal(scn, stiff_holder["s"], mass_holder["m"],
                     fixed_holder["f"], sap_file=sap_file)
    safe(_modal, "modal")

    
    # Serbest düğümlerin K köşegenleri
    free_node_keys = [k for k, n in scn.nodes.items() 
                    if not (getattr(n, "restraint", None) and 
                            all(getattr(n.restraint, d, False) for d in ("ux","uy","uz","rx","ry","rz")))]
    print(f"Serbest düğüm sayısı: {len(free_node_keys)}")
    for k in free_node_keys[:5]:
        n = scn.nodes[k]
        dofs = n.dof_indices
        print(f"Node {k}: K[UX]={stiff.K_global[dofs[0],dofs[0]]:.0f}, "
            f"K[UY]={stiff.K_global[dofs[1],dofs[1]]:.0f}, "
            f"K[UZ]={stiff.K_global[dofs[2],dofs[2]]:.0f}")


    print("K[2,3] UX-UX:", stiff.K_global[6, 12])
    print("K[2,3] UY-UY:", stiff.K_global[7, 13])
    print("K[2,3] UZ-UZ:", stiff.K_global[8, 14])

    print(f"\n{'='*70}\nBitti\n{'='*70}")


if __name__ == "__main__":
    main()
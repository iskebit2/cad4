# tests/test_analiz.py
import numpy as np

from app.commands.analysis.force_recovery import recover_frame_forces
from app.commands.analysis.run import AnalysisOptions, AnalysisService
from tools.s2k import S2KLoader

file_ = "tests/testmodel1.s2k"
slo = S2KLoader(file_)
proj = slo.load()

print("Load Patterns:", list(proj.load_patterns.keys()))
print("Load Cases:", list(proj.load_cases.keys()))
print("Load Combinations:", list(proj.combinations.keys()))
print("Spectrum Functions:", list(proj.spectrum_functions.keys()))
print("Response Spectrum Cases:", list(proj.response_spectrum_cases.keys()))
print("Auto Seis:", list(proj.auto_seismics.keys()))
print(
    f"Ham Model -> Node: {len(proj.math_model.nodes)}, "
    f"Frame: {len(proj.math_model.frames)}, "
    f"Area: {len(proj.math_model.areas)}, "
    f"Link: {len(proj.math_model.links)}"
)

first_spec = next(iter(proj.spectrum_functions.keys()), None)

options = AnalysisOptions(
    n_live=proj.site_info.live_load_factor,
    n_modes=12,
    run_static=True,
    run_modal=True,
    run_spectral=bool(first_spec),
    run_takeoff=True,
    spectrum_name=first_spec,
    use_shear_deform=True,
)

bundle = AnalysisService.run(proj.math_model, proj, options)
res_all = bundle.result

print("\n=== ANALİZ DURUMU VE UYARILAR ===")
print(f"Başarılı (ok): {bundle.ok}")
if bundle.errors:
    print("Hatalar:", bundle.errors)
if res_all and res_all.warnings:
    print("Uyarılar:", res_all.warnings)

if res_all is not None:
    print("\n=== MODEL VE RİJİTLİK ÖZETİ ===")
    print(f"Toplam DOF   : {res_all.K.shape[0]}")
    print(f"Mesnetli DOF : {len(res_all.fixed_dofs)}")
    print(f"Frame Sayısı : {res_all.stiffness.frame_count}")
    print(f"Area Sayısı  : {res_all.stiffness.area_count}")
    print(f"Link Sayısı  : {res_all.stiffness.link_count}")
    print(f"Spring Node  : {res_all.stiffness.spring_node_count}")
    if res_all.stiffness.skipped:
        print(f"Atlanan      : {res_all.stiffness.skipped}")

    print("\n=== KÜTLE ÖZETİ ===")
    print(f"Self (kg)   : {res_all.mass.total_self_kg:.3f}")
    print(f"Dead (kg)   : {res_all.mass.total_dead_kg:.3f}")
    print(f"Live (kg)   : {res_all.mass.total_live_kg:.3f}")
    print(f"Toplam (kg) : {res_all.mass.total_kg:.3f} ({res_all.mass.total_ton:.4f} ton)")

    print("\n=== ÇÖZÜLEN STATİK LOAD CASE'LER ===")
    print("Load Case'ler:", list(res_all.static_results.keys()))

    frame_forces = recover_frame_forces(proj, res_all.mesh, res_all.static_results)

    for cname, res in res_all.static_results.items():
        U = res.displacements
        F = res.applied_forces
        R = res.reactions

        sum_F = np.array([np.sum(F[i::6]) for i in range(6)], dtype=float)
        sum_R = np.array([np.sum(R[i::6]) for i in range(6)], dtype=float)
        unbalance = sum_F + sum_R

        print(f"\n=== GLOBAL DENGE KONTROLÜ ({cname}) ===")
        print(f"Toplam Uygulanan Kuvvet [FX, FY, FZ, MX, MY, MZ]: {sum_F}")
        print(f"Toplam Mesnet Reaksiyonu [RX, RY, RZ, MX, MY, MZ]: {sum_R}")
        print(f"Global Denge Farkı (F + R)                        : {unbalance}")
        print(f"Sıfır dışı F bileşeni sayısı                      : {np.count_nonzero(np.abs(F) > 1e-9)}")
        print(f"Max |U| (mm / rad)                                : {np.max(np.abs(U)):.6e}")

        print(f"\n=== DÜĞÜM DEPLASMANLARI ({cname}) ===")
        for n_key, u_vec in res.node_displacements.items():
            if np.linalg.norm(u_vec) > 1e-12:
                print(
                    f"  {n_key:>6s}: UX={u_vec[0]:+.4e}, UY={u_vec[1]:+.4e}, UZ={u_vec[2]:+.4e} | "
                    f"RX={u_vec[3]:+.4e}, RY={u_vec[4]:+.4e}, RZ={u_vec[5]:+.4e}"
                )

        print(f"\n=== MESNET REAKSİYONLARI ({cname}) ===")
        for n_key, r_vec in res.node_reactions.items():
            if np.linalg.norm(r_vec) > 1e-9:
                print(
                    f"  {n_key:>6s}: FX={r_vec[0]:+12.2f}, FY={r_vec[1]:+12.2f}, FZ={r_vec[2]:+12.2f} | "
                    f"MX={r_vec[3]:+13.1f}, MY={r_vec[4]:+13.1f}, MZ={r_vec[5]:+13.1f}"
                )

        print(f"\n=== ÇUBUK İÇ KUVVETLERİ ({cname}) ===")
        for fid, ff in frame_forces.get(cname, {}).items():
            print(f"\nFrame id={fid} ({ff.label}), L={ff.length:.2f} mm")
            print(f"  end_i (lokal): {np.round(ff.end_i, 3)}")
            print(f"  end_j (lokal): {np.round(ff.end_j, 3)}")
            for st in ff.stations:
                print(
                    f"  x/L={st.ratio:.3f} (x={st.x:7.1f}) | "
                    f"N={st.N:+10.2f}  V2={st.V2:+10.2f}  V3={st.V3:+10.2f} | "
                    f"T={st.T:+11.1f}  M2={st.M2:+11.1f}  M3={st.M3:+11.1f}"
                )

    if res_all.modal is not None:
        m = res_all.modal
        print("\n=== MODAL ANALİZ VE KÜTLE KATILIM ORANLARI ===")
        print(
            f"Serbest Toplam Kütle (ton) -> "
            f"Mx={m.total_mass_x:.4f}, My={m.total_mass_y:.4f}, Mz={m.total_mass_z:.4f}"
        )
        cum_rx = 0.0
        cum_ry = 0.0
        cum_rz = 0.0
        for i in range(m.n_modes):
            t_val = m.periods[i]
            f_val = m.frequencies[i]
            w_val = 2.0 * np.pi * f_val
            rx = (m.effective_mass_x[i] / m.total_mass_x * 100.0) if m.total_mass_x > 0.0 else 0.0
            ry = (m.effective_mass_y[i] / m.total_mass_y * 100.0) if m.total_mass_y > 0.0 else 0.0
            rz = (m.effective_mass_z[i] / m.total_mass_z * 100.0) if m.total_mass_z > 0.0 else 0.0
            cum_rx += rx
            cum_ry += ry
            cum_rz += rz
            print(
                f"  Mod {i + 1:2d}: T={t_val:.4f} s | f={f_val:.4f} Hz | w={w_val:.4f} rad/s | "
                f"Gamma=({m.participation_factor_x[i]:+.3f}, {m.participation_factor_y[i]:+.3f}, {m.participation_factor_z[i]:+.3f}) | "
                f"UX={rx:6.2f}% (Sum={cum_rx:6.2f}%), "
                f"UY={ry:6.2f}% (Sum={cum_ry:6.2f}%), "
                f"UZ={rz:6.2f}% (Sum={cum_rz:6.2f}%)"
            )

    if bundle.spectral is not None:
        sp = bundle.spectral
        print(f"\n=== TEPKİ SPEKTRUMU (RESPONSE SPECTRUM) SONUÇLARI ({first_spec}) ===")
        for attr_name in vars(sp):
            val = getattr(sp, attr_name)
            if isinstance(val, np.ndarray):
                print(f"  {attr_name}: shape={val.shape}, max={np.max(np.abs(val)):.6e}")
            else:
                print(f"  {attr_name}: {val}")

if bundle.takeoff is not None:
    print("\n=== MALZEME METRAJI (TAKEOFF) ===")
    for attr_name in vars(bundle.takeoff):
        print(f"  {attr_name}: {getattr(bundle.takeoff, attr_name)}")
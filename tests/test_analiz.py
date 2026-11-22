from __future__ import annotations

import time
import numpy as np

from app.commands.analysis.force_recovery import (
    _frame_local_equivalent_nodal_loads,
    recover_frame_forces,
)
from app.commands.analysis.frame_resolver import (
    resolve_frame_kinematics,
    resolve_section,
)
from app.commands.analysis.run import AnalysisOptions, AnalysisService
from app.commands.analysis.solve_static import (
    assemble_load_case_vector,
    assemble_pattern_load_vector,
)
from tools.s2k import S2KLoader

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename="cad4_test.log",
    filemode="w",
    encoding="utf-8",
    force=True,
)
logger = logging.getLogger(__name__)

def run_full_analysis_test(s2k_path: str = "tests/simple_steel.s2k") -> None:
    t0 = time.perf_counter()
    proj = S2KLoader(s2k_path).load()
    t_load = time.perf_counter() - t0

    model = proj.math_model
    first_spec = next(iter(proj.spectrum_functions.keys()), None)

    logger.info(f"=== MODEL ÖZETİ ({s2k_path}) | Yükleme: {t_load * 1000:.1f} ms ===")
    logger.info(f"Load Patterns          : {list(proj.load_patterns.keys())}")
    logger.info(f"Load Cases             : {list(proj.load_cases.keys())}")
    logger.info(f"Load Combinations      : {list(proj.combinations.keys())}")
    logger.info(f"Spectrum Functions     : {list(proj.spectrum_functions.keys())}")
    logger.info(f"Response Spectrum Cases: {list(proj.response_spectrum_cases.keys())}")
    logger.info(f"Ham Model              : Node={len(model.nodes)}, Frame={len(model.frames)}, Area={len(model.areas)}, Link={len(model.links)}")

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

    t1 = time.perf_counter()
    bundle = AnalysisService.run(model, proj, options)
    t_solve = time.perf_counter() - t1
    res_all = bundle.result

    logger.info(f"\n=== ANALİZ DURUMU ({t_solve * 1000:.1f} ms) ===")
    logger.info(f"Başarılı (ok): {bundle.ok}")
    if bundle.errors:
        logger.info(f"Hatalar: {bundle.errors}")
    if res_all and res_all.warnings:
        logger.info(f"Uyarılar: {res_all.warnings}")

    assert bundle.ok and res_all is not None, f"Analiz başarısız: {bundle.errors}"

    mesh = res_all.mesh
    num_dofs = res_all.K.shape[0]
    dof_map = {
        n_key: int(nd.dof_indices[0])
        for n_key, nd in mesh.nodes.items()
        if getattr(nd, "dof_indices", None)
    }

    logger.info(f"\n=== RİJİTLİK VE MESH TUTARLILIĞI ===")
    logger.info(f"DOF={num_dofs} (Mesnetli={len(res_all.fixed_dofs)}) | ")
    logger.info(f"Frame={res_all.stiffness.frame_count}, Area={res_all.stiffness.area_count}, ")
    logger.info(f"Link={res_all.stiffness.link_count}, Spring={res_all.stiffness.spring_node_count}")
    if res_all.stiffness.skipped:
        logger.info(f"Atlanan Elemanlar: {res_all.stiffness.skipped}")

    missing_parents = [uid for uid in mesh.frame_children if uid not in model.frames]
    assert not missing_parents, f"model.frames içinde olmayan parent uid: {missing_parents}"

    logger.info(f"\n=== KÜTLE ÖZETİ ===")
    logger.info(f"Self={res_all.mass.total_self_kg:.3f} kg | ")
    logger.info(f"Dead={res_all.mass.total_dead_kg:.3f} kg | ")
    logger.info(f"Live={res_all.mass.total_live_kg:.3f} kg | ")
    logger.info(f"Toplam={res_all.mass.total_kg:.3f} kg ({res_all.mass.total_ton:.4f} ton)")

    if mesh.frames:
        sf0 = next(iter(mesh.frames.values()))
        sec_res0 = resolve_section(sf0.section, getattr(sf0, "modifiers", None))
        kin0 = resolve_frame_kinematics(sf0, sec_res0)
        f_eq0, spans0 = _frame_local_equivalent_nodal_loads(proj, sf0, sec_res0, kin0, "DEAD")
        logger.info(f"\nİlk Sub-Frame ({sf0.label}): A={sec_res0.A:.1f} mm², ")
        logger.info(f"L_clear={kin0.L_clear:.1f} mm, |f_eq|={np.linalg.norm(f_eq0):.3e}, ")
        logger.info(f"span_loads={len(spans0)}")

    if "DEAD" in proj.load_patterns and "DEAD" in proj.load_cases:
        F_pat = assemble_pattern_load_vector(
            mesh=mesh,
            dof_map=dof_map,
            num_dofs=num_dofs,
            pattern_name="DEAD",
            pattern=proj.load_patterns["DEAD"],
            scale=1.0,
        )
        F_lc = assemble_load_case_vector(
            project=proj,
            mesh=mesh,
            dof_map=dof_map,
            num_dofs=num_dofs,
            load_case=proj.load_cases["DEAD"],
            M_global=res_all.mass.M_global if res_all.mass else None,
        )
        logger.info(f"DEAD Vektör Normları -> |F_pat|={np.linalg.norm(F_pat):.6e}, |F_lc|={np.linalg.norm(F_lc):.6e}")

    frame_forces = recover_frame_forces(
        proj,
        mesh,
        res_all.static_results,
        use_shear_deform=options.use_shear_deform,
    )

    free_dofs = np.setdiff1d(np.arange(num_dofs), res_all.fixed_dofs)

    for cname, res in res_all.static_results.items():
        U = res.displacements
        F = res.applied_forces
        R = res.reactions

        sum_F = np.array([np.sum(F[i::6]) for i in range(3)], dtype=float)
        sum_R = np.array([np.sum(R[i::6]) for i in range(3)], dtype=float)
        force_unbalance = sum_F + sum_R

        logger.info(f"\n=== STATİK SONUÇLAR: {cname} ===")
        logger.info(f"|F|={np.linalg.norm(F):.4e} (|F_free|={np.linalg.norm(F[free_dofs]):.4e}) | ")
        logger.info(f"|U|_max={np.max(np.abs(U)):.6e}")
        logger.info(f"Toplam Kuvvet [FX, FY, FZ]    : {np.round(sum_F, 3)}")
        logger.info(f"Toplam Reaksiyon [RX, RY, RZ] : {np.round(sum_R, 3)}")
        logger.info(f"Kuvvet Denge Farkı (F + R)    : {force_unbalance}")
        assert np.linalg.norm(force_unbalance) <= max(1e-3, np.linalg.norm(sum_F) * 1e-6), (
            f"{cname} kuvvet dengesi sağlanamadı: {force_unbalance}"
        )

        logger.info(f"\n--- Düğüm Deplasmanları ({cname}) ---")
        for n_key, u_vec in res.node_displacements.items():
            if n_key.startswith("N_-"):
                continue
            if np.linalg.norm(u_vec) > 1e-12:
                
                logger.info(f"  {n_key:>6s}: UX={u_vec[0]:+.4e}, UY={u_vec[1]:+.4e}, UZ={u_vec[2]:+.4e} | RX={u_vec[3]:+.4e}, RY={u_vec[4]:+.4e}, RZ={u_vec[5]:+.4e}")
                

        logger.info(f"\n--- Mesnet Reaksiyonları ({cname}) ---")
        for n_key, r_vec in res.node_reactions.items():
            if np.linalg.norm(r_vec) > 1e-9:
                logger.info(f"  {n_key:>6s}: FX={r_vec[0]:+12.2f}, FY={r_vec[1]:+12.2f}, FZ={r_vec[2]:+12.2f} | MX={r_vec[3]:+13.1f}, MY={r_vec[4]:+13.1f}, MZ={r_vec[5]:+13.1f}")

        logger.info(f"\n--- Çubuk İç Kuvvetleri ve Uç-İstasyon Tutarlılığı ({cname}) ---")
        cmap = frame_forces.get(cname, {})
        for fid, ff in cmap.items():
            if ff.stations:
                s0 = ff.stations[0]
                sL = ff.stations[-1]
                max_err = max(
                    abs(s0.M3 - (-ff.end_i[5])),
                    abs(s0.M2 - (-ff.end_i[4])),
                    abs(s0.V2 - ff.end_i[1]),
                    abs(s0.V3 - ff.end_i[2]),
                    abs(s0.N - (-ff.end_i[0])),
                    abs(sL.M3 - ff.end_j[5]),
                    abs(sL.M2 - ff.end_j[4]),
                    abs(sL.V2 - (-ff.end_j[1])),
                    abs(sL.V3 - (-ff.end_j[2])),
                    abs(sL.N - ff.end_j[0]),
                )
                tol = max(1.0, float(np.max(np.abs(ff.end_i))) * 1e-5)
                assert max_err < tol, f"Frame {fid} uç-istasyon uyumsuzluğu: max_err={max_err:.3e}"

            logger.info(f"\nFrame id={fid} ({ff.label}), L={ff.length:.2f} mm  end_i (lokal): {np.round(ff.end_i, 3)}  end_j (lokal): {np.round(ff.end_j, 3)}")
            for st in ff.stations:
                logger.info(f"  x/L={st.ratio:.3f} (x={st.x:7.1f}) | N={st.N:+10.2f}  V2={st.V2:+10.2f}  V3={st.V3:+10.2f} | T={st.T:+11.1f}  M2={st.M2:+11.1f}  M3={st.M3:+11.1f}")

    if res_all.modal is not None:
        m = res_all.modal
        logger.info(f"\n=== MODAL ANALİZ VE KÜTLE KATILIM ORANLARI ===")
        logger.info(f"Serbest Toplam Kütle (ton) -> Mx={m.total_mass_x:.4f}, My={m.total_mass_y:.4f}, Mz={m.total_mass_z:.4f}")
        cum_rx = 0.0
        cum_ry = 0.0
        cum_rz = 0.0
        for i in range(m.n_modes):
            t_val = m.periods[i]
            f_val = m.frequencies[i]
            w_val = 2.0 * np.pi * f_val
            if i > 0:
                assert t_val <= m.periods[i - 1] + 1e-9, "Modal periyot sıralaması bozuk"
            rx = (m.effective_mass_x[i] / m.total_mass_x * 100.0) if m.total_mass_x > 0.0 else 0.0
            ry = (m.effective_mass_y[i] / m.total_mass_y * 100.0) if m.total_mass_y > 0.0 else 0.0
            rz = (m.effective_mass_z[i] / m.total_mass_z * 100.0) if m.total_mass_z > 0.0 else 0.0
            cum_rx += rx
            cum_ry += ry
            cum_rz += rz
            logger.info(f"  Mod {i + 1:2d}: T={t_val:.4f} s | f={f_val:.4f} Hz | w={w_val:.4f} rad/s | Gamma=({m.participation_factor_x[i]:+.3f}, {m.participation_factor_y[i]:+.3f}, {m.participation_factor_z[i]:+.3f}) | UX={rx:6.2f}% (Sum={cum_rx:6.2f}%), UY={ry:6.2f}% (Sum={cum_ry:6.2f}%), UZ={rz:6.2f}% (Sum={cum_rz:6.2f}%)")
        assert cum_rx <= 100.01 and cum_ry <= 100.01 and cum_rz <= 100.01, "Kütle katılımı %100'ü aştı"

    if bundle.spectral is not None:
        sp = bundle.spectral
        logger.info(f"\n=== TEPKİ SPEKTRUMU SONUÇLARI ({first_spec}) ===")
        for attr_name in vars(sp):
            val = getattr(sp, attr_name)
            if isinstance(val, np.ndarray):
                logger.info(f"  {attr_name}: shape={val.shape}, max={np.max(np.abs(val)):.6e}")
            else:
                logger.info(f"  {attr_name}: {val}")

    if bundle.takeoff is not None:
        logger.info(f"\n=== MALZEME METRAJI (TAKEOFF) ===")
        for attr_name in vars(bundle.takeoff):
            logger.info(f"  {attr_name}: {getattr(bundle.takeoff, attr_name)}")


if __name__ == "__main__":
    
    run_full_analysis_test("tests/testmodel1.s2k")

import logging

logger = logging.getLogger(__name__)

import numpy as np
from tools.s2kloader import S2KLoader
from core.analysis.solver import StructuralSolver
from core.analysis.assembler import ModelAssembler
from core.analysis.mass_source import build_global_mass_matrix

    
# ============================================================
# 1. MODEL YÜKLE
# ============================================================

app = S2KLoader("examples/testmodel.s2k")
scene = app.load()

node_map = {key: i for i, key in enumerate(scene.nodes.keys())}
num_dofs = len(scene.nodes) * 6
project_info = getattr(scene.def_mgr, "project_info", {})

site_info = project_info.get("site")
n = getattr(site_info, "live_load_factor", 0.3)

for key, node in scene.nodes.items():
    base = node_map[key] * 6
    node.dof_indices = list(range(base, base + 6))

logger.info(
    "Model: %d node, %d frame, %d area, %d link",
    len(scene.nodes),
    len(scene.frames),
    len(scene.areas),
    len(scene.links),
)
asm = ModelAssembler(scene, node_map, num_dofs)
K = asm.build_stiffness()
M, mass_report = build_global_mass_matrix(scene, num_dofs, n)

fixed_dofs = []
for key, node in scene.nodes.items():
    if node.restraint:
        base = node_map[key] * 6
        for i, dof_name in enumerate(node.DOF_ORDER):
            if getattr(node.restraint, dof_name, False):
                fixed_dofs.append(base + i)





logger.info(f"\n=== KÜTLE RAPORU === {mass_report['breakdown']}")



# logger.info(f"\nKilitli DOF: {len(fixed_dofs)}")


# # ============================================================
# # 5. ÇÖZÜCÜ
# # ============================================================

solver = StructuralSolver(K, M, fixed_dofs, num_dofs)


# ---- 5a. Statik analiz ----
F = np.zeros(num_dofs)
top_z = max(n.z for n in scene.nodes.values())
top_nodes = [k for k, n in scene.nodes.items()
             if np.isclose(n.z, top_z) and k not in [n for n in scene.nodes]]

if top_nodes:
    F[node_map[top_nodes[0]] * 6] = 1000.0  # 1 kN

U_static = solver.static_solve(F)
if top_nodes:
    top_ux = U_static[node_map[top_nodes[0]] * 6]
    logger.info(f"\nStatik: Tepe UX = {top_ux:.4f} mm")


# ---- 5b. Modal analiz ----
freqs, periods, modes, modal_dofs = solver.modal_solve(n_modes=10)

logger.info(f"\n=== MODAL ANALİZ ===")
for i in range(min(5, len(periods))):
    logger.info(f"Mod {i+1}: T = {periods[i]:.4f} s | f = {freqs[i]:.3f} Hz")


# ---- 5c. Spektral analiz ----
# 1. 'points' listesini değil, SpectrumFunction nesnesinin kendisini alıyoruz
spec_func = scene.def_mgr.spectrum_functions['ZD']

# SRSS birleştirme
U_modes = []
r_x = np.zeros(len(modal_dofs))
for i, dof in enumerate(modal_dofs):
    if dof % 6 == 0:
        r_x[i] = 1.0

M_mod = M[np.ix_(modal_dofs, modal_dofs)]

for n in range(min(6, len(periods))):
    phi = modes[:, n]
    T_n = periods[n]
    
    M_n = phi @ M_mod @ phi
    L_n = phi @ M_mod @ r_x
    Gamma = L_n / M_n if M_n > 0 else 0
    
    # 2. Periyoda (T_n) karşılık gelen Sa değerini noktalar üzerinden interpolasyonla çekiyoruz
    S_a = spec_func.get_sa(T_n) * 9810  # mm/s² (g cinsinden ivmeyi mm/s²'ye çeviriyorsan)
    w_n2 = (2 * np.pi / T_n) ** 2 if T_n > 0 else 1.0
    
    u_n = Gamma * (S_a / w_n2) * phi
    
    u_full = np.zeros(num_dofs)
    u_full[modal_dofs] = u_n
    U_modes.append(u_full)

U_srss = np.sqrt(np.sum([u**2 for u in U_modes], axis=0))

if top_nodes:
    top_ux = U_srss[node_map[top_nodes[0]] * 6]
    logger.info(f"\nSpektral (SRSS): Tepe UX = {top_ux:.2f} mm")
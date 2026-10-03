
from logging_config import CadLogger

from logging_config import CadLogger

logger = CadLogger.get(__name__)

import numpy as np
from tools.s2kloader import S2KLoader
from core.analysis import (
    ModelAssembler,
    read_mass_source,
    read_frame_loads,
    StructuralSolver,
    TBDYSpectrum,
    read_spectrum_from_parser,
)


# ============================================================
# 1. MODEL YÜKLE
# ============================================================

app = S2KLoader("examples/testmodel.s2k")
scene = app.load()

node_map = {key: i for i, key in enumerate(scene.nodes.keys())}
num_dofs = len(scene.nodes) * 6

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


# ============================================================
# 2. MASS SOURCE VE YÜKLER
# ============================================================

mass_source = read_mass_source(app.parser)
mass_source['frame_loads'] = read_frame_loads(app.parser)
mass_source['g'] = 9810.0

logger.info(
    "Mass source multipliers: %d Self weight mults: %d",
    mass_source['multipliers'],
    mass_source['self_weight_mults'],
)


# ============================================================
# 3. GLOBAL MATRİSLER
# ============================================================

asm = ModelAssembler(scene, node_map, num_dofs)
K = asm.build_stiffness()
M, mass_report = asm.build_mass(mass_source)


# ============================================================
# 4. SINIR KOŞULLARI
# ============================================================

fixed_dofs = []
for key, node in scene.nodes.items():
    if node.restraint:
        base = node_map[key] * 6
        for i, dof_name in enumerate(node.DOF_ORDER):
            if getattr(node.restraint, dof_name, False):
                fixed_dofs.append(base + i)

logger.info(f"\n=== KÜTLE RAPORU ===")
for pat, m in mass_report['user'].items():
    logger.info(f"  Kullanıcı {pat}: {m:.4f} ton")
for pat, m in mass_report['self'].items():
    logger.info(f"  Self {pat}:      {m:.4f} ton")
logger.info(f"  TOPLAM:         {sum(mass_report['user'].values()) + sum(mass_report['self'].values()):.4f} ton")


logger.info(f"\nKilitli DOF: {len(fixed_dofs)}")


# ============================================================
# 5. ÇÖZÜCÜ
# ============================================================

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
seismic = read_spectrum_from_parser(app.parser)
spec = TBDYSpectrum(**seismic)

logger.info(f"\n=== TBDY 2018 SPEKTRUM ===")
logger.info(spec.info())

# SRSS birleştirme (basit örnek)
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
    
    S_a = spec.S_ra(T_n) * 9810  # mm/s²
    w_n2 = (2 * np.pi / T_n) ** 2
    
    u_n = Gamma * (S_a / w_n2) * phi
    
    u_full = np.zeros(num_dofs)
    u_full[modal_dofs] = u_n
    U_modes.append(u_full)

U_srss = np.sqrt(np.sum([u**2 for u in U_modes], axis=0))

if top_nodes:
    top_ux = U_srss[node_map[top_nodes[0]] * 6]
    logger.info(f"\nSpektral (SRSS): Tepe UX = {top_ux:.2f} mm")
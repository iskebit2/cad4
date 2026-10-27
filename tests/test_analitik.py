import numpy as np

from core.analysis.solver import StructuralSolver
from domain.definition import Material, Section, Restraint
from domain.project import Project
from domain.element import Frame, Node

def local_collect_fixed_dofs(scene) -> list:
    fixed = []
    for node in scene.nodes.values():
        dofs = getattr(node, "dof_indices", None)
        if not dofs: continue
        r = getattr(node, "restraint", None)
        if r is None: continue
        for i, dof_name in enumerate(("ux", "uy", "uz", "rx", "ry", "rz")):
            if getattr(r, dof_name, False):
                if i < len(dofs) and dofs[i] is not None:
                    fixed.append(int(dofs[i]))
    return fixed
    
def local_stiffness(E, G, A, J, I33, I22, AS2, AS3, L, release_i=None, release_j=None, use_shear_deform=True):
    k = np.zeros((12, 12), dtype=float)
    ri = release_i or {}
    rj = release_j or {}
    def rel(d, code):
        return bool(d.get(code, False))
    if not (rel(ri, "R1") or rel(rj, "R1")):
        EA_L = E * A / L
        k[0, 0] += EA_L; k[6, 6] += EA_L; k[0, 6] -= EA_L; k[6, 0] -= EA_L
    if not (rel(ri, "R4") or rel(rj, "R4")):
        GJ_L = G * J / L
        k[3, 3] += GJ_L; k[9, 9] += GJ_L; k[3, 9] -= GJ_L; k[9, 3] -= GJ_L
    phi3 = 0.0
    if use_shear_deform and G > 0 and AS2 > 0 and I33 > 0:
        phi3 = (12.0 * E * I33) / (G * AS2 * L**2)
    denom3 = 1.0 + phi3
    a3 = 12.0 * E * I33 / (denom3 * L**3)
    b3 = 6.0 * E * I33 / (denom3 * L**2)
    c3 = (4.0 + phi3) * E * I33 / (denom3 * L)
    d3 = (2.0 - phi3) * E * I33 / (denom3 * L)
    k[1, 1] += a3;  k[1, 5] += b3;  k[1, 7] -= a3;  k[1, 11] += b3
    k[5, 1] += b3;  k[5, 5] += c3;  k[5, 7] -= b3;  k[5, 11] += d3
    k[7, 1] -= a3;  k[7, 5] -= b3;  k[7, 7] += a3;  k[7, 11] -= b3
    k[11, 1] += b3; k[11, 5] += d3; k[11, 7] -= b3; k[11, 11] += c3
    phi2 = 0.0
    if use_shear_deform and G > 0 and AS3 > 0 and I22 > 0:
        phi2 = (12.0 * E * I22) / (G * AS3 * L**2)
    denom2 = 1.0 + phi2
    a2 = 12.0 * E * I22 / (denom2 * L**3)
    b2 = 6.0 * E * I22 / (denom2 * L**2)
    c2 = (4.0 + phi2) * E * I22 / (denom2 * L)
    d2 = (2.0 - phi2) * E * I22 / (denom2 * L)
    k[2, 2] += a2;  k[2, 4] -= b2;  k[2, 8] -= a2;  k[2, 10] -= b2
    k[4, 2] -= b2;  k[4, 4] += c2;  k[4, 8] += b2;  k[4, 10] += d2
    k[8, 2] -= a2;  k[8, 4] += b2;  k[8, 8] += a2;  k[8, 10] += b2
    k[10, 2] -= b2; k[10, 4] += d2; k[10, 8] += b2; k[10, 10] += c2
    return 0.5 * (k + k.T)
    
def dynamic_build_stiffness(project, use_shear_deform=True):
    scene = project.scene
    for i, node in enumerate(scene.nodes.values()):
        node.dof_indices = list(range(i * 6, i * 6 + 6))
    num_dofs = len(scene.nodes) * 6
    K = np.zeros((num_dofs, num_dofs), dtype=float)

    for frame in scene.frames.values():
        sec = getattr(frame, "section", None)
        if not sec: continue
        mat = getattr(sec, "material", None)
        if not mat: continue
        params = sec.profile_params or {}
        A = float(params["Area"]) * float(params.get("AMod", 1.0))
        J = float(params["J"]) * float(params.get("JMod", 1.0))
        I33 = float(params["I33"]) * float(params.get("I3Mod", 1.0))
        I22 = float(params["I22"]) * float(params.get("I2Mod", 1.0))
        AS2 = float(params.get("AS2", A))
        AS3 = float(params.get("AS3", A))
        E = float(getattr(mat, "E1", 0.0))
        G = float(getattr(mat, "G12", 0.0))

        p1 = (frame.node_i.x, frame.node_i.y, frame.node_i.z)
        p2 = (frame.node_j.x, frame.node_j.y, frame.node_j.z)

        T, L = transformation_matrix(p1, p2, getattr(frame, "rotation_deg", 0.0) or 0.0)
        k_loc = local_stiffness(E, G, A, J, I33, I22, AS2, AS3, L,
                                getattr(frame, "release_i", None),
                                getattr(frame, "release_j", None),
                                use_shear_deform)
        k_glob = T.T @ k_loc @ T
        k_glob = 0.5 * (k_glob + k_glob.T)
        dofs = list(frame.node_i.dof_indices) + list(frame.node_j.dof_indices)
        K[np.ix_(dofs, dofs)] += k_glob

    K = 0.5 * (K + K.T)
    class TempStiff:
        def __init__(self, K, nd):
            self.K_global = K
            self.num_dofs = nd
    return TempStiff(K, num_dofs)

def transformation_matrix(p1, p2, beta_deg=0.0, up_global=(0.0, 0.0, 1.0)):
    import math
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    v = p2 - p1
    L = float(np.linalg.norm(v))
    if L < 1e-9:
        raise ValueError(f"Sıfır uzunluklu eleman: L={L}")
    e1 = v / L
    up = np.asarray(up_global, dtype=float)
    if abs(np.dot(e1, up)) > 0.9999:
        up = np.array([0.0, 1.0, 0.0]) if abs(e1[2]) > 0.9999 else np.array([0.0, 0.0, 1.0])
    e3 = np.cross(e1, up)
    e3 /= np.linalg.norm(e3)
    e2 = np.cross(e3, e1)
    if abs(beta_deg) > 1e-12:
        a = math.radians(beta_deg)
        ca, sa = math.cos(a), math.sin(a)
        e2, e3 = ca * e2 + sa * e3, -sa * e2 + ca * e3
    R = np.vstack([e1, e2, e3])
    T = np.kron(np.eye(4), R)
    return T, L

# --- TEST ÇALIŞTIRMA FONKSİYONU ---
def run_beam_test(section, L=6000.0, P_load_N=2500.0, axis='I33'):
    proj = Project()
    scn = proj.scene

    node_left = Node(x=0.0, y=0.0, z=0.0)
    node_mid = Node(x=L/2, y=0.0, z=0.0)
    node_right = Node(x=L, y=0.0, z=0.0)

    scn.add_node(node_left)
    scn.add_node(node_right)
    scn.add_node(node_mid)
    scn.add_frame(Frame(node_i=node_left, node_j=node_mid, section=section))
    scn.add_frame(Frame(node_i=node_mid, node_j=node_right, section=section))

    node_mid.restraint = Restraint(ux=False, uy=True, uz=False, rx=True, ry=False, rz=True)

    E = section.material.E1
    I_val = section.profile_params[axis]

    def solve(restraint):
        node_left.restraint = restraint
        node_right.restraint = restraint
        stiff_asm = dynamic_build_stiffness(proj, use_shear_deform=True)
        F = np.zeros(stiff_asm.num_dofs)
        F[node_mid.dof_indices[2]] = -P_load_N
        solver = StructuralSolver(stiff_asm.K_global, np.zeros_like(stiff_asm.K_global), local_collect_fixed_dofs(proj.scene), stiff_asm.num_dofs)
        return abs(solver.static_solve(F)[node_mid.dof_indices[2]])

    # Sonuçlar
    res_fixed = solve(Restraint(ux=True, uy=True, uz=True, rx=True, ry=True, rz=True))
    th_fixed = (P_load_N * (L**3)) / (192 * E * I_val)
    print(f"[{section.name} | {axis}] Ankastre -> Sayısal: {res_fixed:.6f} mm | Analitik: {th_fixed:.6f} mm")

    res_pinned = solve(Restraint(ux=True, uy=True, uz=True, rx=False, ry=False, rz=False))
    th_pinned = (P_load_N * (L**3)) / (48 * E * I_val)
    print(f"[{section.name} | {axis}] Pinned   -> Sayısal: {res_pinned:.6f} mm | Analitik: {th_pinned:.6f} mm\n")


# --- MALZEME VE KESİTLER ---
steel = Material(name='S275')
steel.E1 = 210000.0
steel.G12 = 80769.23
steel.density = 7.849e-06

box200 = Section(name="BOX200x200x10", material=steel)
box200.profile_params = {
    "Area": 200**2 - 180**2, "J": 3.61e8,
    "I33": (200**4 - 180**4) / 12, "I22": (200**4 - 180**4) / 12,
    "AS2": 0.0, "AS3": 0.0,
}

ipe200 = Section(name='IPE200', material=steel)
ipe200.profile_params = {
    'Area': 2850.0, 'J': 69200.0,
    'I33': 19430000.0, 'I22': 1420000.0,
    'AS2': 1120.0, 'AS3': 1416.667
}

# --- TESTLERİ ÇALIŞTIR ---
run_beam_test(box200, L=6000.0, P_load_N=2500.0, axis='I33')
run_beam_test(ipe200, L=6000.0, P_load_N=2500.0, axis='I22')

run_beam_test(ipe200, L=5000.0, P_load_N=1000.0, axis='I33')
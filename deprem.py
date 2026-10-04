from core.analysis.structuralanalysis import run_modal_analysis
from core.analysis.assembler import ModelAssembler
from tools.s2kloader import S2KLoader


# ============================================================
# MODEL
# ============================================================
file= "examples/testmodel.s2k"
app = S2KLoader(file)
scene = app.load()

node_map = {
    key: i
    for i, key in enumerate(scene.nodes.keys())
}

num_dofs = len(scene.nodes) * 6


# ============================================================
# DOF
# ============================================================

for i, node in enumerate(scene.nodes.values()):

    node.dof_indices = list(
        range(
            i * 6,
            i * 6 + 6
        )
    )


# ============================================================
# RİJİTLİK
# ============================================================

assembler = ModelAssembler(
    scene,
    node_map,
    num_dofs
)

K = assembler.build_stiffness()


# ============================================================
# MESNETLER
# ============================================================

fixed_dofs = []

for key, node in scene.nodes.items():

    if not node.restraint:
        continue

    base = node_map[key] * 6

    for i, dof_name in enumerate(
        node.DOF_ORDER
    ):

        if getattr(
            node.restraint,
            dof_name,
            False
        ):

            fixed_dofs.append(
                base + i
            )


# ============================================================
# SPEKTRUM
# ============================================================

project_info = getattr(
    scene.def_mgr,
    "project_info",
    {}
)

site_info = project_info.get(
    "site"
)

n = getattr(
    site_info,
    "live_load_factor",
    0.3
)

spectrum = (
    scene.def_mgr
    .spectrum_functions
    .get("ZD")
)


# ============================================================
# TEK ANALİZ
# ============================================================

result = run_modal_analysis(
    scene=scene,
    K=K,
    fixed_dofs=fixed_dofs,
    n=n,
    n_modes=10,
    spectrum=spectrum,
)

print(result)
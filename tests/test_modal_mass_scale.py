
from core.analysis.mass_assembly import build_mass
from core.analysis.solver import StructuralSolver
from core.analysis.stiffness_assembly import build_stiffness
from core.analysis.structuralanalysis import _collect_fixed_dofs
from tools.s2k import S2KLoader


def main():
    project = S2KLoader("tests/simple_ba1.s2k").load()
    scene = project.scene

    mass = build_mass(scene, project)
    stiff = build_stiffness(scene, project)
    fixed_dofs = _collect_fixed_dofs(scene)

    for scale in (1e-4, 1e-6, 1e-8, 1e-10):
        solver = StructuralSolver(
            K_global=stiff.K_global,
            M_global=mass.M_global,
            fixed_dofs=fixed_dofs,
            num_dofs=len(scene.nodes) * 6,
        )
        solver.ROT_MASS_SCALE = scale

        result = solver.modal_solve(n_modes=6)

        print(f"\nROT_MASS_SCALE = {scale:g}")
        for i, period in enumerate(result.periods, 1):
            print(f"  Mod {i}: T = {period:.6f} s")


if __name__ == "__main__":
    main()
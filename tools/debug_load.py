# tools/debug_load.py
from domain.project import Project
from core.analysis.material_takeoff import compute_takeoff
from logging_config import CadLogger
logger = CadLogger.get(__name__)

for path in ["betonarme.cd4", "test_model.cd4"]:
    logger.debug(f"\n{'='*60}\n{path}\n{'='*60}")
    p = Project.load(path)

    # Malzemeler
    for name, m in list(p.materials.items())[:5]:
        logger.debug(f"  {name:15s} density={m.density:.4e}  E1={m.E1:.0f}")

    # İlk 3 frame'in section.material'ı
    for f in list(p.scene.frames.values())[:3]:
        sec = f.section
        mat = sec.material if sec else None
        if mat:
            logger.debug(f"  Frame {f.label}: "
                  f"sec.mat.density={mat.density:.4e}, "
                  f"sec.mat.E1={mat.E1:.0f}")

    t = compute_takeoff(p.scene)
    logger.debug(f"  → {len(t.elements)} eleman, {t.total_mass_kg:.2f} kg "
          f"({t.total_mass_ton:.2f} ton)")
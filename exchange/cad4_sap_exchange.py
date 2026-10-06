# exchange/cad4_sap_exchange.py

from logging_config import CadLogger
from domain.importer import import_model

logger = CadLogger.get(__name__)


def import_sap_to_scene(sap, scene):
    """SAP2000 modelini mevcut CAD4 Scene'e aktarır."""

    if sap is None or sap.SapModel is None:
        raise RuntimeError("SAP bağlantısı yok")

    if scene is None:
        raise RuntimeError("Scene yok")

    # SAP -> domain
    model = import_model(sap)

    # domain -> Scene
    _add_definitions(scene, model)
    _add_elements(scene, model)

    return {
        "materials": len(model.get("materials", {})),
        "sections": len(model.get("sections", {})),
        "link_props": len(model.get("link_properties", {})),
        "nodes": len(model.get("nodes", {})),
        "frames": len(model.get("frames", {})),
        "areas": len(model.get("areas", {})),
        "links": len(model.get("links", {})),
    }


def _add_definitions(scene, model):
    def_mgr = scene.def_mgr

    for material in model.get("materials", {}).values():
        def_mgr.add_material(material)

    for section in model.get("sections", {}).values():
        def_mgr.add_section(section)

    for link_prop in model.get("link_properties", {}).values():
        def_mgr.add_link_prop(link_prop)


def _add_elements(scene, model):

    # Önce Node
    for node in model.get("nodes", {}).values():
        scene.add_node(node)

    # Sonra elemanlar
    for frame in model.get("frames", {}).values():
        scene.add_frame(frame)

    for area in model.get("areas", {}).values():
        scene.add_area(area)

    for link in model.get("links", {}).values():
        scene.add_link(link)
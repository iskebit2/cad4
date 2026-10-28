# tools/frame_to_link.py — TAM


from domain.definition import LinkPropLinear, LinkPropType
from domain.element import Frame, Link
from logging_config import CadLogger

logger = CadLogger.get(__name__)

DEFAULT_LINK_PROP_NAME = "DefaultLink"


def ensure_default_link_prop(project) -> LinkPropLinear:
    """Projede DefaultLink yoksa oluştur."""
    if DEFAULT_LINK_PROP_NAME in project.link_props:
        return project.link_props[DEFAULT_LINK_PROP_NAME]

    prop = LinkPropLinear(
        name=DEFAULT_LINK_PROP_NAME,
        prop_type=LinkPropType.LINEAR,
    )
    prop.DOF = {"U1": True, "U2": True, "U3": True,
                "R1": True, "R2": True, "R3": True}
    prop.Fixed = {}
    prop.Ke = {"U1": 0.0, "U2": 0.0, "U3": 0.0,
               "R1": 0.0, "R2": 0.0, "R3": 0.0}
    prop.Ce = {"U1": 0.0, "U2": 0.0, "U3": 0.0,
               "R1": 0.0, "R2": 0.0, "R3": 0.0}
    project.add_link_prop(prop)
    logger.info(f"[LinkProp] '{DEFAULT_LINK_PROP_NAME}' oluşturuldu")
    return prop


def frame_to_link(
    frame: Frame,
    link_prop_name: str = DEFAULT_LINK_PROP_NAME,
) -> tuple[Link | None, str | None]:
    """Bir Frame'i Link'e çevirir. Hata varsa (None, err) döner."""
    if frame.node_i is None or frame.node_j is None:
        return None, f"Frame '{frame.label}': node_i veya node_j eksik"

    link = Link(
        node_i=frame.node_i,
        node_j=frame.node_j,
        propname=link_prop_name,
        label=f"L{frame.label}",
    )
    if hasattr(frame, "color") and frame.color:
        link.color = list(frame.color[:3])

    return link, None


def convert_frames_to_links(
    scene,
    project,
    frames: list[Frame],
    link_prop_name: str = DEFAULT_LINK_PROP_NAME,
    delete_original: bool = True,
) -> dict:
    """
    Seçili Frame listesini Link'e çevir. Sonuç raporu döndürür.
    """
    report = {"converted": 0, "failed": 0, "errors": [], "new_links": []}

    # LinkProp kontrolü
    if link_prop_name not in project.link_props:
        logger.warning(
            f"[Frame→Link] '{link_prop_name}' projede yok, DefaultLink oluşturuluyor"
        )
        ensure_default_link_prop(project)
        link_prop_name = DEFAULT_LINK_PROP_NAME

    for frame in frames:
        link, err = frame_to_link(frame, link_prop_name=link_prop_name)
        if err:
            report["failed"] += 1
            report["errors"].append(err)
            logger.error(f"[Frame→Link] {err}")
            continue

        # Önce Link'i ekle
        scene.add_link(link)
        report["new_links"].append(link)

        # Sonra Frame'i sil / gizle
        if delete_original:
            ok = scene.remove_element(frame)
            if not ok:
                logger.warning(f"[Frame→Link] Frame '{frame.label}' silinemedi")
        else:
            frame.is_visible = False
            frame.mark_dirty()

        report["converted"] += 1

    scene.mark_dirty()
    logger.info(
        f"[Frame→Link] converted={report['converted']}, "
        f"failed={report['failed']}"
    )
    return report
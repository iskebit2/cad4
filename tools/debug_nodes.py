# tools/debug_nodes.py
"""
Node render debug komutu.

Kullanım (uygulama içinden veya Python konsolundan):
    from tools.debug_nodes import debug_nodes
    debug_nodes(app)

    # veya sadece engine ile:
    from tools.debug_nodes import debug_nodes
    debug_nodes(app=None, engine=engine)
"""
from __future__ import annotations

from logging_config import CadLogger

logger = CadLogger.get(__name__)


def debug_nodes(app=None, engine=None) -> dict:
    """Node render pipeline'ını tüm katmanlarda kontrol eder.
    
    Returns:
        dict: Her katmanın kontrol sonucu.
    """
    if engine is None and app is not None:
        engine = getattr(app, "engine", None)
    if engine is None:
        logger.error("[DEBUG_NODES] engine yok")
        return {}

    result = {}
    logger.error("=" * 60)
    logger.error("[DEBUG_NODES] Node render teşhisi başlıyor")
    logger.error("=" * 60)

    # --- 1. Engine show flags ---
    show_node = engine.show.get("node", None)
    show_scene = engine.show.get("scene", None)
    show_interaction = engine.show.get("interaction", None)
    logger.error(
        "[DEBUG_NODES] engine.show: node=%s scene=%s interaction=%s",
        show_node, show_scene, show_interaction,
    )
    result["show_node"] = show_node

    # --- 2. MathModel domain ---
    mm = getattr(engine, "math_model", None)
    if mm is None:
        logger.error("[DEBUG_NODES] math_model yok")
        return result
    all_nodes = list(mm.nodes.values())
    visible_nodes = [n for n in all_nodes if getattr(n, "is_visible", True)]
    logger.error(
        "[DEBUG_NODES] math_model.nodes: total=%d visible=%d",
        len(all_nodes), len(visible_nodes),
    )
    result["nodes_total"] = len(all_nodes)
    result["nodes_visible"] = len(visible_nodes)

    # Örnek node bilgisi
    if all_nodes:
        n = all_nodes[0]
        logger.error(
            "[DEBUG_NODES] örnek node: uid=%s label=%r pos=(%.2f,%.2f,%.2f) "
            "is_visible=%s is_selected=%s restraint=%s",
            getattr(n, "unique_id", "?"),
            getattr(n, "label", ""),
            getattr(n, "x", 0.0), getattr(n, "y", 0.0), getattr(n, "z", 0.0),
            getattr(n, "is_visible", None),
            getattr(n, "is_selected", None),
            getattr(n, "restraint", None),
        )

    # --- 3. Renderer elements ---
    mmr = getattr(engine.renderer, "math_model_renderer", None) if engine.renderer else None
    if mmr is None:
        logger.error("[DEBUG_NODES] math_model_renderer yok")
        return result
    node_r = getattr(mmr, "node_r", None)
    if node_r is None:
        logger.error("[DEBUG_NODES] node_r yok")
        return result

    logger.error(
        "[DEBUG_NODES] node_r: elements=%d vao=%s vcount=%d icount=%d "
        "simple_vao=%s simple_vcount=%d rlines_vcount=%d",
        len(node_r.elements),
        node_r.vao,
        node_r.vcount,
        node_r.icount,
        node_r.simple_vao,
        node_r.simple_vcount,
        getattr(node_r, "rlines_vcount", 0),
    )
    result["node_r_elements"] = len(node_r.elements)
    result["node_r_vcount"] = node_r.vcount
    result["node_r_icount"] = node_r.icount
    result["node_r_simple_vcount"] = node_r.simple_vcount
    result["node_r_simple_vao"] = bool(node_r.simple_vao)
    result["node_r_vao"] = bool(node_r.vao)

    # --- 4. show flag on math_model_renderer ---
    logger.error(
        "[DEBUG_NODES] mmr.show: node=%s frame=%s area=%s link=%s",
        mmr.show.get("node"),
        mmr.show.get("frame"),
        mmr.show.get("area"),
        mmr.show.get("link"),
    )
    result["mmr_show_node"] = mmr.show.get("node")
    result["render_mode"] = mmr.render_mode
    logger.error("[DEBUG_NODES] render_mode=%s", mmr.render_mode)

    # --- 5. node shader ---
    # render_simple içinde kullanılan gerçek shader:
    actual_shader = getattr(mmr, "node_shader", None)   # ← _render_simple bunu kullanıyor
    if actual_shader is None:
        logger.error("[DEBUG_NODES] mmr.node_shader = None")
    else:
        logger.error("[DEBUG_NODES] mmr.node_shader = %s", actual_shader)
        try:
            locs = {}
            for name in ("mvp", "model", "normalMatrix", "pointSize",
                        "isConstantSize", "pointScale", "alpha",
                        "renderMode", "useVertexColor"):
                locs[name] = actual_shader.get_loc(name)
            logger.error("[DEBUG_NODES] ACTUAL node shader uniform locs: %s", locs)
            result["actual_shader_locs"] = locs
        except Exception as e:
            logger.error("[DEBUG_NODES] uniform loc hatası: %s", e)

    
    

    # --- 6. NodeBuilder durumu ---
    builder = getattr(node_r, "builder", None)
    if builder is not None:
        logger.error(
            "[DEBUG_NODES] builder: point_size=%s node_size=%s",
            getattr(node_r, "point_size", None),
            getattr(builder, "size", None),
        )

    # --- 7. visible_ids etkisi ---
    try:
        vm = getattr(app, "viewport_manager", None) if app else None
        if vm:
            for name, vp in vm.viewports.items():
                vis = getattr(vp, "visible_ids", None)
                node_in_vis = None
                if vis is not None and visible_nodes:
                    node_in_vis = visible_nodes[0].unique_id in vis
                logger.error(
                    "[DEBUG_NODES] viewport %r: visible_ids=%s "
                    "örnek_node_in_vis=%s is_2d=%s plane=%s",
                    name,
                    "None" if vis is None else f"{len(vis)} eleman",
                    node_in_vis,
                    getattr(vp, "is_2d", False),
                    getattr(getattr(vp, "plane", None), "name", None),
                )
    except Exception as e:
        logger.error("[DEBUG_NODES] viewport bilgisi hatası: %s", e)

    # --- 8. Kamera ve pick ---
    cam = getattr(engine, "cam", None)
    if cam is not None:
        logger.error(
            "[DEBUG_NODES] cam: pos=(%.2f,%.2f,%.2f) yaw=%.1f pitch=%.1f "
            "distance=%.2f ortho=%s",
            cam.position.x, cam.position.y, cam.position.z,
            getattr(cam, "yaw", 0.0),
            getattr(cam, "pitch", 0.0),
            getattr(cam, "distance", 0.0),
            getattr(cam, "use_ortho", None),
        )

    logger.error("=" * 60)
    return result


def debug_nodes_pick(app, screen_x: int, screen_y: int) -> int:
    """Belirli bir ekran noktasında node pick ID'sini döndür (senkron okuma).
    
    Node'un render edilip edilmediğini anlamak için: pick ID 0 değilse
    node ID buffer'a yazılıyor demektir. Görsel shader sorunu olabilir.
    """
    engine = getattr(app, "engine", None) if app else None
    if engine is None or engine.renderer is None:
        logger.error("[DEBUG_NODES_PICK] engine/renderer yok")
        return 0
    pp = engine.renderer.pick_pass
    if pp is None:
        logger.error("[DEBUG_NODES_PICK] pick_pass yok")
        return 0

    w, h = engine.w, engine.h
    if not (0 <= screen_x < w and 0 <= screen_y < h):
        logger.error("[DEBUG_NODES_PICK] koordinat aralık dışı")
        return 0

    # Senkron okuma (pick_async'in PBO'suz hali)
    import numpy as np
    from OpenGL.GL import (
        glBindFramebuffer, glReadBuffer, glReadPixels, glBindFramebuffer,
        GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT1, GL_RED_INTEGER,
        GL_UNSIGNED_INT, GL_PACK_ALIGNMENT, glPixelStorei,
    )
    size = pp.pick_size
    half = pp.pick_half
    x0 = max(0, min(screen_x - half, w - size))
    y0 = max(0, min(screen_y - half, h - size))
    y_gl = h - y0 - size

    buf = np.zeros((size, size), dtype=np.uint32)
    glBindFramebuffer(GL_READ_FRAMEBUFFER, pp.main_fbo)
    glReadBuffer(GL_COLOR_ATTACHMENT1)
    glPixelStorei(GL_PACK_ALIGNMENT, 1)
    glReadPixels(x0, y_gl, size, size, GL_RED_INTEGER, GL_UNSIGNED_INT,
                 buf.ctypes.data_as(__import__("ctypes").c_void_p))
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)

    ids = sorted(set(int(v) for v in buf.flatten() if v > 0))
    logger.error(
        "[DEBUG_NODES_PICK] xy=(%d,%d) ids=%s", screen_x, screen_y, ids,
    )
    if ids:
        el = pp.get_element(ids[0])
        if el is not None:
            logger.error(
                "[DEBUG_NODES_PICK] ilk id=%d element=%s label=%r",
                ids[0], type(el).__name__, getattr(el, "label", ""),
            )
        return ids[0]
    return 0

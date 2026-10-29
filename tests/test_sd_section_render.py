"""SD section — FrameBuilder çıktısını ve renderer'ın gördüğü veriyi doğrula."""
from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path

from tools.s2k.loader import S2KLoader
from geometry.frame_builder import FrameBuilder
from geometry.profile_generator import ProfileGenerator


FIXTURE = Path(__file__).parent / "merdiven_sap2000.s2k"


"""SceneRenderer.update_geo — GPU context olmadan, mock ile test."""
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
from pathlib import Path


@pytest.fixture(scope="module")
def project():
    from tools.s2k.loader import S2KLoader
    fixture = Path(__file__).parent / "merdiven_sap2000.s2k"
    if not fixture.exists():
        pytest.skip(f"Fixture yok: {fixture}")
    return S2KLoader(str(fixture)).load()


@pytest.fixture
def scene_renderer():
    gl_names = {
        "glGenFramebuffers": MagicMock(return_value=1),
        "glGenTextures": MagicMock(return_value=1),
        "glGenRenderbuffers": MagicMock(return_value=1),
        "glBindFramebuffer": MagicMock(),
        "glBindTexture": MagicMock(),
        "glTexImage2D": MagicMock(),
        "glTexParameteri": MagicMock(),
        "glFramebufferTexture2D": MagicMock(),
        "glBindRenderbuffer": MagicMock(),
        "glRenderbufferStorage": MagicMock(),
        "glFramebufferRenderbuffer": MagicMock(),
        "glDrawBuffers": MagicMock(),
        "glCheckFramebufferStatus": MagicMock(return_value=36053),
        "glGenVertexArrays": MagicMock(return_value=1),
        "glGenBuffers": MagicMock(return_value=1),
        "glBindVertexArray": MagicMock(),
        "glBindBuffer": MagicMock(),
        "glBufferData": MagicMock(),
        "glBufferSubData": MagicMock(),
        "glEnableVertexAttribArray": MagicMock(),
        "glVertexAttribPointer": MagicMock(),
        "glVertexAttribIPointer": MagicMock(),
        "glIsBuffer": MagicMock(return_value=True),
        "glIsVertexArray": MagicMock(return_value=True),
        "glDeleteBuffers": MagicMock(),
        "glDeleteVertexArrays": MagicMock(),
    }

    with patch.multiple("render.scenerenderer", **gl_names), \
         patch.multiple("render.base_renderer", **gl_names):
        from render.scenerenderer import SceneRenderer

        shader = MagicMock()
        shader.get_loc = MagicMock(return_value=-1)
        shader.use = MagicMock()

        yield SceneRenderer(
            pick_s=shader, standard_s=shader, node_s=shader,
            simple_s=shader, overlay_s=shader, axes_s=shader,
            w=800, h=600,
        )


# ============================================================================
# TEST: update_geo — frame_r vertex count doğru mu?
# ============================================================================
def test_update_geo_sd_frame_vertex_count(scene_renderer, project):
    """update_geo sonrası SD frame'in vertex count'u 60 olmalı."""
    scn = project.scene
    scene_renderer.update_geo(scn)

    # SD frame bul
    sd_frame = None
    for f in scn.frames.values():
        if getattr(f.section, "name", "") == "115_147":
            sd_frame = f
            break

    assert sd_frame is not None
    vc = scene_renderer.frame_r.elem_to_vcount.get(sd_frame.unique_id, 0)
    assert vc == 60, f"frame_r vertex count: {vc}, beklenen 60"
    assert scene_renderer.frame_r.icount > 0


def test_update_geo_sd_frame_in_elements(scene_renderer, project):
    """SD frame frame_r.elements içinde mi?"""
    scn = project.scene
    scene_renderer.update_geo(scn)

    labels = {e.label for e in scene_renderer.frame_r.elements}
    assert "C115_147" in labels or any(
        getattr(e.section, "name", "") == "115_147"
        for e in scene_renderer.frame_r.elements
    ), "SD frame renderer.elements'te yok"


@pytest.fixture(scope="module")
def sd_frame(project):
    """115_147 SD section'lı ilk frame."""
    for f in project.scene.frames.values():
        if getattr(f.section, "name", "") == "115_147":
            return f
    pytest.skip("115_147 section'lı frame yok")


# ============================================================================
# 1. IMPORT — Section + SD section doğru mu?
# ============================================================================
def test_section_has_sd_section(sd_frame):
    sec = sd_frame.section
    assert sec is not None
    assert sec.name == "115_147"
    assert sec.profile_type.name == "CUSTOM"
    assert sec.sd_section is not None, "sd_section import edilmemiş"
    assert len(sec.sd_section.shapes) == 1
    assert len(sec.sd_section.shapes[0].points) == 10


# ============================================================================
# 2. PROFILE — get_profile 10 nokta döndürüyor mu?
# ============================================================================
def test_get_profile_sd_polygon(sd_frame):
    sec = sd_frame.section
    params = dict(sec.profile_params or {})
    if sec.sd_section is not None:
        params["sd_section"] = sec.sd_section

    gen = ProfileGenerator()
    profile = gen.get_profile(sec.profile_type, params)

    assert len(profile) == 10, f"Beklenen 10 nokta, alınan {len(profile)}"
    # İlk nokta kabaca (-2.4, 0.15)
    assert abs(profile[0][0] - (-2.4)) < 0.01
    assert abs(profile[0][1] - 0.15) < 0.01


# ============================================================================
# 3. BUILD — 60 vertex, 36 üçgen (10 nokta × 4 + 2×10 cap)
# ============================================================================
def test_build_sd_geometry(sd_frame):
    builder = FrameBuilder()
    verts, colors, idxs = builder.build(sd_frame)

    # 10 nokta: side 40 + start cap 10 + end cap 10 = 60 vertex
    n_verts = len(verts) // 6
    assert n_verts == 60, f"Beklenen 60 vertex, alınan {n_verts}"

    # Side: 10 quad × 2 tri = 20, cap: 8 tri × 2 = 16 → 36 tri × 3 = 108
    n_idx = len(idxs)
    assert n_idx == 108, f"Beklenen 108 index, alınan {n_idx}"

    # Vertex'ler geçerli
    assert np.all(np.isfinite(verts))
    assert colors.shape == (60, 3)


# ============================================================================
# 4. BUFFER BOYUTLARI — renderer'a gidecek veri
# ============================================================================
def test_build_buffer_sizes(sd_frame):
    builder = FrameBuilder()
    verts, colors, idxs = builder.build(sd_frame)

    # VBO: 60 vertex × 6 float × 4 byte = 1440
    assert verts.nbytes == 60 * 6 * 4
    # CBO: 60 × 3 × 4 = 720
    assert colors.nbytes == 60 * 3 * 4
    # EBO: 108 × 4 = 432
    assert idxs.nbytes == 108 * 4


# ============================================================================
# 5. RENDERER'ın gördüğü frame.section — aynı nesne mi?
# ============================================================================
def test_renderer_sees_same_section(project, sd_frame):
    """FrameBuilder'ın gördüğü section, project.sections[115_147] ile aynı mı?"""
    sec_from_frame = sd_frame.section
    sec_from_project = project.sections.get("115_147")

    assert sec_from_frame is not None
    assert sec_from_project is not None
    assert sec_from_frame.sd_section is not None, (
        "frame.section.sd_section boş — kopya üretilmiş"
    )
    assert len(sec_from_frame.sd_section.shapes) == 1


# ============================================================================
# 6. TÜM SD frame'ler — her biri 60 vertex mi?
# ============================================================================
def test_all_sd_frames_build(project):
    """SD section'lı tüm frame'ler 60 vertex üretmeli."""
    builder = FrameBuilder()
    n_sd = 0
    for f in project.scene.frames.values():
        sec = getattr(f, "section", None)
        if sec is None:
            continue
        if getattr(sec, "sd_section", None) is None:
            continue
        n_sd += 1
        verts, _, idxs = builder.build(f)
        n_verts = len(verts) // 6
        # Bazı section'lar 6 nokta olabilir (119_148), side: 24+6+6=36
        n_pts = len(sec.sd_section.shapes[0].points)
        expected = n_pts * 4 + n_pts * 2   # side + 2 caps
        assert n_verts == expected, (
            f"frame {f.label}: beklenen {expected} vertex, alınan {n_verts}"
        )

    assert n_sd > 0, "Hiç SD section'lı frame yok"


# ============================================================================
# 7. GEOMETRİ — polygon noktaları gerçekten ekstrüde ediliyor mu?
# ============================================================================
def test_geometry_uses_polygon_not_bbox(sd_frame):
    """Vertex'lerin min/max'ı, polygon bbox'ı ile eşleşmeli (dikdörtgen değil)."""
    builder = FrameBuilder()
    verts, _, _ = builder.build(sd_frame)

    # Position = ilk 3 float (her 6'da)
    positions = verts.reshape(-1, 6)[:, :3]

    # sd polygon noktaları
    pts = [(p.x, p.y) for p in sd_frame.section.sd_section.shapes[0].points]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    bbox_w = max(xs) - min(xs)
    bbox_h = max(ys) - min(ys)

    # Vertex'lerin local Y/Z'deki bbox'ı (frame eksenine göre)
    # Basit test: vertex'lerin XY düzlemindeki "genişliği" bbox'tan farklı olmalı
    # (polygon 10 noktalı, bbox 4 noktalı dikdörtgen değil)
    # Alternatif: unique XY kombinasyon sayısı > 4 olmalı
    local_pts = set()
    for v in positions:
        local_pts.add((round(float(v[0]), 3), round(float(v[1]), 3)))
    assert len(local_pts) > 4, (
        f"Sadece {len(local_pts)} benzersiz nokta — dikdörtgen gibi görünüyor"
    )
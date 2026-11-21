# ui/widgets/icon_manager.py
from __future__ import annotations

import base64
from io import BytesIO

import OpenGL.GL as gl
from PIL import Image

from assets.icons_base64 import ICON_DATA
# _ICONS dosya yolu map'i artık gerekmiyor — ICON_DATA anahtar bazlı.


class IconManager:
    def __init__(self) -> None:
        self._textures: dict[str, tuple[int, int, int]] = {}
        self._failed: set[str] = set()

    def has(self, icon_name: str) -> bool:
        return icon_name in ICON_DATA

    def get_texture(self, icon_name: str | None):
        
        if not icon_name or icon_name in self._failed:
            return None
        if icon_name not in ICON_DATA:
            self._failed.add(icon_name)
            return None
        cached = self._textures.get(icon_name)
        if cached is not None:
            return cached
        try:
            img_data = base64.b64decode(ICON_DATA[icon_name])
            img = Image.open(BytesIO(img_data)).convert("RGBA")
            w, h = img.size
            raw = img.tobytes("raw", "RGBA")

            tex_id = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, w, h,
                0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, raw,
            )
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

            entry = (tex_id, w, h)
            self._textures[icon_name] = entry
            return entry
        except Exception as e:
            print(f"[IconManager] '{icon_name}' yüklenemedi: {e}")
            self._failed.add(icon_name)
            return None
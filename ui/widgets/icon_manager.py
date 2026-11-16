# ui/widgets/icon_manager.py
from __future__ import annotations

import base64
from io import BytesIO

import OpenGL.GL as gl
from PIL import Image

from assets.icons_base64 import ICON_DATA


class IconManager:
    def __init__(self) -> None:
        self._textures: dict[str, tuple[int, int, int]] = {}
        self._failed: set[str] = set()
        print(f"[IconManager] {len(ICON_DATA)} ikon mevcut: {list(ICON_DATA.keys())[:5]}...")

    def get_texture(self, icon_name):
        if not icon_name:
            return None
        if icon_name in self._failed:
            return None
        if icon_name not in ICON_DATA:
            print(f"[IconManager] '{icon_name}' ICON_DATA'da YOK. Mevcut: {list(ICON_DATA.keys())}")
            self._failed.add(icon_name)
            return None
        if icon_name in self._textures:
            return self._textures[icon_name]
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

            self._textures[icon_name] = (tex_id, w, h)
            return self._textures[icon_name]
        except Exception as e:
            print(f"[IconManager Error] Failed to load icon '{icon_name}': {e}")
            return None
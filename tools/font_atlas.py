# tools/font_atlas.py
"""
Basit font atlas — TTF'den bitmap atlas üretir.
- Her karakter için UV + advance + bearing saklar.
- Tek texture olarak GPU'ya yüklenir.
- Binlerce label için tek draw call'lık sistemin temelidir.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from logging_config import CadLogger
logger = CadLogger.get(__name__)

@dataclass(frozen=True)
class Glyph:
    u0: float
    v0: float
    u1: float
    v1: float
    width: int          # piksel (bitmap içindeki glyph genişliği)
    height: int         # piksel
    bearing_x: int      # sol boşluk
    bearing_y: int      # baseline'dan yukarı offset
    advance: float      # bir sonraki karaktere yatay adım


class FontAtlas:
    """
    Tek texture'da birden fazla glyph barındıran bitmap font atlası.

    Kullanım:
        atlas = FontAtlas("C:/Windows/Fonts/consola.ttf", size=32)
        atlas.upload()
        atlas.glyphs['A'].u0 ...
    """

    # Atlas'a koyulacak karakterler. İhtiyaca göre genişlet.
    DEFAULT_CHARS = (
        "0123456789"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        ".,-+:;=_/\\()[]{}<>#%&*'\"!?@$^|~`"
        " "
    )

    def __init__(self, ttf_path: Optional[str] = None,
                 size: int = 32,
                 chars: Optional[str] = None,
                 padding: int = 2,
                 supersample: int = 1):
        """
        Parameters
        ----------
        ttf_path : str | None
            None ise PIL default font kullanılır (küçük ve çirkin ama çalışır).
        size : int
            Font boyutu (piksel).
        chars : str | None
            Atlas'a dahil edilecek karakterler.
        padding : int
            Karakterler arası boşluk (bleeding'i önler).
        supersample : int
            >1 ise font SS× büyük render edilir, sonra küçültülür (daha yumuşak).
        """
        self.ttf_path = ttf_path
        self.size = size
        self.padding = padding
        self.supersample = max(1, supersample)
        self.chars = chars if chars is not None else self.DEFAULT_CHARS

        # Font yükle
        render_size = self.size * self.supersample
        if ttf_path and os.path.isfile(ttf_path):
            self.font = ImageFont.truetype(ttf_path, render_size)
        else:
            # Windows/Linux/Mac default'larını dene
            fallbacks = [
                "C:/Windows/Fonts/consola.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/System/Library/Fonts/Monaco.ttf",
            ]
            loaded = False
            for fp in fallbacks:
                if os.path.isfile(fp):
                    self.font = ImageFont.truetype(fp, render_size)
                    loaded = True
                    break
            if not loaded:
                self.font = ImageFont.load_default()

        self.glyphs: Dict[str, Glyph] = {}
        self.texture_id: int = 0
        self.width: int = 0
        self.height: int = 0
        self.pixels: Optional[np.ndarray] = None

        # Baseline bilgisi (satır yüksekliği)
        try:
            ascent, descent = self.font.getmetrics()
        except Exception:
            ascent, descent = self.size, self.size // 4
        # Supersample'lı font olduğu için böl
        self.ascent = ascent / self.supersample
        self.descent = descent / self.supersample
        self.line_height = (ascent + descent) / self.supersample

        self._build()

    def _build(self):
        """Atlas image'ını üretir, glyph metriklerini doldurur."""
        # Her glyph için boyut ölç
        rendered: List[Tuple[str, Image.Image, int, int, float]] = []
        max_w = 0
        max_h = 0

        for ch in self.chars:
            try:
                bbox = self.font.getbbox(ch)
            except Exception:
                bbox = (0, 0, self.size, self.size)
            w = max(1, bbox[2] - bbox[0])
            h = max(1, bbox[3] - bbox[1])
            advance = self.font.getlength(ch)

            # Glyph bitmap
            img = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(img)
            draw.text((-bbox[0], -bbox[1]), ch, fill=255, font=self.font)

            rendered.append((ch, img, bbox[0], bbox[1], advance))
            max_w = max(max_w, w)
            max_h = max(max_h, h)

        # Atlas yerleşimi (grid)
        cols = max(1, int(np.ceil(np.sqrt(len(rendered)))))
        rows = int(np.ceil(len(rendered) / cols))

        cell_w = max_w + self.padding * 2
        cell_h = max_h + self.padding * 2
        atlas_w = cols * cell_w
        atlas_h = rows * cell_h

        atlas = Image.new("L", (atlas_w, atlas_h), 0)

        for i, (ch, img, bx, by, advance) in enumerate(rendered):
            col = i % cols
            row = i // cols
            cx = col * cell_w + self.padding
            cy = row * cell_h + self.padding

            atlas.paste(img, (cx, cy))

            u0 = cx / atlas_w
            v0 = cy / atlas_h
            u1 = (cx + img.width) / atlas_w
            v1 = (cy + img.height) / atlas_h

            self.glyphs[ch] = Glyph(
                u0=u0, v0=v0, u1=u1, v1=v1,
                width=img.width,
                height=img.height,
                bearing_x=bx,
                bearing_y=by,
                advance=advance / self.supersample,   # supersample'lı ölçüyü böl
            )

        self.width = atlas_w
        self.height = atlas_h
        self.pixels = np.array(atlas, dtype=np.uint8)

        # İsteğe bağlı: SS>1 ise küçült (daha yumuşak kenar)
        if self.supersample > 1:
            big = Image.fromarray(self.pixels, mode="L")
            small = big.resize(
                (atlas_w // self.supersample, atlas_h // self.supersample),
                Image.LANCZOS,
            )
            self.width = small.width
            self.height = small.height
            self.pixels = np.array(small, dtype=np.uint8)
            # UV'leri yeniden ölçekle
            scale_u = atlas_w / self.width
            scale_v = atlas_h / self.height
            self.glyphs = {
                ch: Glyph(
                    u0=g.u0, v0=g.v0, u1=g.u1, v1=g.v1,   # UV zaten 0-1 normalize
                    width=max(1, g.width // self.supersample),
                    height=max(1, g.height // self.supersample),
                    bearing_x=g.bearing_x // self.supersample,
                    bearing_y=g.bearing_y // self.supersample,
                    advance=g.advance,
                )
                for ch, g in self.glyphs.items()
            }

    # ------------------------------------------------------------------
    def upload(self):
        from OpenGL.GL import (
            glGenTextures, glBindTexture, glTexImage2D, glTexParameteri,
            glPixelStorei,
            GL_TEXTURE_2D, GL_R8, GL_RED, GL_UNSIGNED_BYTE,
            GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
            GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE,
            GL_UNPACK_ALIGNMENT,
        )

        if self.texture_id:
            return self.texture_id

        # ---- DEBUG: atlas'ı diske kaydet ----
        try:
            from PIL import Image
            Image.fromarray(self.pixels, mode="L").save("_atlas_debug.png")
            logger.debug(f"[Atlas] {self.width}x{self.height} kaydedildi: _atlas_debug.png")
            logger.debug(f"[Atlas] pixel min/max: {self.pixels.min()}/{self.pixels.max()}")
        except Exception as e:
            logger.debug(f"[Atlas] debug kaydedilemedi: {e}")

        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)

        # R8 — tek kanal
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_R8,
            self.width, self.height, 0,
            GL_RED, GL_UNSIGNED_BYTE,
            self.pixels.tobytes(),
        )

        # !! Swizzle'ı KALDIR — fragment .r okuyor !!
        # glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_R, GL_ALPHA)   # <-- SİL

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

        glBindTexture(GL_TEXTURE_2D, 0)
        self.texture_id = tex
        logger.debug(f"[Atlas] texture id={tex}")
        return tex

    # ------------------------------------------------------------------
    def measure(self, text: str, pixel_size: float) -> Tuple[float, float]:
        """
        Verilen metnin `pixel_size` yüksekliğinde piksel cinsinden boyutunu döner.
        (width, height)
        """
        # Font size 32 varsayılan; ölçek faktörü:
        k = pixel_size / float(self.size)
        w = 0.0
        for ch in text:
            g = self.glyphs.get(ch)
            if g is None:
                g = self.glyphs.get(" ")
                if g is None:
                    continue
            w += g.advance * k
        return w, self.line_height * k

    # ------------------------------------------------------------------
    def cleanup(self):
        from OpenGL.GL import glDeleteTextures, glIsTexture
        if self.texture_id and glIsTexture(self.texture_id):
            try:
                glDeleteTextures(1, [int(self.texture_id)])
            except Exception:
                pass
        self.texture_id = 0
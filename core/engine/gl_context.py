# core/engine/gl_context.py
from __future__ import annotations

from pathlib import Path

from OpenGL.GL import glGetString, GL_VERSION

from render.shaderprogram import ShaderProgram
from logging_config import CadLogger

logger = CadLogger.get(__name__)

SHADER_DIR = Path(__file__).resolve().parent.parent.parent / "render" / "shaders"

SHADER_NAMES = ("pick", "standard", "node", "simple", "2d_overlay", "preview", "grid", "axes")


class GLContext:
    """GL init + shader yükleme. Engine/app bilmez."""

    def __init__(self, width: int, height: int, shader_dir: Path | None = None) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.shader_dir = Path(shader_dir) if shader_dir else SHADER_DIR
        self.shaders: dict[str, ShaderProgram | None] = {}
        self._initialized = False

    def init(self) -> None:
        if self._initialized:
            return
        logger.info("GL_VERSION: %s", glGetString(GL_VERSION))
        self._load_shaders()
        self._initialized = True

    def _load_shaders(self) -> None:
        for name in SHADER_NAMES:
            vert = self.shader_dir / f"{name}.vert"
            frag = self.shader_dir / f"{name}.frag"
            try:
                self.shaders[name] = ShaderProgram(name, str(vert), str(frag))
            except Exception:
                logger.exception("Shader yükleme hatası: %s", name)
                self.shaders[name] = None

    def resize(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))

    def get(self, name: str) -> ShaderProgram | None:
        return self.shaders.get(name)
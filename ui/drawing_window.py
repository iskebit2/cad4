"""
drawing_window.py - Bağımsız 3D Görüntüleyici Pencere
"""
import sys
from logging_config import CadLogger
from typing import Optional, List, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QStatusBar, QToolBar, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QSurfaceFormat

from domain.scene import Scene
from geometry.scenebuilder import SceneBuilder
from domain.definition import SectionType, MatType
from core.qt_engine import RenderEngineWidget, InteractionMode

from logging_config import CadLogger

logger = CadLogger.get(__name__)


class DrawingWindow(QMainWindow):
    """3D Görüntüleyici Pencere"""

    def __init__(self, scene: Optional[Scene] = None, parent=None):
        super().__init__(parent)

        # === Pencere Ayarları ===
        self.setWindowTitle("CAD3 - 3D Görüntüleyici")
        self.setGeometry(100, 100, 1280, 720)
        self.setMinimumSize(800, 600)

        self._scene = scene

        # === Ana Widget (Viewport'u tam ekran kaplayacak) ===
        container = QWidget(self)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(container)
        
        # Layout - hiç margin/spacing olmasın
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === Engine Widget (Tam ekran) ===
        self._engine = RenderEngineWidget(parent=self)
        if self._scene is not None and hasattr(self._engine, 'set_scene'):
            self._engine.set_scene(self._scene)
        self._engine.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._engine)

        # === Status Bar ===
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Sistem Hazır - 3D Viewport Etkin")

        # === UI Bileşenleri ===
        self._setup_menu()
        self._setup_toolbar()

        # === Sinyal Bağlantıları ===
        self._engine.selection_changed.connect(self._on_selection_changed)
        self._engine.status_message.connect(self._status_bar.showMessage)
        self._engine.mode_changed.connect(self._on_mode_changed)

        logger.info("DrawingWindow başlatıldı.")

    # ==================== UI Kurulumu ====================

    def _setup_menu(self):
        menubar = self.menuBar()

        # Dosya Menüsü
        file_menu = menubar.addMenu("&Dosya")
        open_action = QAction("Örnek Model Yükle", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._load_sample_model)
        file_menu.addAction(open_action)

        file_menu.addSeparator()
        exit_action = QAction("Çıkış", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Görünüm Menüsü
        view_menu = menubar.addMenu("&Görünüm")
        reset_action = QAction("Kamerayı Sıfırla", self)
        reset_action.setShortcut("R")
        reset_action.triggered.connect(self._engine.reset_camera)
        view_menu.addAction(reset_action)

        focus_action = QAction("Modeli Ortala", self)
        focus_action.setShortcut("F")
        focus_action.triggered.connect(self._engine.focus_model)
        view_menu.addAction(focus_action)

        view_menu.addSeparator()
        proj_action = QAction("Projeksiyon Değiştir (Persp/Ortho)", self)
        proj_action.setShortcut("P")
        proj_action.triggered.connect(self._engine.toggle_projection)
        view_menu.addAction(proj_action)

        render_action = QAction("Render Modu Değiştir (Wire/Shaded)", self)
        render_action.setShortcut("W")
        render_action.triggered.connect(self._engine.toggle_render_mode)
        view_menu.addAction(render_action)

        # Mod Menüsü
        mode_menu = menubar.addMenu("&Mod")
        modes = [
            ("Seçim", InteractionMode.SELECT),
            ("Nokta Ekle", InteractionMode.DRAW_NODE),
            ("Kiriş Ekle", InteractionMode.DRAW_BEAM),
            ("Alan Ekle", InteractionMode.DRAW_AREA),
            ("Ölçüm", InteractionMode.MEASURE),
            ("Sil", InteractionMode.DELETE),
        ]
        for label, mode in modes:
            action = QAction(label, self)
            action.triggered.connect(lambda checked, m=mode: self._engine.set_mode(m))
            mode_menu.addAction(action)

    def _setup_toolbar(self):
        toolbar = QToolBar("Araç Çubuğu")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(28, 28))
        self.addToolBar(toolbar)

        reset_btn = self._create_tool_button("🔄", "Kamerayı Sıfırla (R)")
        reset_btn.clicked.connect(self._engine.reset_camera)
        toolbar.addWidget(reset_btn)

        focus_btn = self._create_tool_button("🎯", "Modeli Ortala (F)")
        focus_btn.clicked.connect(self._engine.focus_model)
        toolbar.addWidget(focus_btn)

        toolbar.addSeparator()

        mode_actions = [
            ("🔍", InteractionMode.SELECT, "Seç"),
            ("📍", InteractionMode.DRAW_NODE, "Nokta Ekle"),
            ("📏", InteractionMode.DRAW_BEAM, "Kiriş Ekle"),
            ("🔲", InteractionMode.DRAW_AREA, "Alan Ekle"),
            ("📐", InteractionMode.MEASURE, "Ölçüm"),
            ("🗑️", InteractionMode.DELETE, "Sil"),
        ]

        self._mode_buttons = {}
        for icon, mode, tip in mode_actions:
            btn = self._create_tool_button(icon, tip)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, m=mode: self._engine.set_mode(m))
            self._mode_buttons[mode] = btn
            toolbar.addWidget(btn)

        toolbar.addSeparator()

        render_btn = self._create_tool_button("🎨", "Render Modu Değiştir (W)")
        render_btn.clicked.connect(self._engine.toggle_render_mode)
        toolbar.addWidget(render_btn)

    def _create_tool_button(self, icon: str, tooltip: str) -> QPushButton:
        btn = QPushButton(icon)
        btn.setToolTip(tooltip)
        btn.setFixedSize(32, 32)
        btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                border: none;
                border-radius: 4px;
                background: transparent;
            }
            QPushButton:hover {
                background: #3a3f4a;
                color: #ffffff;
            }
            QPushButton:checked {
                background: #4a7fbf;
                color: #ffffff;
                border: 1px solid #6ba4e8;
            }
        """)
        return btn

    # ==================== Sinyal İşleyicileri ====================

    def _on_selection_changed(self, elements: List[Any]):
        if elements:
            self._status_bar.showMessage(f"{len(elements)} eleman seçildi", 3000)
        else:
            self._status_bar.showMessage("Seçim temizlendi", 2000)

    def _on_mode_changed(self, mode: str):
        for m, btn in self._mode_buttons.items():
            btn.setChecked(m == mode)
        self._status_bar.showMessage(f"Mod: {mode}", 2000)

    # ==================== Aksiyonlar ====================

    def _load_sample_model(self):
        """Örnek 3D model yükle"""
        scene = self._create_sample_scene()
        self._engine.set_scene(scene)
        self._engine.focus_model()
        self._status_bar.showMessage("Örnek model yüklendi", 3000)

    def _create_sample_scene(self) -> Scene:
        """Örnek scene oluştur"""
        builder = SceneBuilder()

        # Malzeme
        mat = builder.create_material("S355", MatType.STEEL, E=210000000, density=7850)
        
        # Kesit
        builder.create_section(
            name="HE200A",
            profile_type=SectionType.I,
            profile_params={"h": 0.19, "b": 0.20, "tw": 0.0065, "tf": 0.010},
            material=mat
        )

        # Düğümler
        coords = [
            (-6.0, 0.0, -4.0), (0.0, 0.0, -4.0), (6.0, 0.0, -4.0),
            (-6.0, 0.0, 4.0), (0.0, 0.0, 4.0), (6.0, 0.0, 4.0),
            (-6.0, 5.0, -4.0), (0.0, 5.0, -4.0), (6.0, 5.0, -4.0),
            (-6.0, 5.0, 4.0), (0.0, 5.0, 4.0), (6.0, 5.0, 4.0),
            (0.0, 7.5, -4.0), (0.0, 7.5, 4.0)
        ]

        nodes = [builder.create_node(x, y, z, f"N_{i+1}") for i, (x, y, z) in enumerate(coords)]

        # Çerçeve elemanları
        lines = [
            (0, 6), (1, 7), (2, 8), (3, 9), (4, 10), (5, 11),
            (6, 12), (12, 8), (9, 13), (13, 11),
            (6, 7), (7, 8), (9, 10), (10, 11),
            (6, 9), (7, 10), (8, 11), (12, 13)
        ]

        for i, j in lines:
            builder.create_frame(nodes[i], nodes[j], section_name="HE200A")

        return builder.scene

    # ==================== Public API ====================

    def set_scene(self, scene: Scene):
        """Scene'i ayarla"""
        self._engine.set_scene(scene)

    def get_engine(self) -> RenderEngineWidget:
        """Engine widget'ını döndür"""
        return self._engine

    def get_scene(self) -> Optional[Scene]:
        """Mevcut scene'i döndür"""
        return self._engine.get_scene()

    # ==================== Kapatma ====================

    def closeEvent(self, event):
        self._engine.cleanup()
        logger.info("DrawingWindow kapatıldı.")
        event.accept()


# ==================== Test / Bağımsız Çalıştırma ====================

def main():
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = DrawingWindow()
    window.show()

    # Model yükle
    window._load_sample_model()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
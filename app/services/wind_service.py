# app/services/wind_service.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.cad_app import CadApp


class WindService:
    """WindManager'a ince sarmalayıcı — UIHost doğrudan erişmesin."""

    def __init__(self, app: "CadApp"):
        self.app = app
        self.manager = None  # CadApp tarafından atanır

    def attach(self, manager) -> None:
        self.manager = manager

    def state(self) -> dict:
        return self.manager.wind_state() if self.manager else {}

    def run(self) -> None:
        if self.manager:
            self.manager.run_wind()

    def select_direction(self, w_dir) -> None:
        if self.manager:
            self.manager.select_wind_direction(w_dir)
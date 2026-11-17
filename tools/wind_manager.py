# tools/wind_manager.py
from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING
import numpy as np

from domain.definition import WindDirectionResult
from tools.wind_scene_adapter import WindSceneAdapter

if TYPE_CHECKING:
    from app.cad_app import CadApp


class WindManager:
    def __init__(self, app: CadApp):
        self.app = app
        self._wind_queue: queue.Queue = queue.Queue()
        self._wind_generation = 0
        self._wind_status = ""

    def wind_state(self) -> dict:
        analysis = self.app.current_project.analysis
        wind = analysis.wind
        if not isinstance(wind, dict):
            wind = {}
            analysis.wind = wind
        directions = wind.get("directions")
        if not isinstance(directions, dict):
            directions = {}
            wind["directions"] = directions
        if not directions:
            directions["01"] = WindDirectionResult(w_dir=(1.0, 0.0, 0.0))
        if wind.get("active_direction") is None:
            first = next(iter(directions.values()))
            if isinstance(first, dict):
                wind["active_direction"] = tuple(first.get("w_dir", (1.0, 0.0, 0.0)))
            else:
                wind["active_direction"] = tuple(getattr(first, "w_dir", (1.0, 0.0, 0.0)))
        return wind

    def run_wind(self) -> None:
        wind = self.wind_state()
        active = wind.get("active_direction")
        if active is None:
            active = next(iter(wind["directions"].values())).w_dir
        direction = tuple(float(v) for v in active)
        key = self._wind_key(direction)
        self._start_wind_analysis(key, direction)

    def select_wind_direction(self, w_dir) -> None:
        direction = tuple(float(v) for v in w_dir)
        if len(direction) != 3 or not np.isfinite(direction).all():
            self._wind_status = "Geçersiz rüzgar yönü."
            return
        if np.linalg.norm(direction[:2]) < 1e-12:
            self._wind_status = "Geçersiz rüzgar yönü."
            return
        wind = self.wind_state()
        wind["active_direction"] = direction
        key = self._wind_key(direction)
        record = wind["directions"][key]
        if hasattr(record, "w_dir"):
            record.w_dir = direction
        elif isinstance(record, dict):
            record["w_dir"] = direction
        self._start_wind_analysis(key, direction)

    def _wind_key(self, w_dir) -> str:
        directions = self.wind_state()["directions"]
        for key, record in directions.items():
            candidate = getattr(record, "w_dir", None)
            if candidate is None and isinstance(record, dict):
                candidate = record.get("w_dir")
            if candidate is not None and np.allclose(candidate, w_dir, atol=1e-8):
                return str(key)
        numeric = [int(k) for k in directions if str(k).isdigit()]
        key = f"{max(numeric, default=0) + 1:02d}"
        directions[key] = WindDirectionResult(w_dir=tuple(w_dir))
        return key

    def _start_wind_analysis(self, direction_key: str, direction) -> None:
        project = self.app.current_project
        eng = self.app.engine
        scene = eng.math_model if eng else project.math_model
        if scene is None:
            return
        points, polygons, wind_config = WindSceneAdapter.build_inputs(project)
        self._wind_generation += 1
        generation = self._wind_generation
        self._wind_status = "Rüzgar analizi çalışıyor..."

        def analyze() -> None:
            zones, engine_data = WindSceneAdapter.analyze(
                points, polygons, wind_config, direction,
            )
            self._wind_queue.put(("done", generation, project, scene, direction_key,
                                  direction, zones, engine_data))

        threading.Thread(target=analyze, daemon=True).start()

    def process_queue(self) -> None:
        while True:
            try:
                message = self._wind_queue.get_nowait()
            except queue.Empty:
                return
            status, generation, project, scene, key, direction, *payload = message
            if generation != self._wind_generation:
                continue
            if project is not self.app.current_project:
                continue
            eng = self.app.engine
            if eng and eng.math_model is not scene:
                continue
            if status == "error":
                self._wind_status = f"Rüzgar analizi başarısız: {payload[0]}"
                continue
            zones, engine_data = payload
            wind = self.wind_state()
            record = wind["directions"].get(key)
            if record is None:
                record = WindDirectionResult(w_dir=direction)
                wind["directions"][key] = record
            if isinstance(record, dict):
                record = WindDirectionResult(**record)
                wind["directions"][key] = record
            record.w_dir = direction
            WindSceneAdapter.update_direction_result(record, zones, engine_data)
            WindSceneAdapter.store_zones(project, key, zones, engine_data, direction)
            if eng is not None:
                eng.update_geo(project)
            self._wind_status = f"{len(zones)} rüzgar bölgesi hesaplandı."
            if self.app.ui:
                self.app.ui.on_wind_analysis_done(key)
# render/scenerenderer.py
from __future__ import annotations

from pyglm import glm

from render.presentation_renderer import PresentationRenderer


class SceneRenderer:

    def __init__(
        self, standard_shader, axes_shader, overlay_shader, simple_shader,
        grid_shader, math_model_renderer=None,
    ):
        self.math_model_renderer = math_model_renderer
        self.presentation_renderer = PresentationRenderer(
            standard_shader, axes_shader, overlay_shader, simple_shader,
            grid_shader, math_model_renderer,
        )
        self.engine = None

    def __getattr__(self, name):
        presentation = self.__dict__.get("presentation_renderer")
        if presentation is not None and hasattr(presentation, name):
            return getattr(presentation, name)
        model = self.__dict__.get("math_model_renderer")
        if model is not None:
            return getattr(model, name)
        raise AttributeError(name)

    @property
    def pick_pass(self):
        return self.math_model_renderer.pick_pass if self.math_model_renderer else None

    def set_engine(self, engine):
        self.engine = engine
        self.presentation_renderer.set_engine(engine)
        if self.math_model_renderer:
            self.math_model_renderer.set_engine(engine)

    def set_cam(self, camera):
        if self.math_model_renderer:
            self.math_model_renderer.set_cam(camera)

    def set_snap(self, snap):
        if self.math_model_renderer:
            self.math_model_renderer.set_snap(snap)

    def resize(self, width, height):
        if self.math_model_renderer:
            self.math_model_renderer.resize(width, height)

    def update_geo(
        self, math_model, scene=None, progress_cb=None, polygons=None,
        lines=None, grid_axes=None, frames=None, nodes=None, areas=None,
        links=None,
    ):
        self.presentation_renderer.math_model = math_model
        if self.math_model_renderer:
            self.math_model_renderer.update_geo(
                math_model, progress_cb,
                frames=frames, nodes=nodes, areas=areas, links=links,
                polygons=polygons, lines=lines,
            )
        if scene is not None:
            self.presentation_renderer.set_scene_data(
                scene, polygons=polygons, lines=lines, grid_axes=grid_axes,
            )

    def set_scene_data(self, scene, polygons=None, lines=None, grid_axes=None):
        if self.math_model_renderer:
            model = self.presentation_renderer.math_model
            self.math_model_renderer.update_polygons(
                polygons if polygons is not None else (
                    model.polygons.values() if model else ()
                )
            )
            self.math_model_renderer.update_lines(
                lines if lines is not None else (
                    model.lines.values() if model else ()
                )
            )
        self.presentation_renderer.set_scene_data(
            scene, polygons=polygons, lines=lines, grid_axes=grid_axes,
        )

    def render(self, camera, target_fbo=0, force_id_pass=False,
               viewport_name=None, plane=None, visible_ids=None):
        if not self.engine:
            if self.math_model_renderer:
                self.math_model_renderer.render(
                    camera, target_fbo, force_id_pass=force_id_pass, plane=plane,
                )
            return

        engine = self.engine
        if engine.show.get("presentation_any", True) and engine.scene is not None:
            model = (
                self.math_model_renderer.model_mat
                if self.math_model_renderer else glm.mat4(1.0)
            )
            self.presentation_renderer.render_scene_visuals(
                camera, model,
                engine.scene, engine.math_model, engine.w, engine.h,
                engine.show, engine.active_wind_vector,
            )

        if not self.math_model_renderer:
            return
        base = self.math_model_renderer
        base.show["polygon"] = (
            engine.show.get("polygon", True)
            and self.presentation_renderer.show.get("polygon", True)
        )
        base.show["lines"] = (
            engine.show.get("lines", True)
            and self.presentation_renderer.show.get("lines", True)
        )
        if engine.show.get("scene", True):
            base.render(camera, target_fbo, force_id_pass=force_id_pass,
                        plane=plane, visible_ids=visible_ids)

    def render_scene_visuals(self, *args, **kwargs):
        return self.presentation_renderer.render_scene_visuals(*args, **kwargs)

    def render_math_model(self, camera, target_fbo=0):
        return self.render(camera, target_fbo)

    def update_sel(self):
        if self.math_model_renderer:
            self.math_model_renderer.update_sel()

    def update_dirty(self):
        if self.math_model_renderer:
            self.math_model_renderer.update_dirty()

    def remove_viewport(self, viewport_name):
        pass

    def cleanup(self):
        self.presentation_renderer.cleanup()
        if self.math_model_renderer:
            self.math_model_renderer.cleanup()
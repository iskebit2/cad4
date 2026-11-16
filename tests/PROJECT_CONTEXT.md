# tests - Project Context

Generated: 2026-11-14T20:11:33

## Project Overview

- Name: tests
- Python files: 9

## Architecture Notes

- CAD4 is a structural engineering CAD application.
- The project uses Python and OpenGL.

## Module Structure

### `input_smoke_test`

Path: `input_smoke_test.py`

InputManager + bindings + handler dispatch'in doğruluğunu GLFW penceresi olmadan test eder.
Kullanım:
    python -m tools.input_smoke_test

#### Classes

- **MockHandler** (line 11)
  - `__init__(self, name, active=True, swallow=True)`
  - `handle_click(self, x, y, button)`
  - `handle_release(self, x, y, button)`
  - `handle_move(self, x, y, dx, dy)`
  - `handle_key(self, key, mods)`
  - `handle_scroll(self, delta)`

#### Module Functions

- `_test_dispatch_order()`
- `_test_dispatch_skip_inactive()`
- `_test_double_click()`
- `_test_binding()`
- `_test_fallback()`
- `_test_state()`
- `_test_modifiers()`
- `main()`

### `project_mapper`

Path: `project_mapper.py`

#### Module Functions

- `relative_path(path: Path -> str)`
- `module_name(path: Path -> str)`
  - Dosya yolundan Python modül adını üretir.
- `get_docstring(node -> str | None)`
- `get_signature(node -> str)`
  - Fonksiyon/metot imzasını üretir.
- `get_base_names(node -> list[str])`
- `read_python_file(path: Path)`
- `scan_project()`
  - Projedeki Python dosyalarını tarar.
- `analyze_file(path: Path)`
- `resolve_imports(modules)`
  - Import kayıtlarını yerel ve harici bağımlılıklar
- `build_tree(modules)`
- `save_json(path: Path, data)`
- `build_context(modules, dependency_data)`
- `main()`

### `test1`

Path: `test1.py`

#### Module Functions

- `make_polygon(scene, node_ids, label)`
  - Node ID listesinden polygon üret.
- `main()`

### `test_0`

Path: `test_0.py`

### `test_createagac`

Path: `test_createagac.py`

#### Module Functions

- `get_classes_in_file(file_path)`
  - Dosyadaki sınıfları ve docstring'lerini bulur.
- `print_tree(root_path, prefix='')`

### `test_math_model_geometry_ownership`

Path: `test_math_model_geometry_ownership.py`

#### Module Functions

- `_project_with_six_elements()`
- `test_six_geometry_types_share_math_model_ownership_and_bounds()`
- `test_geometry_processor_prepares_polygon_and_line_from_math_model()`
- `test_serializer_stores_geometry_in_math_model_and_reads_legacy_scene_fields(tmp_path)`

### `test_registry`

Path: `test_registry.py`

### `test_section_render_cache`

Path: `test_section_render_cache.py`

#### Classes

- **_SectionRendererStub** (line 7)
  - `__init__(self, **kwargs)`
  - `set_engine(self, engine)`
  - `set_cam(self, camera)`
  - `set_lighting(self, lighting)`
  - `update_geo(self, model)`
  - `render(self, camera, target_fbo, force_id_pass=False)`

#### Module Functions

- `_scene_renderer_stub()`
- `test_section_renderer_is_reused_per_viewport_and_refreshed_on_plane_change(monkeypatch)`
- `test_section_viewport_renders_with_its_cached_renderer(monkeypatch)`

### `test_viewport_interaction`

Path: `test_viewport_interaction.py`

#### Module Functions

- `test_marquee_uses_viewport_dimensions()`
- `test_async_pick_reads_viewport_fbo_and_coordinates(monkeypatch)`
- `test_mrt_clear_targets_integer_id_attachment(monkeypatch)`
- `test_interaction_renderer_targets_matching_viewport_and_pointer()`

## Internal Dependencies


## Inheritance


## Important Notes

- This document is generated using Python AST.
- Import relationships are statically inferred.
- Dynamic imports and runtime relationships may not appear.
- Class ownership and architectural responsibilities require human documentation.
- Refer to the source code for authoritative implementation details.

# cad4 - Project Context

Generated: 2026-11-17T23:24:52

## Project Overview

- Name: cad4
- Python files: 246

## Architecture Notes

- CAD4 is a structural engineering CAD application.
- The project uses Python and OpenGL.

## Module Structure

### `app.cad_app`

Path: `app/cad_app.py`

#### Classes

- **CadApp** (line 27)
  - `__init__(self, window: CadWindow)`
  - `_load_section_catalog(self -> Dict[str, Section])`
  - `attach_ui(self, ui_host: 'UIHost' -> None)`
  - `ui(self -> 'UIHost | None')`
  - `tick(self, dt: float -> None)`
  - `_ensure_engine(self -> None)`
  - `shutdown(self -> None)`
  - `new_project(self -> None)`
  - `load_project(self, path: str -> None)`
  - `save_project(self, path: str -> None)`
  - `quick_save(self -> None)`
  - `set_project(self, project: Project -> None)`
  - `on_s2k_import_complete(self, project: Project -> None)`
  - `on_selection_changed(self, selected: list -> None)`
  - `on_hover_changed(self, element -> None)`
  - `get_selected(self -> list)`
  - `set_unit_system(self, unit_system: UnitSystem -> None)`
  - `wind_state(self -> dict)`
  - `run_wind(self -> None)`
  - `select_wind_direction(self, w_dir -> None)`
  - `on_plane_selected(self, plane -> None)`
  - `toggle_2d(self -> None)`
  - `get_loads_visible(self -> bool)`
  - `set_loads_visible(self, enabled: bool -> None)`
  - `show_entire_model(self -> None)`
  - `convert_frames_to_links(self, link_prop_name='DefaultLink', delete_original=True -> None)`
  - `_active_working_plane(self)`
  - `_update_scene_if_dirty(self -> None)`
  - `_drain_commands(self -> None)`

### `app.cad_window`

Path: `app/cad_window.py`

#### Classes

- **CadWindow** (line 18)
  - `__init__(self, width: int=1200, height: int=800, title: str='CAD4')`
  - `create(self -> None)`
  - `_init_glfw(self -> None)`
  - `_init_imgui(self -> None)`
  - `_wire_callbacks(self -> None)`
  - `_cb_resize(self, win, w: int, h: int -> None)`
  - `_cb_key(self, win, key: int, scancode: int, action: int, mods: int -> None)`
  - `_cb_mouse_button(self, win, button: int, action: int, mods: int -> None)`
  - `_cb_mouse_move(self, win, x: float, y: float -> None)`
  - `_cb_scroll(self, win, xoff: float, yoff: float -> None)`
  - `_cb_char(self, win, codepoint: int -> None)`
  - `_cb_focus(self, win, focused: bool -> None)`
  - `run(self, frame_callback: Callable[[float], None], target_fps: int=60 -> None)`
  - `get_mouse_pos(self -> tuple[float, float])`
  - `is_key_pressed(self, key: int -> bool)`
  - `should_close(self -> bool)`
  - `shutdown(self -> None)`

### `app.commands.camera`

Path: `app/commands/camera.py`

#### Module Functions

- `register(reg)`
- `_toggle_render_mode(app, cmd: PC.ToggleRenderMode -> CommandResult)`
- `_fit(app, cmd: PC.FitView -> CommandResult)`
- `_zoom(app, cmd: PC.ZoomExtents -> CommandResult)`
- `_preset(app, cmd: PC.SetCameraPreset -> CommandResult)`

### `app.commands.definitions`

Path: `app/commands/definitions.py`

#### Module Functions

- `register(reg)`
- `_add(app, cmd: PC.AddDefinition -> CommandResult)`
- `_update(app, cmd: PC.UpdateDefinition -> CommandResult)`
- `_remove(app, cmd: PC.RemoveDefinition -> CommandResult)`
- `_rename(app, cmd: PC.RenameDefinition -> CommandResult)`

### `app.commands.elements`

Path: `app/commands/elements.py`

#### Module Functions

- `register(reg)`
- `_delete_selected(app, cmd: PC.DeleteSelected -> CommandResult)`
- `_update_fields(app, cmd: PC.UpdateElementFields -> CommandResult)`
- `_delete(app, cmd: PC.DeleteElements -> CommandResult)`
- `_add_node(app, cmd: PC.AddNode -> CommandResult)`
- `_add_frame(app, cmd: PC.AddFrame -> CommandResult)`

### `app.commands.engine_flags`

Path: `app/commands/engine_flags.py`

#### Module Functions

- `register(reg)`
- `_hover(app, cmd: PC.HoverChanged -> CommandResult)`
- `_start_draw(app, cmd: PC.StartDrawTool -> CommandResult)`
- `_start_plane(app, cmd: PC.StartPlaneTool -> CommandResult)`
- `_undo(app, cmd: PC.Undo -> CommandResult)`
- `_redo(app, cmd: PC.Redo -> CommandResult)`
- `_toggle_2d(app, cmd: PC.Toggle2D -> CommandResult)`
- `_loads(app, cmd: PC.ToggleLoadsVisible -> CommandResult)`
- `_local_axes(app, cmd: PC.ToggleLocalAxes -> CommandResult)`
- `_render_flag(app, cmd: PC.ToggleRenderFlag -> CommandResult)`
- `_render_mode(app, cmd: PC.SetRenderMode -> CommandResult)`

### `app.commands.project`

Path: `app/commands/project.py`

#### Module Functions

- `register(reg)`
- `_replace(app, cmd: PC.ReplaceProject -> CommandResult)`
- `_set_unit(app, cmd: PC.SetUnitSystem -> CommandResult)`

### `app.commands.registry`

Path: `app/commands/registry.py`

#### Classes

- **CommandRegistry** (line 14)
  - `__init__(self -> None)`
  - `register(self, cmd_type: type, handler: CommandHandler -> None)`
  - `dispatch(self, app: 'CadApp', cmd: Command -> CommandResult)`

#### Module Functions

- `build_registry( -> CommandRegistry)`

### `app.commands.result`

Path: `app/commands/result.py`

#### Classes

- **CommandResult** (line 7)
  - Komut uygulama sonucu.

### `app.commands.selection`

Path: `app/commands/selection.py`

#### Module Functions

- `register(reg)`
- `_clear(app, cmd: PC.ClearSelection -> CommandResult)`
- `_select(app, cmd: PC.SelectElements -> CommandResult)`

### `app.commands.signals`

Path: `app/commands/signals.py`

#### Module Functions

- `register(reg)`
- `_refresh(app, cmd: PC.RefreshGeometry -> CommandResult)`

### `app.commands.visibility`

Path: `app/commands/visibility.py`

#### Module Functions

- `register(reg)`
- `_show_only(app, cmd: PC.ShowOnly -> CommandResult)`
- `_hide(app, cmd: PC.HideElements -> CommandResult)`
- `_show_all(app, cmd: PC.ShowEntireModel -> CommandResult)`

### `app.input_bindings`

Path: `app/input_bindings.py`

#### Module Functions

- `build_bindings(command_queue -> dict)`

### `core.analysis`

Path: `core/analysis/__init__.py`

### `core.analysis.mass_assembly`

Path: `core/analysis/mass_assembly.py`

#### Classes

- **MassContribution** (line 26)
- **MassAssembly** (line 35)
  - `total_kg(self -> float)`
  - `total_ton(self -> float)`

#### Module Functions

- `_is_vertical_load_set(load -> bool)`
- `_pattern_kind(design_type: str -> str)`
- `_node_key_map(scene -> dict[object, str])`
- `_polygon_area_3d(nodes -> float)`
- `_load_segment_value(seg, key: str, default=0.0 -> float)`
- `_distributed_load_mass_kg(load, frame_length: float -> float)`
- `local_consistent_mass(A: float, L: float, rho: float, J: float, I33: float, I22: float -> np.ndarray)`
  - 3D Çubuk 12x12 Lokal Tutarlı (Consistent) Kütle Matrisi.
- `triangle_consistent_mass_3d(nodes: list, thickness: float, material -> np.ndarray)`
  - 3 düğümlü 3D kabuk elemanı 18x18 Consistent Kütle Matrisi.
- `_node_translation_dofs(node, num_dofs: int)`
  - Düğümün UX/UY/UZ global DOF endekslerini döndürür (None'ları atar).
- `_lump_to_node(M: np.ndarray, node, mass_kg: float, num_dofs: int -> None)`
  - Lumped kütleyi düğümün UX/UY/UZ köşegenlerine eşit yazar.
- `build_mass(scene, project, n_live: float=0.3, *, validate: bool=True -> MassAssembly)`
  - Kütle matrisi montajı.

### `core.analysis.material_takeoff`

Path: `core/analysis/material_takeoff.py`

Malzeme metrajı — ElementWeight ve özet tablolar.

Birim sözleşmesi: units.py (kg, mm, N, MPa, kg/mm³).

#### Classes

- **ElementWeight** (line 21)
  - `mass_ton(self -> float)`
  - `weight_kN(self -> float)`
- **MaterialSummary** (line 45)
- **TakeoffResult** (line 55)
  - `total_mass_kg(self -> float)`
  - `total_mass_ton(self -> float)`
  - `total_weight_kN(self -> float)`

#### Module Functions

- `_polygon_area_3d(points -> float)`
  - Newell — mm².
- `_frame_weight(frame: Frame -> ElementWeight | None)`
- `_area_weight(area: Area -> ElementWeight | None)`
- `compute_takeoff(scene: MathModel -> TakeoffResult)`
- `takeoff_to_dataframes(result: TakeoffResult)`

### `core.analysis.modal_analysis`

Path: `core/analysis/modal_analysis.py`

#### Classes

- **SpectralModeResult** (line 16)
  - `__inspector_tree__(self)`
- **SpectralResult** (line 52)
  - `__inspector_tree__(self)`

#### Module Functions

- `_direction_vector(modal_dofs, direction)`
- `response_spectrum_solve(modal: ModalResult, M_global, num_dofs, spectrum, n_modes=None)`

### `core.analysis.run`

Path: `core/analysis/run.py`

Yüksek seviye analiz servisi — UI'nin tek giriş noktası.

    from core.analysis.run import AnalysisService
    result = AnalysisService.run(scene, project, options)

#### Classes

- **AnalysisOptions** (line 18)
- **AnalysisBundle** (line 29)
  - `ok(self -> bool)`
- **AnalysisService** (line 41)
  - `run(scene, project, options: AnalysisOptions -> AnalysisBundle)`

### `core.analysis.solver`

Path: `core/analysis/solver.py`

#### Classes

- **ModalResult** (line 19)
  - `__len__(self -> int)`
  - `n_modes(self -> int)`
- **StructuralSolver** (line 81)
  - `__init__(self, K_global: np.ndarray, M_global: np.ndarray, fixed_dofs, num_dofs: int)`
  - `_guyan_reduced(self)`
  - `_reduced(self -> tuple[np.ndarray, np.ndarray])`
  - `static_solve(self, F: np.ndarray -> np.ndarray)`
  - `modal_solve(self, n_modes: int=10, debug: bool=True, use_condensation: bool=True -> ModalResult)`
  - `_build_effective_mass(self, M: np.ndarray -> np.ndarray)`
  - `_participation_condensed(self, vectors_a: np.ndarray, M_cond: np.ndarray, trans_idx: np.ndarray, rot_idx: np.ndarray, G: np.ndarray | None, modal_dofs: np.ndarray -> tuple[np.ndarray, np.ndarray, np.ndarray])`
  - `_total_masses_condensed(self, M_cond: np.ndarray, trans_idx: np.ndarray, rot_idx: np.ndarray, G: np.ndarray | None, modal_dofs: np.ndarray -> tuple[float, float, float])`
  - `_participation(self, mode_shapes: np.ndarray, M_red: np.ndarray, modal_dofs: np.ndarray -> tuple[np.ndarray, np.ndarray, np.ndarray])`
  - `_total_masses(M_red: np.ndarray, modal_dofs: np.ndarray -> tuple[float, float, float])`
  - `_direction_vectors(self, modal_dofs: np.ndarray -> np.ndarray)`

#### Module Functions

- `perform_guyan_condensation(K, M, master_indices, slave_indices)`

### `core.analysis.spectrum`

Path: `core/analysis/spectrum.py`

TBDY 2018 spektrum ve spektral analiz.

#### Classes

- **TBDYSpectrum** (line 8)
  - TBDY 2018 yatay elastik tasarım spektrumu.
  - `__init__(self, Ss, S1, Fs, F1, R, D, I, TL=6.0)`
  - `get_sa(self, T: float -> float)`
    - Alias for S_ra — modal_analysis uyumu için.
  - `S_ae(self, T)`
    - Yatay elastik spektral ivme (g).
  - `R_a(self, T)`
    - Deprem yükü azaltma katsayısı.
  - `S_ra(self, T)`
    - Azaltılmış tasarım spektral ivmesi (g).
  - `info(self)`

#### Module Functions

- `read_spectrum_from_parser(parser)`
  - S2K tablolarından spektrum parametrelerini oku.

### `core.analysis.stiffness_assembly`

Path: `core/analysis/stiffness_assembly.py`

Rijitlik Matrisi Toplama — TEK Çıkış: StiffnessAssembly (Frame Timoshenko + Area 3D Shell Simetrik)

Birim Sözleşmesi (units.py):
    E   [MPa = N/mm²]
    G   [MPa = N/mm²]
    A   [mm²]
    AS2 [mm²] (Kesme alanı - y yönü)
    AS3 [mm²] (Kesme alanı - z yönü)
    I   [mm⁴]
    L   [mm]
    → K [N/mm] (öteleme), [N·mm/rad] (rotasyon)

#### Classes

- **StiffnessAssembly** (line 24)

#### Module Functions

- `local_stiffness(E: float, G: float, A: float, J: float, I33: float, I22: float, AS2: float, AS3: float, L: float, release_i: dict[str, bool] | None=None, release_j: dict[str, bool] | None=None, use_shear_deform: bool=True -> np.ndarray)`
  - 3D Çubuk 12x12 Lokal Rijitlik Matrisi (Timoshenko Kesme Deformasyonu Destekli).
- `transformation_matrix(p1, p2, beta_deg=0.0, up_global=(0.0, 0.0, 1.0))`
- `triangle_shell_stiffness_3d(nodes: list, thickness: float, material -> np.ndarray)`
- `ensure_dof_indices(scene -> None)`
- `build_stiffness(scene, project, *, validate: bool=True, use_shear_deform: bool=False -> StiffnessAssembly)`
- `_assemble_frame(frame, K: np.ndarray, num_dofs: int, use_shear_deform: bool=True -> str | None)`
- `_assemble_area(area, K: np.ndarray, num_dofs: int -> str | None)`

### `core.analysis.structuralanalysis`

Path: `core/analysis/structuralanalysis.py`

Orchestration — mass + stiffness + modal (+ spectrum).

Birim sözleşmesi: units.py.

#### Classes

- **StructuralAnalysisResult** (line 18)
  - `K(self -> np.ndarray)`
  - `M(self -> np.ndarray)`
  - `__inspector_tree__(self)`

#### Module Functions

- `_collect_fixed_dofs(scene -> list[int])`
  - Mesnetli node'ların DOF endekslerini topla.
- `_validate_modal(modal: ModalResult, tol: float=1e-06 -> list[str])`
  - Modal sonuç doğrulaması.
- `run_analysis(scene, project, n_live: float=0.3, n_modes: int=10, spectrum=None, *, validate: bool=True, use_shear_deform: bool=True -> StructuralAnalysisResult)`
  - Tam analiz zinciri: mass → stiffness → modal (+ spectrum).
- `_resolve_spectrum(project, spectrum)`

### `core.analysis.unit_guard`

Path: `core/analysis/unit_guard.py`

#### Module Functions

- `ensure_nmm(project -> None)`
  - Solver öncesi project'i N_MM'ye çevir.

### `core.analysis.validation`

Path: `core/analysis/validation.py`

Analiz ara doğrulama.

Her aşama sonunda çağrılır. Hata listesi döndürür; exception fırlatmaz.
Tüm toleranslar ölçek-bağımsız (göreli) veya mutlak olarak açıkça belirtilmiştir.

#### Module Functions

- `_is_symmetric(A: np.ndarray, rtol: float -> tuple[bool, float])`
  - Simetri kontrolü. (bool, max_rel_asym) döndürür.
- `_offdiag_max(A: np.ndarray -> float)`
  - Köşegen dışı mutlak maksimum.
- `_translation_dof_indices(num_nodes: int, num_dofs: int -> np.ndarray)`
  - Her düğümün UX (offset 0) global DOF endekslerini döndürür.
- `_total_mass_consistent(M: np.ndarray -> float)`
  - Consistent mass korunum toplamı: Σ_ij M_ij.
- `validate_mass(asm, is_consistent: bool=False -> list[str])`
  - MassAssembly nesnesi üzerinde kütle ve matris doğrulama kontrolleri.
- `validate_stiffness(asm -> list[str])`
  - StiffnessAssembly doğrula.

### `core.camera`

Path: `core/camera.py`

#### Classes

- **Camera** (line 15)
  - Milimetre/Metre uyumlu, yapısal aks sistemleri için optimize edilmiş CAD Kamerası.
  - `__post_init__(self)`
  - `min_distance(self -> float)`
  - `max_distance(self -> float)`
  - `near(self -> float)`
  - `far(self -> float)`
  - `update_bounds(self, center, size)`
  - `focus_on_model(self)`
  - `reset(self)`
  - `set_top_view(self -> None)`
    - Üstten bakış — 2D görünüm için.
  - `orbit(self, dx, dy)`
  - `_is_2d_locked(self -> bool)`
    - 2D / plane görünümünde orbit engellenmeli mi?
  - `pan(self, dx, dy)`
  - `zoom(self, delta)`
  - `position(self -> glm.vec3)`
  - `_update_position(self)`
  - `_invalidate(self)`
  - `get_view_matrix(self)`
  - `get_projection_matrix(self)`
  - `get_mvp_matrix(self, model_matrix=None)`
  - `set_aspect(self, w, h)`
  - `toggle_projection(self)`
  - `set_view_preset(self, preset)`
  - `clear_view_preset(self)`
  - `set_section_filter(self, normal, origin, min_s, max_s)`
    - Aktif UCS'ye göre alt/üst aralık filtresi.
  - `clear_section_filter(self)`
  - `is_element_visible_by_section(self, coords)`
  - `look_at_plane(self, origin, u, v, n, fit_radius=None)`
  - `save_view(self -> None)`
    - Mevcut kamerayı kaydet (F2 3D→2D geçişinde).
  - `restore_view(self -> bool)`
    - Kaydedilmiş kamerayı geri yükle (F2 2D→3D geçişinde).
  - `set_level_filter(self, z_min: float, z_max: float -> None)`
    - Z aralığı filtresi — sadece z_min ≤ z ≤ z_max arasındaki elemanlar görünür.
  - `clear_level_filter(self -> None)`

### `core.camera_controller`

Path: `core/camera_controller.py`

#### Classes

- **CameraController** (line 7)
  - `__init__(self, engine)`
  - `_active_camera(self)`
  - `_active_viewport(self)`
  - `handle_click(self, x, y, button -> bool)`
  - `handle_release(self, x, y, button -> bool)`
  - `handle_move(self, x, y, dx, dy -> bool)`
  - `handle_key(self, key, mods -> bool)`
  - `handle_scroll(self, delta -> bool)`
  - `_pick_at_viewport(self, vp, x_px, y_px)`
  - `_on_escape(self)`

### `core.commands`

Path: `core/commands/__init__.py`

### `core.commands.base`

Path: `core/commands/base.py`

#### Classes

- **Command** (ABC) (line 10)
  - Tüm komutların arayüzü.
  - `execute(self)`
    - İşlemi uygula.
  - `undo(self)`
    - İşlemi geri al.
  - `redo(self)`
    - Yeniden uygula (varsayılan: execute).
  - `name(self -> str)`
    - Debug/log için okunabilir isim.
- **CommandManager** (line 31)
  - Komut geçmişi ve undo/redo yönetimi.
  - `__init__(self, max_history: int=100)`
  - `execute(self, command: Command -> bool)`
    - Komutu çalıştır ve geçmişe ekle.
  - `undo(self -> bool)`
    - Son komutu geri al.
  - `redo(self -> bool)`
    - Son geri alınanı yeniden uygula.
  - `can_undo(self -> bool)`
  - `can_redo(self -> bool)`
  - `clear(self)`
    - Tüm geçmişi temizle.
  - `add_listener(self, callback)`
    - Komut sonrası tetiklenecek callback ekle.
  - `_notify(self)`

### `core.commands.bulk_update`

Path: `core/commands/bulk_update.py`

BulkUpdateCommand — Birden fazla elemana aynı anda alan uygular.

- execute(): plan'daki tüm (element, after) çiftlerini uygular
- undo():    ters sırayla before değerlerini geri koyar
- Tek bir Command → CommandManager'da tek undo/redo kaydı

#### Classes

- **BulkUpdateCommand** (Command) (line 19)
  - plan: List[(element, before_dict, after_dict)]
  - `__init__(self, plan: list[tuple[Any, dict[str, Any], dict[str, Any]]], setter: Callable[[Any, str, Any], None])`
  - `execute(self)`
    - Tüm alanları sırayla uygula.
  - `undo(self)`
    - Ters sırayla eski değerleri geri koy.
  - `name(self -> str)`

### `core.commands.command_queue`

Path: `core/commands/command_queue.py`

UI thread → CadApp.tick arasında komut kuyruğu.

Thread-safe. UI Host kendi thread'inden put() yapar, CadApp ana thread'de
drain() yapar ve komutları uygular.

#### Classes

- **CommandQueue** (line 16)
  - `__init__(self -> None)`
  - `put(self, command: 'Command' -> None)`
  - `drain(self -> list['Command'])`

### `core.commands.create`

Path: `core/commands/create.py`

#### Classes

- **CreateElementCommand** (Command) (line 11)
  - Yeni bir eleman oluşturup scene'e ekler.
  - `__init__(self, scene, element_type: str, factory: Callable[[dict[str, Any]], Any], values: dict[str, Any])`
  - `execute(self)`
  - `undo(self)`
  - `name(self -> str)`

### `core.commands.delete`

Path: `core/commands/delete.py`

#### Classes

- **DeleteElementsCommand** (Command) (line 8)
  - Seçili elemanları sil. Node bağlı ise reddedilir.
  - `__init__(self, scene, elements: list)`
    - Parameters
  - `execute(self)`
    - Elemanları sil.
  - `undo(self)`
    - Silinenleri geri koy.
  - `name(self -> str)`

### `core.commands.project_commands`

Path: `core/commands/project_commands.py`

#### Classes

- **AddDefinition** (line 9)
- **UpdateDefinition** (line 16)
- **RemoveDefinition** (line 24)
- **RenameDefinition** (line 30)
- **UpdateElementFields** (line 38)
- **DeleteElements** (line 44)
- **AddNode** (line 49)
- **AddFrame** (line 58)
- **ReplaceProject** (line 68)
- **SetUnitSystem** (line 74)
- **FitView** (line 81)
- **ZoomExtents** (line 85)
- **SetCameraPreset** (line 89)
- **Toggle2D** (line 94)
- **ToggleLoadsVisible** (line 98)
- **ToggleLocalAxes** (line 103)
- **ClearSelection** (line 107)
- **SelectElements** (line 111)
- **RefreshGeometry** (line 117)
- **ShowOnly** (line 121)
- **HideElements** (line 126)
- **ShowEntireModel** (line 131)
- **ToggleRenderFlag** (line 134)
- **SetRenderMode** (line 139)
- **ToggleRenderMode** (line 143)
- **DeleteSelected** (line 148)
- **StartDrawTool** (line 153)
- **StartPlaneTool** (line 158)
- **Undo** (line 163)
- **Redo** (line 168)
- **HoverChanged** (line 172)

### `core.commands.update`

Path: `core/commands/update.py`

#### Classes

- **UpdateElementCommand** (Command) (line 11)
  - Bir elemanın alanlarını değiştirir.
  - `__init__(self, element, before: dict[str, Any], after: dict[str, Any], setter: Callable[[Any, str, Any], None])`
  - `execute(self)`
  - `undo(self)`
  - `name(self -> str)`

### `core.edit.edit_controller`

Path: `core/edit/edit_controller.py`

#### Classes

- **EditResult** (line 18)
- **EditController** (line 25)
  - Panel ↔ Scene köprüsü.
  - `__init__(self, engine, max_history: int=100)`
  - `scene(self)`
  - `create(self, element_type: str, values: dict[str, Any] -> EditResult)`
  - `update(self, element, new_values: dict[str, Any] -> EditResult)`
  - `delete(self, elements -> EditResult)`
  - `undo(self -> EditResult)`
  - `redo(self -> EditResult)`
  - `_factory_for(self, et: str)`
  - `_build_node(self, v)`
  - `_build_frame(self, v)`
  - `_build_link(self, v)`
  - `_build_area(self, v)`
  - `_build_polygon(self, v)`
  - `_read_field(self, element, field: str)`
  - `_apply_field(self, element, field: str, value)`
  - `_resolve_node(self, ref)`
    - ref: Node | unique_id (int) | label (str) | UUID (str)
  - `_resolve_section(self, name)`
  - `_is_same(self, a, b)`
  - `_refresh(self)`
  - `bulk_update(self, elements, changes -> EditResult)`
    - Birden fazla elemente aynı anda alan uygula.
  - `_read_field_safe(self, element, field)`
    - Bulk update için güvenli field okuma.

### `core.engine`

Path: `core/engine/__init__.py`

#### Classes

- **Engine** (line 25)
  - Render pipeline orkestratörü. App bilmez, UI bilmez.
  - `__init__(self, width: int, height: int, command_queue -> None)`
  - `init_gl(self -> None)`
  - `resize(self, w: int, h: int -> None)`
  - `update_geo(self, project: 'Project | None'=None -> None)`
  - `render_viewport(self, vp: 'Viewport' -> None)`
  - `tick(self -> None)`
  - `enter_plane_2d(self, plane -> None)`
  - `exit_plane_2d(self -> None)`
  - `fit_view(self -> None)`
  - `zoom_extents(self -> None)`
  - `default_xy_plane(self)`
  - `set_viewport_pointer(self, viewport, x: int, y: int -> None)`
  - `clear_hover(self -> None)`
  - `handle_pick_from_hover(self, ctrl: bool=False -> None)`
  - `start_hover_pick(self, x: int, y: int -> None)`
  - `start_viewport_hover_pick(self, viewport, x: int, y: int -> None)`
  - `check_pick_result(self -> bool)`
  - `_find_element(self, pick_id: int)`
  - `screen_ray(self, x: float, y: float)`
  - `screen_to_world(self, x: float, y: float)`
  - `update_world_pos(self, x: float, y: float -> None)`
  - `start_plane_from_element(self -> None)`
  - `cancel_plane_from_element(self -> None)`
  - `toggle_plane_from_element_axis(self -> None)`
  - `cleanup(self -> None)`
  - `cam(self)`
  - `renderer(self)`
  - `pick_pass(self)`
  - `mrt(self)`
  - `presentation_renderer(self)`
  - `interaction_renderer(self)`
  - `math_model_renderer(self)`
  - `grid(self)`
  - `scene(self)`
  - `math_model(self)`
  - `hover_id(self)`
  - `preview_s(self)`
  - `pick_s(self)`
  - `sel_mgr(self)`
  - `sel_policy(self)`
  - `draw_mgr(self)`
  - `plane_draw_mgr(self)`
  - `marquee(self)`
  - `edit(self)`
  - `snap(self)`
  - `pending_pick_check(self)`
  - `active_working_plane(self)`
  - `viewport_pointer(self)`
  - `_combined_bounds(self)`
  - `set_scene(self, project -> None)`

### `core.engine.camera_rig`

Path: `core/engine/camera_rig.py`

#### Classes

- **CameraRig** (line 13)
  - Kamera + view operasyonları. Engine/app bilmez.
  - `__init__(self, width: int, height: int -> None)`
  - `resize(self, width: int, height: int -> None)`
  - `fit_view(self, bounds: 'Bounds3D | None' -> None)`
  - `zoom_extents(self, bounds: 'Bounds3D | None' -> None)`
  - `enter_plane_2d(self, plane: 'Plane' -> None)`
  - `exit_plane_2d(self -> None)`

### `core.engine.gl_context`

Path: `core/engine/gl_context.py`

#### Classes

- **GLContext** (line 18)
  - GL init + shader yükleme. Engine/app bilmez.
  - `__init__(self, width: int, height: int, shader_dir: Path | None=None -> None)`
  - `init(self -> None)`
  - `_load_shaders(self -> None)`
  - `resize(self, width: int, height: int -> None)`
  - `get(self, name: str -> ShaderProgram | None)`

### `core.engine.hover_system`

Path: `core/engine/hover_system.py`

#### Classes

- **HoverSystem** (line 13)
  - `__init__(self, pick_pass, command_queue -> None)`
  - `set_pick_pass(self, pick_pass -> None)`
  - `invalidate(self -> None)`
  - `clear(self -> None)`
  - `set_pointer(self, viewport_name: str, x: int, y: int -> None)`
  - `start_pick(self, x: float, y: float, viewport: 'Viewport | None'=None -> None)`
  - `check_pick_result(self -> bool)`
  - `_update_hover(self, pick_id: int, force: bool=False -> None)`

### `core.engine.plane_mode`

Path: `core/engine/plane_mode.py`

#### Classes

- **PlaneMode** (line 15)
  - 2D/3D projeksiyon modu. Engine/app bilmez, komut üretir.
  - `__init__(self, camera_rig: 'CameraRig', pipeline: 'RendererPipeline', command_queue -> None)`
  - `enter_2d(self, plane: 'Plane' -> None)`
  - `exit_2d(self -> None)`
  - `toggle(self, project: 'Project | None' -> bool)`
    - 2D/3D arasında geç. Aktif plane seç ya da oluştur.
  - `_set_projection(self, mode: str -> None)`
  - `_resolve_plane(self, project: 'Project | None' -> 'Plane | None')`
  - `_default_xy_plane(project: 'Project' -> 'Plane | None')`

### `core.engine.ray_cast`

Path: `core/engine/ray_cast.py`

#### Module Functions

- `screen_ray(camera: 'Camera', x: float, y: float, width: int, height: int -> tuple[np.ndarray, np.ndarray] | None)`
- `screen_to_world(camera: 'Camera', x: float, y: float, width: int, height: int, working_plane: 'Plane | None'=None)`

### `core.engine.renderer_pipeline`

Path: `core/engine/renderer_pipeline.py`

#### Classes

- **RendererPipeline** (line 26)
  - MRT + SceneRenderer + pick_pass. Interaction Engine.render_viewport'ta.
  - `__init__(self, width: int, height: int, shaders: dict, snap_renderer -> None)`
  - `_build(self -> None)`
  - `resize(self, width: int, height: int -> None)`
  - `update_geo(self, project: 'Project | None' -> None)`
  - `render(self, vp: 'Viewport', camera_rig: 'CameraRig' -> None)`
    - Sadece scene render + blit. Interaction Engine'de çağrılır.
  - `get_element_by_id(self, pick_id: int)`
  - `in_section(self, element, camera, plane -> bool)`
  - `iter_render_elements(self)`
  - `math_model_renderer(self)`
  - `grid(self)`
  - `fit_view_bounds(self)`
  - `cleanup(self -> None)`

### `core.engine.tools_registry`

Path: `core/engine/tools_registry.py`

#### Classes

- **ToolsRegistry** (line 18)
  - Engine araçlarını DI ile kurar. Test'te fake fabrikalar geçirilebilir.
  - `__init__(self, engine: 'Engine' -> None)`
  - `build(self -> None)`
  - `tick(self -> None)`

### `core.id_manager`

Path: `core/id_manager.py`

#### Classes

- **IDManager** (line 5)
  - Tüm CAD sahne elemanları (Node, Frame, Area, Link, Polygon vb.) 
  - `__new__(cls)`
  - `generate_id(cls -> int)`
    - Yeni ve benzersiz bir global unique_id üretir.
  - `sync_counter(cls, loaded_id: int)`
    - Proje dosyası (S2K / JSON) yüklenirken, dışarıdan gelen ID'ye 
  - `reset(cls, start_value: int=1)`
    - Sayacı sıfırlar veya belirli bir değere ayarlar.

### `core.input_manager`

Path: `core/input_manager.py`

#### Classes

- **InputState** (line 20)
- **InputManager** (line 34)
  - `__init__(self)`
  - `set_global_escape(self, fn -> None)`
  - `set_capture_callbacks(self, mouse_fn, keyboard_fn -> None)`
  - `register(self, handler -> None)`
  - `set_fallback(self, handler -> None)`
  - `bind(self, key: int, mods: int, action -> None)`
  - `is_shift(self -> bool)`
  - `is_ctrl(self -> bool)`
  - `is_alt(self -> bool)`
  - `on_mouse_button(self, button: int, action: int, mods: int -> None)`
  - `on_mouse_move(self, x: float, y: float -> None)`
  - `on_key(self, key: int, action: int, mods: int -> None)`
  - `on_scroll(self, delta: float -> None)`
  - `_double_click(self, button: int, x: float, y: float -> bool)`
  - `set_context_pick_handler(self, handler: Callable | None)`
  - `dispatch_click(self, x, y, button)`
  - `dispatch_release(self, x: float, y: float, button: int -> bool)`
  - `dispatch_move(self, x: float, y: float, dx: float, dy: float -> bool)`
  - `dispatch_key(self, key: int, mods: int -> bool)`
  - `dispatch_scroll(self, delta: float -> bool)`
  - `dispatch_double_click(self, x: float, y: float, button: int -> bool)`

### `core.marquee_selector`

Path: `core/marquee_selector.py`

#### Classes

- **MarqueeSelector** (line 15)
  - `__init__(self, engine, selection_manager, selection_policy)`
  - `start_selection(self, x, y, camera=None, viewport_size=None, viewport_name=None)`
  - `update_selection(self, x, y)`
  - `end_selection(self, camera=None, viewport_size=None, mode=None)`
  - `cancel_selection(self)`
  - `get_box_coords(self)`
  - `_reset(self)`
  - `_is_drag_valid(self)`
  - `_get_rect(self, viewport_size=None)`
    - Mouse ve projection aynı Kivy widget koordinat sistemindedir.
  - `_get_elements(self, camera=None, viewport_size=None)`
  - `_is_element_visible(self, element -> bool)`
    - Element gerçekten görünür mü? (is_visible + render_filter)
  - `_project_line_in(self, line, x1, y1, x2, y2, mvp, win_w, win_h, cross)`
  - `_polygon_in(self, poly, x1, y1, x2, y2, mvp, win_w, win_h, cross)`
  - `_in_rect(self, element, minp, maxp, mvp, win_w, win_h, cross)`
  - `_node_in(self, node, x1, y1, x2, y2, mvp, win_w, win_h)`
  - `_line_in(self, ni, nj, x1, y1, x2, y2, mvp, win_w, win_h, cross)`
  - `_area_in(self, area, x1, y1, x2, y2, mvp, win_w, win_h, cross)`
  - `_project(self, x, y, z, mvp, win_w, win_h)`
  - `_line_rect(self, p1, p2, x1, y1, x2, y2)`
    - Line segment ile axis-aligned rectangle kesişim testi.
  - `handle_click(self, x, y, button -> bool)`
  - `handle_release(self, x, y, button -> bool)`
  - `handle_move(self, x, y, dx, dy -> bool)`
  - `handle_key(self, key, mods -> bool)`
  - `handle_scroll(self, delta -> bool)`
  - `_is_element_visible_and_in_plane(self, element -> bool)`

### `core.mrt`

Path: `core/mrt.py`

#### Classes

- **MRTFramebuffer** (line 9)
  - `__init__(self, w, h)`
  - `_create(self)`
  - `bind(self)`
  - `clear(self)`
  - `blit_to(self, target_fbo, target_w=None, target_h=None, copy_id=False, source_w=None, source_h=None)`
  - `_fbo_has_attachment(fbo, attachment)`
  - `resize(self, w, h)`
  - `cleanup(self)`

### `core.selection_manager`

Path: `core/selection_manager.py`

#### Classes

- **SelectionManager** (line 8)
  - `__init__(self, scene_renderer)`
  - `_update(self)`
  - `_update_geometry_renderers(self, scene)`
  - `_deselect_all(self)`
  - `select(self, element, additive=False)`
  - `select_multiple(self, elements: list, mode=SelectionMode.REPLACE)`
  - `select_only(self, element)`
  - `select_all(self)`
  - `invert_selection(self)`
  - `expand_to_nodes(self)`
    - Filtrelenen/seçilen frame, line, link, area ve polygon'ların köşe node'lerini seçime ekler.
  - `save_selection(self, name: str)`
    - Seçimi isimle kaydet
  - `load_selection(self, name: str)`
    - İsmi verilen kayıtlı seçimi geri yükle
  - `clear(self)`
  - `get_selected(self)`
  - `find_element_by_id(self, unique_id: int)`
  - `count(self)`
  - `is_selected(self, e)`
  - `delete_selected(self)`
  - `undo(self)`
  - `redo(self)`

### `core.selection_policy`

Path: `core/selection_policy.py`

#### Classes

- **SelectionMode** (Enum) (line 8)
- **SelectionPolicy** (line 13)
  - Seçim politikasını belirler - TEK KAYNAK
  - `__init__(self, input_manager)`
  - `get_mode(self -> SelectionMode)`
    - Mevcut modifier tuşlara göre seçim modunu belirle
  - `should_clear_on_empty_click(self -> bool)`
    - Boşluğa tıklandığında seçim temizlensin mi?
  - `get_marquee_mode(self -> SelectionMode)`
    - Marquee seçimi için mod (Shift = Toggle)

### `core.units`

Path: `core/units.py`

Birim sistemi — tek doğruluk kaynağı.

Model her zaman `project.unit_system`'de. `convert_project_units` ile dönüşür.
Builder `float` — birim bilmez. Render `render_scale` ile kanonik mm'ye çevirir.

Import stratejisi:
    S2K import sırasında DEĞER DEĞİŞTİRİLMEZ. `project.unit_system` S2K'nın
    CurrUnits'ine ayarlanır; dönüşüm gerektiğinde (solver öncesi, UI birim
    değişimi) `convert_project_units` ayrıca çağrılır.

#### Classes

- **Dimension** (Enum) (line 64)
- **UnitSystem** (Enum) (line 83)
  - `from_sap(cls, s: str | None -> UnitSystem)`
    - SAP2000 CurrUnits string → UnitSystem.
  - `_normalize_v10(raw: str -> str)`
    - v10 `Ton. m. C` → `Tonf, m, C`.
  - `force_unit(self -> str)`
  - `length_unit(self -> str)`
  - `temp_unit(self -> str)`
- **UnitChangeEvent** (line 231)
  - `__init__(self)`
  - `subscribe(self, fn: Callable)`
  - `emit(self, from_sys: UnitSystem, to_sys: UnitSystem, reason: str='')`

#### Module Functions

- `factor(dim: Dimension, from_sys: UnitSystem, to_sys: UnitSystem -> float)`
  - Boyut ve iki sistem için dönüşüm faktörü (F^a · L^b modeli).
- `convert_value(dim, value, from_sys, to_sys)`
- `_convert_grid_lines(project, from_sys, to_sys -> int)`
- `convert_project_units(project, target: UnitSystem, *, reason: str='' -> int)`
  - Proje ağacındaki tüm birimli alanları hedef sisteme çevir.
- `_collect_schema(cls -> dict[str, Dimension | None])`
  - MRO boyunca `__unit_schema__`'ları birleştir (alt sınıf kazanır).
- `_walk_convert(root: Any, from_sys: UnitSystem, to_sys: UnitSystem -> int)`
  - Ağacı derinlemesine gez, __unit_schema__ olan her nesneyi dönüştür.
- `_convert_field(obj, field_path: str, dim: Dimension | None, from_sys: UnitSystem, to_sys: UnitSystem -> int)`
  - obj.field_path (nested, a.b.c) alanını dönüştür.
- `validate_project_units(project, original_system: UnitSystem -> list[str])`
  - Roundtrip doğrulaması için stub.

### `data.enums`

Path: `data/enums.py`

#### Classes

- **ConstraintType** (Enum) (line 8)
  - `from_sap(cls, name: str -> 'ConstraintType | None')`
    - S2K tablo adından tip çıkar: 'CONSTRAINT DEFINITIONS - DIAPHRAGM' → DIAPHRAGM.
- **MatType** (IntEnum) (line 28)
  - `from_sap(cls, sap_value -> 'MatType')`
    - S2K'dan gelen 'Steel', 'Concrete', 2, '2' vb. normalize et.
  - `sap_label(self -> str)`
    - SAP'ın kullandığı etiket.
- **SectionType** (Enum) (line 94)
- **LinkPropType** (IntEnum) (line 108)
  - `from_sap(cls, sap_str: str -> 'LinkPropType')`
- **ElementType** (Enum) (line 140)
- **ObjType** (Enum) (line 147)
- **LoadPatternType** (Enum) (line 153)
- **LoadCaseType** (Enum) (line 163)
- **ComboType** (Enum) (line 169)
- **GridPlane** (IntEnum) (line 174)
- **SectionCutDefinedBy** (str, Enum) (line 179)
- **SectionCutResultType** (str, Enum) (line 185)
- **PropAreaType** (IntEnum) (line 254)
- **PropType** (IntEnum) (line 261)
- **SymType** (IntEnum) (line 297)
- **SpectrumSourceType** (Enum) (line 303)
- **LoadType** (Enum) (line 310)
- **LoadDirection** (Enum) (line 322)
- **DistType** (Enum) (line 370)
  - `from_input(cls, value)`
  - `is_one_way(self -> bool)`
  - `is_two_way(self -> bool)`
  - `span_direction(self -> str)`
- **PolygonType** (Enum) (line 403)

### `data.materials_catalog`

Path: `data/materials_catalog.py`

Malzeme kataloğu — mevcut mechanical.py verilerini MatType'a göre gruplar.
Panelin "Katalogdan Yükle" özelliği buradan beslenir.

#### Module Functions

- `catalog_names_for(mat_type: MatType)`
  - Verilen MatType için katalog isimleri listesi.
- `get_catalog_params(name: str, mat_type: MatType, thickness_mm: float=16.0 -> dict)`
  - Katalogdan parametreleri getir. MatType'a göre doğru sözlüğe bakar.
- `apply_catalog_to_material(mat, name: str, thickness_mm: float=16.0)`
  - Katalogdan Material nesnesine değerleri yaz.

### `data.section_catalog`

Path: `data/section_catalog.py`

data/*.json dosyalarındaki kesit kataloglarını yükler.
- steel_sections_W.json  → I/Wide Flange
- steel_sections_C.json  → Channel
- steel_sections_L.json  → Angle
- steel_sections_P.json  → Pipe

#### Module Functions

- `_f(val, default=0.0 -> float)`
  - JSON'dan gelen değeri güvenli float yap. None → default.
- `_make_section(entry: dict, section_type: SectionType, family: str -> Section | None)`
  - JSON entry'sini Section'a çevir.
- `load_catalog_from_dir(data_dir: Path -> dict[str, Section])`
  - Verilen klasördeki tüm steel_sections_*.json dosyalarını yükler.

### `data.seismic`

Path: `data/seismic.py`

#### Module Functions

- `get_tsc2018_site_coefficients(ss: float, s1: float, site_class: str -> tuple[float, float])`
  - TBDY 2018 Tablo 2.1 ve 2.2'ye göre doğrusal interpolasyon ile Fs ve F1 katsayılarını hesaplar.

### `data.serializer`

Path: `data/serializer.py`

#### Classes

- **DomainJSONEncoder** (json.JSONEncoder) (line 214)
  - `default(self, obj)`

#### Module Functions

- `_encode_plane(p: Plane -> dict)`
- `_decode_plane(d: dict -> Plane)`
- `_encode(obj: Any -> Any)`
- `_decode(obj: Any -> Any)`
- `save_project_file(project, path: Path -> None)`
- `load_project_file(path: Path)`

### `domain.bounds`

Path: `domain/bounds.py`

#### Classes

- **Bounds3D** (line 7)
  - `center(self)`
  - `size(self)`
  - `half_size(self)`

### `domain.definition`

Path: `domain/definition.py`

#### Classes

- **Material** (line 20)
  - `E(self -> float)`
  - `G(self -> float)`
  - `nu(self -> float)`
  - `is_concrete(self -> bool)`
  - `is_steel(self -> bool)`
- **Section** (line 128)
  - `__post_init__(self)`
  - `is_concrete(self -> bool)`
- **AreaSection** (line 169)
  - `effective_bend_thick(self -> float)`
- **LinkProp** (line 206)
- **LinkPropLinear** (LinkProp) (line 212)
- **Restraint** (line 227)
  - `from_list(cls, values)`
  - `is_free(self)`
  - `is_fully_fixed(self)`
  - `fixed_dofs(self)`
  - `free_dofs(self)`
  - `as_list(self)`
  - `as_dict(self)`
  - `as_int_mask(self)`
- **WindConfig** (line 257)
  - `vb0(self -> float)`
  - `vb0(self, val: float)`
  - `terrain_category(self -> str)`
  - `terrain_category(self, val: str)`
- **SnowConfig** (line 286)
  - `exposure_coefficient(self -> float)`
  - `exposure_coefficient(self, val: float)`
  - `thermal_coefficient(self -> float)`
  - `thermal_coefficient(self, val: float)`
- **SeismicConfig** (line 309)
  - `ss(self -> float)`
  - `s1(self -> float)`
  - `soil_class(self -> str)`
  - `importance_factor(self -> float)`
  - `behavior_factor(self -> float)`
  - `overstrength_factor(self -> float)`
- **ProjectConfig** (line 349)
- **GeneralProjectInfo** (line 356)
- **SiteInformation** (line 373)
- **ProjectInfo** (line 383)
- **WindResult** (line 390)
- **LoadManager** (line 401)
  - `add_area_load_transfer(self, polygon, load: 'AreaUniformLoad', *, analysis_data: Any | None=None, transfer_target: str='frames', dist_type: DistType=DistType.ONE_WAY_U1 -> dict)`
  - `area_load_transfers_for_polygon(self, polygon_id: int -> list[dict])`
- **ReportManager** (line 454)
  - `add_report(self, report -> None)`
    - Aynı rapor nesnesi listede yoksa güvenli bir şekilde ekler.
  - `clear(self -> None)`
- **AnalysisManager** (line 467)
- **QuadDefinition** (line 474)
- **SectionCut** (line 481)
- **LoadPattern** (line 500)
- **StaticLoadAssignment** (line 507)
- **LoadCase** (line 514)
- **ModalCase** (line 526)
- **ComboItem** (line 538)
- **LoadCombination** (line 544)
- **PointLoad** (line 552)
- **LoadSegment** (line 568)
  - `to_points(self)`
- **FrameDistributedLoad** (line 581)
  - `add_segment(self, x1, x2, q1, q2)`
  - `clear(self)`
  - `to_sap_loads(self)`
- **FrameGravityLoad** (line 614)
- **FrameTemperatureLoad** (line 622)
- **AreaGravityLoad** (line 631)
- **AreaRefTemperatureLoad** (line 639)
- **AreaStrainLoad** (line 646)
- **AreaSurfacePressureLoad** (line 653)
- **AreaTemperatureLoad** (line 662)
- **AreaUniformLoad** (line 671)
- **AreaUniformToFrameLoad** (line 682)
- **AreaWindPressureLoad** (line 693)
- **SpectrumFunction** (line 701)
  - `__post_init__(self)`
  - `generate_tbdy2018_points(self, num_points: int=200)`
  - `get_sa(self, period: float -> float)`
- **ResponseSpectrumLoadAssignment** (line 760)
- **ResponseSpectrumCase** (line 768)
- **AutoSeismicTSC2018** (line 778)
- **SDPolygonPoint** (line 796)
- **SDShape** (line 805)
- **SDSection** (line 817)
- **MassContribution** (line 838)
- **MassAssembly** (line 847)
- **ConstraintDefinition** (line 859)
- **WindDirectionResult** (line 882)

### `domain.element`

Path: `domain/element.py`

#### Classes

- **Element** (line 22)
  - `__post_init__(self)`
  - `toggle_selection(self -> None)`
  - `mark_dirty(self -> None)`
- **Node** (Element) (line 45)
  - `__init__(self, x: float=0.0, y: float=0.0, z: float=0.0, label: str='', restraint: D.Restraint | None=None, dof_indices=None, connected=None, loads=None, coord_sys: str='GLOBAL', coord_type: str='Cartesian', special_jt: bool=False, constraint_name: str | None=None, mass_coord_sys: str='Joint Local', load_pattern: str='', mass_1: float=0.0, mass_2: float=0.0, mass_3: float=0.0, mmi_1: float=0.0, mmi_2: float=0.0, mmi_3: float=0.0, added_mass_1: float=0.0, added_mass_2: float=0.0, added_mass_3: float=0.0, added_mmi_1: float=0.0, added_mmi_2: float=0.0, added_mmi_3: float=0.0, spring_u1: float=0.0, spring_u2: float=0.0, spring_u3: float=0.0, spring_r1: float=0.0, spring_r2: float=0.0, spring_r3: float=0.0, **kwargs)`
  - `x(self)`
  - `x(self, v)`
  - `y(self)`
  - `y(self, v)`
  - `z(self)`
  - `z(self, v)`
  - `coords(self)`
  - `set_coords(self, x, y, z)`
  - `distance_to(self, other: 'Node' -> float)`
  - `is_restrained(self)`
  - `is_free(self)`
  - `has_any_restraint(self)`
  - `enumerate_dofs(self, start_index: int -> int)`
  - `get_dof_index(self, name: str)`
  - `add_connection(self, element)`
  - `total_mass(self)`
  - `has_mass(self -> bool)`
- **Frame** (Element) (line 224)
  - `__post_init__(self)`
  - `dist_loads(self -> list[D.FrameDistributedLoad])`
  - `get_length(self -> float)`
  - `get_midpoint(self)`
  - `get_axis(self)`
  - `get_local_axes(self -> glm.mat3)`
- **Area** (Element) (line 324)
  - `__post_init__(self)`
  - `thickness(self -> float)`
  - `thickness(self, value)`
  - `section(self)`
  - `effective_bend_thick(self -> float)`
- **Link** (Element) (line 380)
  - `__init__(self, node_i: Node | None=None, node_j: Node | None=None, propname: str='LINK1', label: str='', **kwargs)`

#### Module Functions

- `id_to_color(obj_id: int -> tuple[float, float, float])`
- `color_to_id(r, g, b -> int)`

### `domain.grid`

Path: `domain/grid.py`

#### Classes

- **Axis** (line 15)
  - `normalized_direction(self -> np.ndarray)`
  - `start_point(self -> np.ndarray)`
  - `end_point(self -> np.ndarray)`
- **ObliqueAxis** (line 47)
- **Grid** (line 58)
  - `__post_init__(self)`
  - `create_default(self)`
  - `axes(self -> list[Axis])`
    - Grid sadece tüm ham akslarını üretir. Filtreleme işine karışmaz.
  - `_ortho_axes(self, prim, sec, zs, first_z, color, kind, prefix, labels, range_fn, swap=False)`
  - `_z_axes(self, xs, ys, zs, cz, half_z)`
  - `_oblique_axes(self, zs, first_z)`
  - `_boundary_axes(self, zs, cz, half_z)`
  - `_y_range(self, x)`
  - `_x_range(self, y)`
  - `_scan(self, v, axis)`
  - `_in_boundary(self, x, y)`
  - `_on_segment(px, py, x1, y1, x2, y2, eps=1e-09)`
  - `_clip_to_boundary(self, p1, p2)`
  - `all_oblique_lines(self)`
  - `snap_points(self, z_level=None)`
  - `snap_points_on_plane(self, plane_axis, level)`
  - `_line_at(p1, p2, v, axis)`
  - `_segment_intersect(p1a, p2a, p1b, p2b)`
  - `visible_axes(self -> Iterator[Axis])`
  - `get_bounds(self)`

### `domain.lighting`

Path: `domain/lighting.py`

#### Classes

- **Light** (line 7)
- **LightingSettings** (line 16)
  - `pos(self -> list[list[float]])`
  - `colors(self -> list[list[float]])`
  - `intensities(self -> list[float])`
  - `set_pos(self, index: int, x: float, y: float, z: float -> None)`
  - `set_color(self, index: int, r: float, g: float, b: float -> None)`
  - `set_intensity(self, index: int, value: float -> None)`
  - `_enabled_light(self, index: int -> Light | None)`

### `domain.line`

Path: `domain/line.py`

#### Classes

- **Line** (Element) (line 13)
  - `__post_init__(self)`
  - `vertices(self -> tuple[Vertex, Vertex])`
  - `length(self -> float)`
  - `midpoint(self -> tuple[float, float, float])`
  - `direction(self -> tuple[float, float, float])`
  - `endpoints(self)`
  - `copy(self -> 'Line')`

### `domain.math_model`

Path: `domain/math_model.py`

#### Classes

- **PolygonAnalysisData** (line 16)
- **MathModel** (line 26)
  - Structural analysis entities, independent of presentation data.
  - `__init__(self)`
  - `compute_bounds(self -> Bounds3D | None)`
  - `bounds(self)`
  - `refresh_bounds(self)`
  - `clear_bounds(self)`
  - `mark_dirty(self)`
  - `invalidate_plane_associations(self)`
  - `mark_plane_associations_current(self)`
  - `refresh_plane_associations(self, planes, force=False, scene=None)`
  - `is_dirty(self)`
  - `clear_dirty(self)`
  - `add_node(self, node: Node)`
  - `add_frame(self, frame: Frame)`
  - `add_area(self, area: Area)`
  - `add_link(self, link: Link)`
  - `add_polygon(self, polygon: Polygon)`
  - `add_line(self, line: Line)`
  - `can_remove(self, element: Element -> tuple[bool, str])`
  - `remove_element(self, element: Element | Polygon | Line -> bool)`
  - `restore_element(self, element: Element)`
  - `mark_dirty_from_node(self, node)`
  - `get_element_by_label(self, label: str)`
  - `get_element_by_id(self, unique_id)`
  - `get_element_by_unique_id(self, unique_id: int)`
  - `all_elements(self)`
  - `get_selected(self)`
  - `clear_selections(self -> int)`
  - `get_bounds(self)`
  - `_bucket(self, element: Element | Polygon | Line)`
  - `is_element_added(self, element: Element | Polygon | Line -> bool)`
  - `add_element(self, element: Element | Polygon | Line -> bool)`
  - `__repr__(self)`
  - `summary(self -> str)`

### `domain.polygon`

Path: `domain/polygon.py`

#### Classes

- **Polygon** (Element) (line 23)
  - `__post_init__(self)`
  - `is_valid(self -> bool)`
  - `centroid(self -> tuple[float, float, float])`
  - `calculate_normal(nodes, use_newell: bool=True -> glm.vec3)`
  - `calculate_plane_axes(nodes -> tuple[glm.vec3, glm.vec3, glm.vec3])`
  - `get_plane_frame(self)`
  - `classify_load_direction(self, load_dir_enum, cos_threshold: float=0.85)`
  - `to_vertices(self -> list[Vertex])`
  - `is_load_transfer(self -> bool)`
  - `assoc_plane(self, *, depth: float | None=None)`
    - Polygon düzleminde, polygon uv bbox'ı ve assoc_depth bandı ile Plane.
  - `_assoc_tolerance(self, pl, world_pts -> float)`
  - `refresh_assoc(self, math_model, *, force: bool=False, write: bool=True, excluded_override: set[int] | None=None -> set[int])`
    - Uygun frame'leri tarar.
  - `toggle_assoc(self, uid: int, on: bool -> bool)`
    - Panelden manuel seçim. (Draft mekanizması paneldedir.)
  - `clear_excluded(self -> bool)`
  - `set_dist_type(self, dist_type: E.DistType | str | int -> None)`
    - UI/panel setter. string/int/Enum hepsini kabul eder.
  - `set_angle_tolerance(self, deg: float -> None)`
  - `set_assoc_depth(self, depth: float -> None)`
  - `assoc_frame_angle_deg(self, frame -> float)`
    - UI için: frame'in seçili local eksene göre açısı (derece).

#### Module Functions

- `_coords(v -> tuple[float, float, float])`

### `domain.project`

Path: `domain/project.py`

#### Classes

- **Project** (line 26)
  - `__post_init__(self)`
  - `_ensure_default_active_plane(self)`
  - `grid(self -> Grid)`
  - `grid(self, value: Grid -> None)`
  - `polygons(self -> dict[int, Polygon])`
  - `polygons(self, value: dict[int, Polygon] -> None)`
  - `lines(self -> dict[int, Line])`
  - `lines(self, value: dict[int, Line] -> None)`
  - `add_polygon(self, polygon: Polygon -> None)`
  - `remove_polygon(self, polygon_id: int -> bool)`
  - `add_line(self, line: Line -> None)`
  - `remove_line(self, line_id: int -> bool)`
  - `polygon_analysis_data(self, polygon: Polygon | int, *, create: bool=True -> PolygonAnalysisData | None)`
  - `_add(self, registry: dict, obj, key: str='name' -> None)`
  - `add_material(self, m)`
  - `add_section(self, s)`
  - `add_area_section(self, s)`
  - `add_link_prop(self, p)`
  - `add_load_pattern(self, p)`
  - `add_load_case(self, c)`
  - `add_modal_case(self, c)`
  - `add_combination(self, c)`
  - `add_spectrum_function(self, s)`
  - `add_response_spectrum_case(self, r)`
  - `add_auto_seismic(self, a)`
  - `add_section_cut(self, s)`
  - `add_constraint_definition(self, c)`
  - `get_section_cut(self, name)`
  - `get_section_by_name(self, name)`
  - `get_material_by_name(self, name)`
  - `get_link_prop_by_name(self, name)`
  - `filtered_grid_axes(self -> list)`
    - Return grid axes prepared by the geometry processing layer.
  - `invalidate_grid_planes(self)`
  - `grid_planes(self -> list[Plane])`
  - `invalidate_grid_planes(self)`
  - `all_planes(self -> dict[str, Plane])`
  - `get_plane(self, name: str -> Plane | None)`
  - `get_plane_by_id(self, plane_id: str -> Plane | None)`
  - `plane_names(self -> list[str])`
  - `add_plane(self, plane: Plane -> Plane)`
  - `remove_plane(self, name: str -> bool)`
  - `active_plane_id(self -> str | None)`
  - `active_plane(self -> Plane | None)`
  - `activate_plane(self, plane: str | Plane -> Plane)`
  - `deactivate_plane(self -> Plane | None)`
  - `planes_containing(self, pt -> list[Plane])`
  - `grid_levels(self, orientation: str -> list[float])`
  - `create_grid_plane(self, orientation: str, level: float, depth_minus: float=0.0, depth_plus: float=0.0, name: str='' -> Plane | None)`
  - `create_tbdy2018_spectrum(self, name, ss, s1, site_class='ZC', r_coeff=1.0, d_coeff=1.0, i_coeff=1.0, tl=6.0, num_points=200 -> SpectrumFunction)`
  - `save(self, filepath: str -> None)`
  - `load(cls, filepath: str -> 'Project')`
  - `sync_grid_from_s2k_lines(self, grid_lines: list[dict] -> None)`
  - `_migrate_materials(self)`
  - `__repr__(self -> str)`
  - `summary(self -> str)`
- **ProjectCatalog** (line 390)
  - `__init__(self, project)`
  - `list_sections(self)`
  - `get_section(self, name)`
  - `get_link_prop(self, name)`
  - `list_materials(self)`
  - `get_material(self, name)`
  - `list_link_props(self)`
  - `list_load_patterns(self)`
  - `list_planes(self)`

### `domain.scene`

Path: `domain/scene.py`

#### Classes

- **Scene** (line 10)
  - Persistent presentation data, independent of the structural MathModel.
  - `__init__(self)`
  - `lights(self -> list[Light])`
  - `compute_bounds(self -> Bounds3D | None)`
  - `bounds(self -> Bounds3D | None)`
  - `refresh_bounds(self -> Bounds3D | None)`
  - `clear_bounds(self -> None)`
  - `mark_dirty(self -> None)`
  - `is_dirty(self -> bool)`
  - `clear_dirty(self -> None)`
  - `__repr__(self -> str)`
  - `summary(self -> str)`

### `domain.vertex`

Path: `domain/vertex.py`

#### Classes

- **Vertex** (line 11)
  - `coords(self -> tuple[float, float, float])`
  - `distance_to(self, other: 'Vertex' -> float)`
  - `copy(self -> 'Vertex')`

### `geometry.area_builder`

Path: `geometry/area_builder.py`

#### Classes

- **AreaBuilder** (line 18)
  - `build(self, area: Area -> tuple[np.ndarray, np.ndarray, np.ndarray])`
  - `_plane_axes(self, points)`
  - `build_simple(self, area: Area -> np.ndarray)`

#### Module Functions

- `normalize(v)`

### `geometry.base_builder`

Path: `geometry/base_builder.py`

#### Classes

- **BaseGeometryBuilder** (ABC, Generic[T]) (line 9)
  - Tüm geometry builder'ların temel sınıfı
  - `build(self, element: T -> tuple[np.ndarray, np.ndarray, np.ndarray])`
    - Element için geometry oluştur
  - `build_all(self, elements: list[T] -> list[tuple[np.ndarray, np.ndarray, np.ndarray]])`
    - Tüm elementler için geometry oluştur

### `geometry.frame_builder`

Path: `geometry/frame_builder.py`

#### Classes

- **FrameBuilder** (line 21)
  - `__init__(self)`
  - `_ensure_closed_cw(self, profile)`
  - `_prepare_geometry(self, frame)`
  - `build(self, frame: Frame -> tuple[np.ndarray, np.ndarray, np.ndarray])`
  - `build_lines(self, frame: Frame -> np.ndarray)`
    - Frame geometrisinin gerçek kenarlarını oluşturur.
  - `build_simple_lines(self, frame: Frame -> np.ndarray)`
    - Frame'in sadece merkez eksenini çizen basit çizgi.

#### Module Functions

- `normalize(v)`

### `geometry.geometry_processor`

Path: `geometry/geometry_processor.py`

#### Classes

- **ProcessedGeometry** (line 15)
- **GeometryProcessor** (line 25)
  - Prepare renderer-compatible geometry without depending on rendering code.
  - `process(cls, scene, plane=None, math_model=None -> ProcessedGeometry)`
  - `process_nodes(cls, nodes: list, plane -> list)`
  - `_mode(plane)`
  - `_coordinates(point -> np.ndarray)`
  - `_copy_point(point, coordinates)`
  - `_copy_segment(cls, element, endpoint_names, start, end)`
  - `process_grid_axes(cls, project_or_grid, plane=None -> list)`
    - Filter or clip grid axes for the active plane.
  - `process_lines(cls, lines: list, plane -> list)`
    - Filter or clip lines and frame-like segments efficiently.
  - `process_polygons(cls, polygons: list, plane -> list)`
    - Filter surfaces or crop their boundaries against the plane bounds.
  - `_clip_polygon_to_bounds(plane, world_points, local_points -> np.ndarray)`
  - `_copy_polygon_point(cls, nodes, world_points, point)`
  - `_clip_polygon_halfspace(points, axis, bound, *, keep_above, tolerance)`
  - `_polygon_area(points -> float)`
- **_CoordinatePoint** (line 289)
  - `coords(self)`

### `geometry.link_builder`

Path: `geometry/link_builder.py`

#### Classes

- **LinkBuilder** (line 14)
  - `build(self, link: Link -> tuple[np.ndarray, np.ndarray, np.ndarray])`
    - Basit link - sadece pos ve norm (6 float)
  - `build_simple_lines(self, link: Link -> np.ndarray)`
    - Link'in sadece merkez çizgisi.

#### Module Functions

- `normalize(v)`

### `geometry.node_builder`

Path: `geometry/node_builder.py`

Node geometri üretici.

Node için iki ayrı iş:
  - build()              → shaded mesh (free node: küp; restraint: sembol)
  - build_simple_points() → simple mod için 1 nokta

Vertex layout her ikisinde de 9 float:
    pos3 (local) + normal3 + center3 (global)

`standard.vert` `isConstantSize=1` iken aCenter + aPos*factor hesaplar;
`isConstantSize=0` iken mvp * aPos (global) hesaplar. NodeRenderer
`isConstantSize=1` kullandığı için aPos local kalabilir.

#### Classes

- **NodeBuilder** (line 30)
  - Node mesh'i (küp veya restraint sembolleri) üretir.
  - `__init__(self)`
  - `set_size(self, size: float -> bool)`
  - `set_restraint_size(self, size: float -> bool)`
  - `build(self, node: Node -> tuple[np.ndarray, np.ndarray, np.ndarray])`
  - `build_simple_points(self, node: Node -> np.ndarray)`
    - Simple modda node → 1 nokta (9 float).
  - `_rebuild_shapes(self)`
  - `_build_shapes_for(self, size)`
  - `_create_circle(self, radius: float -> np.ndarray)`
  - `build_simple_restraint_lines(self, node: Node -> np.ndarray)`
  - `_add_restraint_symbols(self, restraint, center, vlist, ilist)`
  - `determine_support_symbols(self, restraint -> dict[str, str | None])`
    - Restraint → her eksende kullanılacak şekil.
  - `_add_symbol(self, shape_name, rot, offset, center, vlist, ilist)`
  - `_add_cube(self, center, vlist, ilist)`
  - `_rot(self, x_deg: float, y_deg: float, z_deg: float -> np.ndarray)`

### `geometry.polygon_builder`

Path: `geometry/polygon_builder.py`

#### Classes

- **PolygonBuilder** (line 19)
  - Düz poligon — extrude YOK.
  - `build(self, polygon: Polygon -> tuple[np.ndarray, np.ndarray, np.ndarray])`
  - `build_simple_lines(self, polygon: Polygon -> np.ndarray)`
    - Sınır çizgileri için (Beyaz renkli kenar telleri)
  - `build_lines(self, polygon: Polygon -> np.ndarray)`
    - Wireframe mod için — sadece kenar çizgileri.
  - `build_simple_points(self, polygon: Polygon -> np.ndarray)`
    - Simple mod için sadece köşe noktaları (6 float per nokta).
  - `build_simple(self, polygon: Polygon -> np.ndarray)`
    - Simple modda transparan poligon dolgusu (GL_TRIANGLES) için vertex üretir.

#### Module Functions

- `normalize(v)`

### `geometry.profile_generator`

Path: `geometry/profile_generator.py`

#### Classes

- **ProfileGenerator** (line 22)
  - 2D profil geometrisi üretici sınıf
  - `__init__(self)`
    - Profil üretici fonksiyonlarının mapping'i
  - `get_profile(self, section_type: SectionType | str, params: dict -> np.ndarray)`
    - Ana profil üretici fonksiyon - FrameGeometryBuilder bunu çağırır
  - `_validate_params(self, section_type: SectionType, params: Any -> dict)`
    - Parametreleri doğrula ve varsayılan değerleri ekle.
  - `_rect_profile(self, params: dict -> list[tuple[float, float]])`
    - Dikdörtgen profil
  - `_circle_profile(self, params: dict -> list[tuple[float, float]])`
    - Daire profil
  - `_i_profile(self, params: dict -> list[tuple[float, float]])`
    - I-profil (IPE, HEA, HEB)
  - `_l_profile(self, params: dict -> list[tuple[float, float]])`
    - L-profil (köşebent)
  - `_t_profile(self, params: dict -> list[tuple[float, float]])`
    - T-profil
  - `_pipe_profile(self, params: dict -> list[tuple[float, float]])`
    - Boru profil
  - `_tube_profile(self, params: dict -> list[tuple[float, float]])`
    - Kutu profil
  - `_c_profile(self, params: dict -> list[tuple[float, float]])`
    - C-profil (U-profil, kanal)
  - `_custom_profile(self, params: dict -> list[tuple[float, float]])`
  - `_default_profile(self, params: dict -> list[tuple[float, float]])`
    - Varsayılan profil (100x100 kare)
  - `get_profile_info(self, profile: np.ndarray -> dict)`
    - Profil hakkında bilgi döndür (alan, centroid, bounds)

#### Module Functions

- `normalize(v: np.ndarray -> np.ndarray)`
  - Normalize vector with safe division.
- `rotate_outline_2d(outline: np.ndarray, angle_deg: float -> np.ndarray)`
  - 2D outline'ı döndür
- `create_mesh_from_outline(outline: np.ndarray, start: np.ndarray, end: np.ndarray, closed: bool=True, include_caps: bool=False -> tuple[np.ndarray, np.ndarray])`
  - outline: (N,2) veya (N,3) numpy array, 2D kesit
- `get_profile_area(profile: np.ndarray -> float)`
  - Profil alanını hesapla (shoelace formula)
- `get_profile_centroid(profile: np.ndarray -> tuple[float, float])`
  - Profil ağırlık merkezini hesapla
- `get_profile_bounds(profile: np.ndarray -> tuple[float, float, float, float])`
  - Profil sınırlarını hesapla (min_x, max_x, min_y, max_y)

### `geometry.project_builder`

Path: `geometry/project_builder.py`

ProjectBuilder — tüm proje tanımlarını ve elementlerini
`project.unit_system`'de yaratan merkezi sınıf.

- UnitSystem `build` başında set edilir (`unit_system` parametresi)
- Tüm `add_*` metodları `project.unit_system`'de değer alır
- Scene, material, section, load — hepsi `project`'e bağlı
- S2K import: `builder = ProjectBuilder(project, UnitSystem.TONF_M)`
  → tüm handler'lar `builder.add_*` → değerler `Tonf, m` → `convert_project_units(N_MM)`

#### Classes

- **ProjectBuilder** (line 35)
  - Proje oluşturucu — `project.unit_system`'de tüm tanımları yaratır.
  - `__init__(self, project: Project, unit_system: UnitSystem)`
  - `set_project_info(self, **kwargs)`
    - ProjectInfo, GeneralProjectInfo, SiteInformation alanları.
  - `add_material(self, name: str, *, mat_type=None, color=None, E1: float=210000.0, G12: float=81000.0, density: float=7.85e-06, fy: float=235.0, fu: float=360.0, nu12: float=0.3, **kwargs -> Material)`
    - Material `project.unit_system`'de. Değerler dönüştürülmez.
  - `add_section(self, name: str, *, profile_type, profile_params: dict, material: Material | None=None, color=None, sd_section=None, catalog_props: dict | None=None, catalog_source: str='' -> Section)`
    - Section `project.unit_system`'de.
  - `_default_material(self -> Material)`
    - Hiç material yoksa DEFAULT_STEEL.
  - `add_link_prop(self, name: str, *, prop_type, **kwargs -> LinkProp)`
  - `add_load_pattern(self, name: str, *, design_type: str='Dead', self_wt_mult: float=0.0 -> LoadPattern)`
  - `add_load_case(self, name: str, **kwargs -> LoadCase)`
  - `add_modal_case(self, name: str, **kwargs -> ModalCase)`
  - `add_combination(self, name: str, **kwargs -> LoadCombination)`
  - `add_spectrum_function(self, **kwargs -> SpectrumFunction)`
  - `add_response_spectrum_case(self, **kwargs -> ResponseSpectrumCase)`
  - `add_auto_seismic(self, **kwargs -> AutoSeismicTSC2018)`
  - `add_section_cut(self, name: str, **kwargs -> SectionCut)`
  - `add_sd_section(self, name: str, **kwargs -> SDSection)`
  - `create_node(self, x: float, y: float, z: float, label: str='', restraint=None -> Node)`
  - `create_frame(self, node_i: Node, node_j: Node, section_name: str, rotation_deg: float=0.0, label: str='' -> Frame)`
  - `create_area(self, nodes: list[Node], thickness: float, label: str='' -> Area)`
  - `create_link(self, node_i: Node, node_j: Node, prop_name: str, label: str='' -> Link)`
  - `set_grid_lines(self, grid_lines)`
  - `set_joint_constraints(self, constraints: dict[str, str])`
  - `finalize(self)`
    - Scene'i project'e bağla, mass_source_map, load'ları kontrol et.
  - `finalize_and_convert(self, target: UnitSystem=UnitSystem.N_MM)`

### `geometry.scenebuilder`

Path: `geometry/scenebuilder.py`

ProjectBuilder'ın alt katmanı — primitive yaratım.

S2K parse/bağlama işleri `tools/s2k/scene_builder.py`'da.
Bu sınıf sadece Node/Frame/Area/Link/Material/Section/LinkProp yaratır.

#### Classes

- **SceneBuilder** (line 24)
  - `__init__(self, project: Project)`
  - `create_material(self, name: str, mat_type: MatType, E: float=200000000.0, density: float=7850, color: tuple[float, float, float]=(0.8, 0.8, 0.8) -> Material)`
  - `create_section(self, name: str, profile_type: SectionType, profile_params: dict[str, float], material: Material | None=None, color: tuple[float, float, float]=(0.8, 0.8, 0.8) -> Section)`
  - `create_link_prop(self, name: str, prop_type: LinkPropType=LinkPropType.LINEAR, Ke: dict | None=None, Ce: dict | None=None -> LinkProp)`
  - `create_node(self, x: float, y: float, z: float, label: str='', restraint: dict[str, bool] | Restraint | None=None -> Node)`
  - `create_frame(self, node_i: Node | str, node_j: Node | str, section_name: str, rotation_deg: float=0.0, label: str='' -> Frame)`
  - `create_area(self, nodes: list, thickness: float, label: str='' -> Area)`
  - `create_link(self, node_i: Node | str, node_j: Node | str, prop_name: str='LINK1', label: str='' -> Link)`

### `geometry.sd_to_areas`

Path: `geometry/sd_to_areas.py`

#### Module Functions

- `_frame_local_frame(frame: Frame -> tuple[glm.vec3, glm.vec3, glm.vec3])`
  - Frame'in (e1=axis, e2, e3) ortonormal çerçevesi. glm.mat3 sıralamasına bağımlı değil.
- `sd_frame_to_areas(frame: Frame, thickness: float, material: Material | None=None, section_name: str='', label_prefix: str='' -> tuple[list[Area], list[str]])`

### `inspector`

Path: `inspector/__init__.py`

Inspector — bağımsız sahne element editörü.

Kullanım (CadApp içinden):
    from inspector import InspectorWindow

    self.inspector = InspectorWindow(scene=project.math_model)

    # her frame:
    self.inspector.draw()

    # seçim değişince:
    self.inspector.set_selection(selected_elements)

### `inspector.controller`

Path: `inspector/controller.py`

#### Classes

- **InspectorController** (line 5)
  - `__init__(self, scene=None, catalog=None)`
  - `type_counts(self -> dict[str, int])`
  - `active_objects(self -> list)`
  - `common_type(self)`
  - `set_selection(self, elements)`
  - `set_filter_type(self, t: str | None)`
  - `clear(self)`
  - `refresh_from_scene(self)`
  - `apply(self -> bool)`
  - `cancel(self)`

### `inspector.demo`

Path: `inspector/demo.py`

Standalone demo — `python -m inspector.demo`

Küçük bir sahne yaratır, Inspector'ı açar. Scene'in gerçek sınıfları
kullanılabilir; burada sadece `scene.iter_elements(type=...)` çağrısı
varsayılıyor.

#### Module Functions

- `_make_demo_scene()`
  - Gerçek domain'inden sahne üret. Aşağıdaki import'lar senin projene
- `main()`

### `inspector.fields`

Path: `inspector/fields.py`

#### Classes

- **_Mixed** (line 32)
  - `__repr__(self)`

#### Module Functions

- `inspector_fields(obj -> list[tuple[str, Any]])`
- `common_value(objects: list, key: str)`
- `set_value_all(objects: list, key: str, value)`
- `is_mixed(v -> bool)`

### `inspector.schema_bridge`

Path: `inspector/schema_bridge.py`

#### Classes

- **Catalog** (Protocol) (line 23)
  - `list_sections(self -> list[str])`
  - `get_section(self, name: str -> Any | None)`
  - `list_materials(self -> list[str])`
  - `get_material(self, name: str -> Any | None)`
  - `list_link_props(self -> list[str])`
  - `list_load_patterns(self -> list[str])`

#### Module Functions

- `schema_for_object(obj)`

### `inspector.selection`

Path: `inspector/selection.py`

Seçim modeli — Inspector'ın gördüğü element kümesi.

#### Classes

- **SelectionModel** (line 6)
  - `__init__(self)`
  - `set_single(self, element, values: dict[str, Any])`
  - `set_multi(self, elements, common_values: dict[str, Any])`
  - `clear(self)`
  - `_deselect_all(self)`
  - `is_empty(self -> bool)`
  - `is_single(self -> bool)`
  - `count(self -> int)`
  - `primary(self -> Any | None)`
  - `reset_to_original(self)`
    - Cancel — değişiklikleri geri al (scene'e dokunmadan).

#### Module Functions

- `_deep_copy(d)`
  - MIXED gibi sentinel'leri koruyan basit kopya.

### `inspector.topbar`

Path: `inspector/topbar.py`

#### Classes

- **TopBar** (line 7)
  - `__init__(self, inspector)`
  - `app(self)`
  - `draw(self)`
  - `_on_left_toggle(self)`
  - `_on_apply(self)`
  - `_on_delete(self)`
  - `_on_undo(self)`
  - `_on_redo(self)`
  - `_on_fit(self)`
  - `_on_draw_line(self)`
  - `_on_draw_poly(self)`
  - `_on_to_frame(self)`
  - `_on_to_link(self)`
  - `_on_to_plane(self)`
  - `_on_column(self)`

### `inspector.widgets`

Path: `inspector/widgets.py`

#### Module Functions

- `draw_field_row(objects: list, key: str, catalog -> bool)`
- `_draw_mixed(objects, key, catalog -> bool)`
- `_dispatch(objects, key, value, catalog, mixed=False -> bool)`
- `_draw_bool(objects, key, value, mixed -> bool)`
- `_draw_int(objects, key, value, mixed -> bool)`
- `_draw_float(objects, key, value, mixed -> bool)`
- `_draw_string(objects, key, value, mixed=False -> bool)`
- `_draw_enum(objects, key, value, mixed -> bool)`
- `_draw_restraint(objects, key, value: Restraint -> bool)`
- `_draw_vertex(objects, key, value: Vertex -> bool)`
- `_draw_color(objects, key, value -> bool)`
- `_draw_section(objects, key, value, catalog -> bool)`
- `_draw_material(objects, key, value, catalog -> bool)`
- `_draw_link_prop(objects, key, value, catalog -> bool)`
- `_draw_list(objects, key, value -> bool)`
- `_draw_section(obj, key, value, catalog -> bool)`
- `_draw_material(obj, key, value, catalog -> bool)`
- `_draw_area_section(obj, key, value -> bool)`
- `_draw_link_prop(obj, key, value, catalog -> bool)`
- `_scene_groups(scene, math_model=None)`
- `_collect(scene, type_name)`
- `_element_label(el -> str)`
- `_parse_filter(flt: str)`
- `_matches(el, type_name: str, text_hint: str, id_hint -> bool)`
- `_unique_id(el)`
- `_copy_to_clipboard(text: str)`
- `_col(r, g, b, a=1.0 -> imgui.ImVec4)`
- `_domain_field_items(element -> list[tuple[str, Any]])`
  - Return all stored domain fields, including fields added by future models.

### `inspector.window`

Path: `inspector/window.py`

#### Classes

- **InspectorWindow** (line 19)
  - `__init__(self, scene=None, catalog=None, standalone=False)`
  - `set_context(self, ctx: dict)`
  - `open(self)`
  - `close(self)`
  - `toggle(self)`
  - `set_scene(self, scene)`
  - `set_project(self, project)`
  - `set_catalog(self, catalog)`
  - `set_selection(self, elements: list)`
  - `_sync_scene_selection(self, elements)`
  - `refresh(self)`
  - `draw(self)`
  - `_draw_body(self)`
  - `_draw_tree(self)`
  - `_select_first_match(self, flt: str)`
  - `_draw_filtered_groups(self, flt: str, force_open: bool)`
  - `_select_via_scene(self, el)`
  - `_focus_in_scene(self, el)`
  - `_draw_form(self)`
  - `_draw_type_selector(self, c)`

### `loads.wind_zone_distribution_service`

Path: `loads/wind_zone_distribution_service.py`

#### Classes

- **WindZoneDistributionService** (line 16)
  - Zone poligonlarındaki rüzgar yüklerini, surface üzerinden frame'lere aktarır.
  - `distribute(cls, project, *, kind: str='CPE10', cpi_positive: float=0.2, cpi_negative: float=-0.3, tributary_width: float=1.0, clear_existing: bool=True -> int)`
  - `_plane_tolerance(cls, project_or_scene -> float)`
    - Birim sistemine göre düzlem toleransı (sahne birimi cinsinden).
  - `_find_surface(cls, math_model, surface_ref -> Optional[Any])`
    - zone.windplane["surface"] → surface Polygon.
  - `_distribute_one_zone(cls, project, math_model, zone, *, kind: str, cpi_pos: float, cpi_neg: float, tributary_width: float -> int)`
  - `_line_polygon_intersections_2d(p1_2d, p2_2d, poly_2d -> List[tuple])`
    - Bir çizgi parçasının (p1_2d → p2_2d) kapalı poligon (poly_2d) ile
  - `_merge_segments(cls, segs: List[LoadSegment] -> List[LoadSegment])`
    - Bitişik ve aynı q değerine sahip segmentleri birleştirir.
  - `_ensure_load_pattern(cls, definitions, name: str -> None)`
  - `_clear_wind_patterns(cls, math_model -> None)`
  - `_collect_zones(cls, math_model -> List[Any])`
    - MathModel içindeki ZONE poligonlarını döndürür.

### `logging_config`

Path: `logging_config.py`

#### Classes

- **DuplicateMessageFilter** (logging.Filter) (line 18)
  - Aynı logger/seviye/mesaj birleşimini zaman penceresi içinde bastırır.
  - `__init__(self, window_seconds: float=1.0, max_tracked: int=2048 -> None)`
  - `filter(self, record: logging.LogRecord -> bool)`
- **_ColorFormatter** (logging.Formatter) (line 81)
  - `format(self, record: logging.LogRecord -> str)`
- **CadLogger** (line 103)
  - Tüm cad.* logger'larının merkezi yapılandırma noktası.
  - `_env(cls, key: str, default: str -> str)`
  - `_resolve_level(name: str, default: int -> int)`
  - `_console_level(cls -> int)`
  - `_file_level(cls -> int)`
  - `_root_level(cls -> int)`
  - `_console_enabled(cls -> bool)`
  - `_configure_root_once(cls -> None)`
  - `_full_name(cls, name: str -> str)`
  - `get(cls, name: str=ROOT_NAME -> logging.Logger)`
  - `set_module_level(cls, name: str, level: str -> None)`
  - `setup(cls, level: str='INFO' -> None)`
  - `log_file_path(cls -> Path | None)`
  - `print_summary(cls -> None)`
    - Aktif yapılandırmayı konsola bas.

### `main`

Path: `main.py`

#### Module Functions

- `_bootstrap( -> None)`
- `_install_excepthook( -> None)`
- `main()`

### `plane`

Path: `plane/__init__.py`

### `plane.plane`

Path: `plane/plane.py`

#### Classes

- **ChangeOp** (line 18)
- **PendingChange** (line 27)
- **Plane** (line 54)
  - `__init__(self, origin, normal, u=None, v=None, *, plane_id=None, name='', u_min=None, u_max=None, v_min=None, v_max=None, depth_minus=0.0, depth_plus=0.0, filter_mode: SectionFilterMode=SectionFilterMode.INTERSECT)`
  - `x_axis(self)`
  - `y_axis(self)`
  - `boundary(self)`
  - `depth(self)`
  - `from_point_normal(cls, p0, normal, **kw)`
  - `from_3_points(cls, p0, p1, p2, **kw)`
  - `from_2_points_z_up(cls, p1, p2, up=(0.0, 0.0, 1.0), **kw)`
  - `from_2_points(cls, p1, p2, orientation: str, **kw)`
  - `from_polygon(cls, poly, **kw)`
  - `from_axis_offset(cls, axis: str, offset: float, u_min=None, u_max=None, v_min=None, v_max=None, depth_minus=0.0, depth_plus=0.0, **kw)`
  - `from_element(cls, element, *, frame_local_12: bool=False, **kw)`
  - `default_grid_plane_depth(unit_system=None -> float)`
  - `set_filter_mode(self, mode: SectionFilterMode)`
    - Düzlem kesit modunu dinamik olarak değiştirir.
  - `element_passes_filter(self, points: list -> bool)`
    - Verilen eleman noktalarının mevcut politika moduna göre düzlemden geçip geçmediğini saptar.
  - `clip_line_segment(self, p1, p2)`
    - Görsel şölen (CLIP) modu için çizgiyi plane sınırlarına göre keser.
  - `distance(self, pt -> float)`
  - `distance_abs(self, pt -> float)`
  - `project(self, pt -> np.ndarray)`
  - `to_2d(self, pt -> tuple[float, float])`
  - `to_3d(self, uv -> np.ndarray)`
  - `world_to_local(self, point -> np.ndarray)`
  - `local_to_world(self, coordinates -> np.ndarray)`
  - `intersect_ray(self, origin, direction)`
  - `bounds_contains_uv(self, u, v)`
  - `band_contains_pt(self, pt)`
  - `contains_pt(self, pt)`
  - `corners_3d(self)`
  - `all_assoc_ids(self, kind)`
  - `association_revision(self)`
  - `add_assoc(self, kind, uid)`
  - `remove_assoc(self, kind, uid, permanent=True)`
  - `is_excluded(self, kind, uid)`
  - `association_of(self, kind, uid)`
  - `association_counts(self, kind=None)`
  - `refresh_assoc(self, math_model, scene=None)`
  - `classify_element(self, el, kind)`
  - `_triangulate_surface(points)`
  - `_association_bounds(self)`
  - `_association_tolerance(self, world_pts, local_pts)`
  - `_point_in_box(p, lower, upper, tol)`
  - `_segment_intersects_box(cls, a, b, lower, upper, tol)`
  - `_segment_intersects_plane_bounds(cls, a, b, lower, upper, tol)`
  - `_polygon_intersects_box(cls, poly, lower, upper, tol)`
  - `_clip(poly, ax, bound, keep_above, tol)`
  - `_triangle_intersects_plane_bounds(cls, tri, lower, upper, tol)`
  - `_element_points(el, kind)`
  - `is_pending(self, kind, eid)`
  - `pending_of(self, kind, eid)`
  - `add_pending(self, op, kind, eid, data=None)`
  - `clear_pending(self)`
  - `apply_pending(self, math_model, project=None -> dict)`
  - `_build_from_data(self, kind, data, math_model, draft_map, project=None)`
  - `_resolve_node(ref, scene, draft_map)`
  - `_build_node(self, data, math_model, draft_map, project=None)`
  - `_build_frame(self, data, math_model, draft_map, project=None)`
  - `_build_poly(self, data, math_model, draft_map, project=None)`
  - `_build_area(self, data, math_model, draft_map, project=None)`
  - `_build_link(self, data, math_model, draft_map, project=None)`
  - `uv_basis(self)`
  - `set_bounds(self, u_min, u_max, v_min, v_max, recenter=True)`
  - `fit_to_math_model(self, math_model, margin_ratio=0.05, min_margin=100.0)`
  - `__repr__(self)`

#### Module Functions

- `_as_vec3(value, name: str -> np.ndarray)`

### `plane.plane_creation_tool`

Path: `plane/plane_creation_tool.py`

#### Classes

- **PlaneCreationTool** (line 25)
  - `__init__(self, engine)`
  - `start_3pt(self)`
  - `start_2pt_z(self)`
  - `_start(self, mode)`
  - `cancel(self)`
  - `_step_back(self)`
  - `_u_vec(self)`
  - `_v_perp(self)`
  - `_normal(self)`
  - `_dims(self)`
  - `on_mouse_move(self, x, y)`
  - `on_mouse_click(self, x, y -> bool)`
  - `on_key_press(self, key -> bool)`
  - `_model_v_length(self)`
  - `_confirm(self)`
  - `_depth_sensitivity(self)`
  - `_preview_point(self)`
  - `_preview_v_perp(self, point)`
  - `render(self, mvp)`
  - `_upload(self, vao, vbo, verts, mode, color, loc_color, width=1.0)`
  - `_draw_u_v_lines(self, vao, vbo, loc_color)`
  - `_draw_quad_preview(self, vao, vbo, loc_color)`
  - `_draw_quad(self, vao, vbo, loc_color)`
  - `_draw_quad_geometry(self, vao, vbo, v, loc_color, alpha)`
  - `_draw_box(self, vao, vbo, loc_color)`
  - `_draw_hover(self, vao, vbo, loc_color)`
  - `handle_click(self, x, y, button -> bool)`
  - `handle_release(self, x, y, button -> bool)`
  - `handle_move(self, x, y, dx, dy -> bool)`
  - `handle_key(self, key, mods -> bool)`
  - `handle_scroll(self, delta -> bool)`
  - `cleanup(self)`
  - `_same(a, b -> bool)`
- **PlaneFromElementInputHandler** (line 569)
  - `__init__(self, state)`
  - `handle_click(self, x, y, button)`
  - `handle_key(self, key, mods)`
- **PlaneFromElementState** (line 595)
  - Element seçimi state'i.
  - `__init__(self)`
  - `start(self)`
  - `cancel(self)`
  - `set_hover(self, element)`
    - Seçim hover'ında çağrılır.
  - `try_confirm(self -> bool)`
    - Seçili elemandan plane oluştur.

### `plane.plane_manager_panel`

Path: `plane/plane_manager_panel.py`

#### Classes

- **PlaneManagerPanel** (BasePanel) (line 15)
  - `__init__(self)`
  - `_project(self)`
  - `_engine(self)`
  - `_selected_plane(self -> Plane | None)`
  - `_selected_is_custom(self -> bool)`
  - `_sync_render(self)`
  - `open(self)`
  - `close(self)`
  - `on_key_press(self, key -> bool)`
  - `reset(self)`
  - `shutdown(self -> None)`
  - `draw(self)`
  - `_draw_toolbar(self)`
  - `_draw_delete_confirm(self)`
  - `_draw_list(self)`
  - `_draw_detail(self)`
  - `_load_edit(self, plane: Plane, force: bool=False)`
  - `_load_gp(self, gp: Plane)`
  - `_is_edited(self, plane: Plane -> bool)`
  - `_apply_edit(self, plane: Plane)`
  - `_open_plane_viewport(self, plane: Plane | None)`
    - Seçili plane için yeni viewport açar (bağımsız kamera + section filter).
  - `_do_delete(self, name: str)`
  - `_update_preview(self)`
  - `_preview_off(self)`

### `plane.plane_policy`

Path: `plane/plane_policy.py`

#### Classes

- **SectionFilterMode** (str, Enum) (line 9)
  - Düzlem (Plane) filtresinin elemanları nasıl süzeceğini belirleyen politika.
- **PlaneFilterPolicy** (line 18)
  - Plane ve elemanlar arasındaki geometrik süzme politikalarını uygulayan yardımcı motor.
  - `__init__(self, mode: SectionFilterMode=SectionFilterMode.INTERSECT)`
  - `passes_point(self, plane, pt -> bool)`
    - Nokta testi.
  - `passes_segment(self, plane, p1, p2 -> bool)`
    - Çubuk/Çizgi segmenti testi.
  - `passes_polygon(self, plane, points: list -> bool)`
    - Poligon / Yüzey testi.
  - `clip_segment(self, plane, p1, p2 -> tuple[np.ndarray, np.ndarray] | None)`
    - Çizgiyi/Çubuğu plane bounds ve depth sınırlarına göre kırpar (Crop).
  - `passes_segment_intersect_check(self, plane, p1, p2 -> bool)`
  - `passes_poly_intersect_check(self, plane, points: list -> bool)`

### `plane.plane_source_dialog`

Path: `plane/plane_source_dialog.py`

#### Classes

- **PlaneSourceDialog** (line 16)
  - `__init__(self, app)`
  - `open(self)`
  - `close(self)`
  - `draw(self)`
  - `_selected_element(self)`
  - `_start(self)`

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

### `render.axes_renderer`

Path: `render/axes_renderer.py`

LocalAxesRenderer
-----------------
Element'lerin lokal koordinat sistemlerini (1-2-3 eksenleri) düz çizgi olarak çizer.

Renk konvansiyonu:
    1-ekseni → kırmızı  (1.00, 0.15, 0.15)
    2-ekseni → yeşil    (0.20, 1.00, 0.30)
    3-ekseni → cyan     (0.00, 0.90, 1.00)

Geometri:
    Birim uzayda 3 eksen × 2 nokta = 6 vertex.
    Origin (0,0,0) → (1,0,0), (0,1,0), (0,0,1).
    Her vertex position(3f) + color(3f) = 6 float, 24 byte.

Kullanım:
    renderer = LocalAxesRenderer(shader)
    renderer.init_gl()
    ...
    renderer.draw(mvp_matrix)      # çağrı başına bir model matrisi
    ...
    renderer.cleanup()

#### Classes

- **LocalAxesRenderer** (line 64)
  - Element lokal eksenlerini çizen hafif GPU renderer'ı.
  - `__init__(self, shader)`
    - Parameters
  - `init_gl(self -> bool)`
    - VAO/VBO ve shader uniform lokasyonunu hazırlar.
  - `_build_unit_axes(self -> np.ndarray)`
    - Birim uzayda 3 eksen × 2 nokta verisini üretir.
  - `_upload_geometry(self, data: np.ndarray -> None)`
  - `draw(self, mvp: glm.mat4 -> None)`
    - Tek bir element için eksen üçlüsünü çizer.
  - `draw_many(self, mvps -> None)`
    - Birden fazla element için aynı draw call bloğunda çizer.
  - `set_line_width(self, width: float -> None)`
    - NOT: Core profile'da 1.0 üstü driver'a bağlı. Çoğu masaüstü GPU
  - `line_width(self -> float)`
  - `cleanup(self -> None)`
  - `_safe_cleanup(self -> None)`
    - init sırasında yarı tamamlanmış kaynakları temizler.

### `render.base_renderer`

Path: `render/base_renderer.py`

#### Classes

- **BaseRenderer** (ABC, Generic[T]) (line 74)
  - `__init__(self, shader)`
  - `build(self, e: T -> tuple[np.ndarray, np.ndarray, np.ndarray])`
  - `draw_mode(self -> int)`
  - `build_lines(self, e: T -> np.ndarray)`
    - FrameRenderer override eder.
  - `build_simple(self, e: T)`
    - Basit mod (simple) için vertex + renk üretir.
  - `update_dirty(self)`
    - Sadece renk buffer'larını (main + simple) günceller.
  - `update_single_element_color(self, element, color_getter)`
    - Tüm CBO'yu yenilemek yerine sadece tek bir elemanın rengini GPU'da günceller.
  - `_refresh_colors(self)`
    - Elementlerin mevcut is_selected durumuna göre renkleri yeniden üret.
  - `get_bounds(self)`
  - `update(self, raw: list[T])`
  - `_upload(self, v, c, ids, i, line_i)`
  - `_upload_simple(self, v, c, ids)`
  - `render(self, mvp, model=None, cam_pos=None, view=None, proj=None, visible_ids=None)`
  - `render_simple(self, mvp, shader, color=None, alpha=0.5, visible_ids=None)`
  - `update_colors(self, elements, color_func)`
  - `update_simple_colors(self, elements, color_func)`
  - `get(self, eid: str -> T | None)`
  - `_cleanup_main(self)`
  - `_cleanup_simple(self)`
  - `cleanup(self)`
- **FrameRenderer** (BaseRenderer[Frame]) (line 751)
  - `__init__(self, shader)`
  - `build(self, f)`
  - `build_lines(self, f)`
  - `build_simple(self, frame)`
    - Simple mod için eksen çizgisi vertex'leri ve renk matrisi
  - `draw_mode(self)`
  - `render(self, mvp, model=None, cam_pos=None, view=None, proj=None, visible_ids=None)`
- **AreaRenderer** (BaseRenderer[Area]) (line 810)
  - `__init__(self, shader)`
  - `build(self, a)`
  - `build_simple(self, a)`
  - `draw_mode(self)`
  - `set_lighting(self, l)`
  - `render(self, mvp, model=None, cam_pos=None, view=None, proj=None, visible_ids=None)`
- **LinkRenderer** (BaseRenderer[Link]) (line 872)
  - `__init__(self, shader)`
  - `build(self, l)`
  - `build_simple(self, l)`
  - `draw_mode(self)`
  - `render(self, mvp, model=None, cam_pos=None, view=None, proj=None, visible_ids=None)`

#### Module Functions

- `_final_color_for(element)`
  - Elementin son rengini döndür (RGB 3-tuple).

### `render.gl_utils`

Path: `render/gl_utils.py`

#### Module Functions

- `mat4_data(matrix: glm.mat4 -> np.ndarray)`

### `render.global_axis_renderer`

Path: `render/global_axis_renderer.py`

GlobalAxisRenderer — Tekla tarzı tıklanabilir global eksen.

Özellikler:
    - Sol alt köşede 3D eksen üçlüsü (X=kırmızı, Y=yeşil, Z=mavi)
    - Kameraya duyarlı (view rotation ile döner)
    - Tıklanabilir: X/Y/Z eksenine tıklayınca kamera o yönden bakar
    - Hover vurgusu: fare üstündeyken eksen parlar
    - Ayarlanabilir: renk, uzunluk, görünürlük, konum, etiket
    - 2D/3D projection desteği (2D'de ekrana dik eksen gizlenir)

Kullanım:
    axis = GlobalAxisRenderer(shader=axes_shader)
    axis.init_gl()

    # her frame:
    axis.begin_frame(camera, viewport_w, viewport_h, projection="3d")
    axis.render()   # çizer + hover güncelle

    # tıklama:
    hit = axis.pick(mouse_x, mouse_y)
    if hit:
        axis.apply_view(hit, camera)   # X/Y/Z → view preset

#### Classes

- **GlobalAxisSettings** (line 46)
  - Global eksen görsel ayarları.
- **GlobalAxisRenderer** (line 86)
  - Tekla tarzı global eksen HUD'u.
  - `__init__(self, shader, settings: GlobalAxisSettings | None=None)`
  - `init_gl(self -> bool)`
  - `_build_unit_axes(self -> np.ndarray)`
    - Origin'den +X, +Y, +Z yönlerine 3 eksen.
  - `_upload_geometry(self, data: np.ndarray -> None)`
  - `begin_frame(self, camera, viewport_w: int, viewport_h: int, projection: str='3d' -> None)`
    - Her frame başında çağrılır — hover ve hit box'ları temizler.
  - `update_hover(self, mouse_x: float, mouse_y: float -> str | None)`
    - Fare üzerinde hangi eksen var? Hit box'lar zaten güncel.
  - `render(self -> None)`
    - Eksenleri çizer.
  - `pick(self, mouse_x: float, mouse_y: float -> str | None)`
    - Fare pozisyonuna göre eksen seç.
  - `apply_view(self, axis: str, camera -> bool)`
    - X/Y/Z eksenine göre kamerayı hizala.
  - `hover_axis(self -> str | None)`
  - `set_visible(self, visible: bool -> None)`
  - `set_length(self, length: float -> None)`
  - `set_colors(self, x=None, y=None, z=None -> None)`
  - `set_position(self, position: str -> None)`
  - `_gizmo_origin_px(self -> tuple[int, int])`
    - Gizmo viewport'unun sol-alt köşesi (OpenGL piksel).
  - `_should_hide_axis(self, axis: str -> bool)`
    - 2D'de ekrana dik ekseni gizle.
  - `_alpha_for(self, axis: str -> float)`
  - `_update_hit_boxes(self -> None)`
    - Dünya uzayındaki eksen uçlarını ekran uzayına projekte et.
  - `_point_segment_dist(px: float, py: float, x0: float, y0: float, x1: float, y1: float -> float)`
    - Noktadan doğru parçasına mesafe (ekran uzayı).
  - `cleanup(self -> None)`
  - `_safe_cleanup(self -> None)`

### `render.grid_renderer`

Path: `render/grid_renderer.py`

#### Classes

- **_GLBuffer** (line 13)
  - `__init__(self)`
  - `upload(self, verts: list[float] -> int)`
  - `draw(self, mode, count, offset=0)`
  - `cleanup(self)`
- **GridRenderer** (line 71)
  - `__init__(self, shader)`
  - `set_grid(self, grid)`
  - `set_axes(self, axes)`
    - Proje seviyesinden gelen filtrelenmiş aksları doğrudan set eder.
  - `mark_dirty(self)`
  - `_get_axes(self)`
  - `draw(self, mvp)`
  - `_bind(self, mvp)`
  - `_rebuild(self)`
  - `_perp(d)`
  - `get_label_anchors(self)`
  - `_leader(self, a, d)`
  - `cleanup(self)`
- **BubbleRenderer** (line 192)
  - `__init__(self, shader)`
  - `begin(self)`
  - `add(self, anchor, direction, normal, text_width, color, leader_len=None)`
  - `_norm(v, fallback)`
  - `_outline(self, b)`
  - `flush(self, mvp)`
  - `cleanup(self)`

#### Module Functions

- `_line(out, a, b, color)`
- `_dash_dot(out, a, b, color)`

### `render.interactionrenderer`

Path: `render/interactionrenderer.py`

#### Classes

- **InteractionRenderer** (line 13)
  - Kullanıcı etkileşiminin anlık görselleri (Interaction Layer):
  - `__init__(self, overlay_shader)`
  - `render(self, engine, w, h, camera=None, viewport_name=None, mouse_pos=None)`
    - Tüm etkileşim ve anlık preview görsellerini çizer.
  - `_draw_element_outline(self, element, camera, w, h, color=(1, 1, 0, 1))`
    - Element'in kenar/vertex noktalarını vurgula.
  - `_draw_marquee(self, marquee, w, h)`
  - `_draw_snap(self, engine, w, h, camera, mouse_pos)`
  - `_draw_tool_snap(self, engine, snap, w, h, camera -> bool)`
  - `_draw_hover_snap(self, engine, snap, w, h, camera, mouse_pos -> bool)`
  - `_project(camera, x, y, z, w, h)`
  - `_ensure_dynamic_buffers(self)`
  - `_draw_plane_preview(self, plane, mvp)`
  - `_upload_and_draw(self, vao, vbo, verts, mode, count, color, loc_color)`
  - `cleanup(self)`

### `render.label_batch`

Path: `render/label_batch.py`

#### Classes

- **LabelBatch** (line 44)
  - `__init__(self, atlas)`
  - `init_gl(self)`
  - `_shader(self)`
  - `_buffers(self, quads: int)`
  - `_lut(self)`
  - `_grow(self, need_quads: int)`
  - `begin(self, view=None, proj=None, cam_pos=None, screen_h=None, fov_y_rad=None, mode='billboard', mvp=None)`
  - `add(self, world_pos, text, color=(1, 1, 1, 1), pixel_size=14.0, anchor='center', u_axis=None, v_axis=None, size_world=None, world_offset=None)`
  - `add_many(self, positions, texts, colors, pixel_sizes, anchors='center', max_distances=None, world_offsets=None, u_axis=None, v_axis=None, size_world=None)`
  - `_basis(self, world, ps, size_world, u_axis, v_axis, N)`
  - `_unit(v)`
  - `_anchor_k(self, anchors, N)`
  - `flush(self, disable_depth=False)`
  - `stats(self)`
  - `cleanup(self)`

### `render.light_ubo`

Path: `render/light_ubo.py`

#### Classes

- **LightUBO** (line 10)
  - `__init__(self)`
  - `update(self, lighting, camera_pos)`
  - `cleanup(self)`

### `render.lightingsystem`

Path: `render/lightingsystem.py`

### `render.line_renderer`

Path: `render/line_renderer.py`

#### Classes

- **LineRenderer** (BaseRenderer[Line]) (line 12)
  - `__init__(self, shader)`
  - `_line_verts(self, ln)`
  - `build(self, ln)`
  - `build_simple(self, ln)`
  - `draw_mode(self)`
  - `draw(self, mvp, visible_ids=None)`
    - Eski API uyumluluğu — MathModelRenderer kullanıyor.
  - `render_pick(self, mvp, pick_shader, visible_ids=None)`

### `render.load_renderer`

Path: `render/load_renderer.py`

#### Classes

- **LoadRenderer** (line 14)
  - `__init__(self)`
  - `init_gl(self)`
  - `_compile(self, vs_src, fs_src)`
  - `_pattern_color(self, name: str -> tuple[float, float, float])`
  - `update(self, scene, camera_scale: float=1.0, scene_size: float=1.0)`
  - `_scan_patterns(self, scene -> list[str])`
  - `_emit_load_set(self, frame, ls, lines, tris, cam_scale)`
  - `_attr(obj, key)`
  - `_emit_profile(self, frame, pts, color, lines, tris, cam_scale, load=None)`
  - `_interp(pts, xr)`
  - `_push_line(out, a, b, color)`
  - `_push_tri(out, a, b, c, color)`
  - `render(self, mvp)`
  - `cleanup(self)`
  - `_frame_local_axes(p0, p1, rotation_deg=0.0)`
  - `_resolve_load_direction(load, e1, e2, e3)`
  - `_emit_point_load(self, node, pl, lines, tris)`
  - `_emit_polygon_load(self, polygon, load, lines, tris, arrow_len)`
  - `_emit_area_load(self, area, load, lines, tris, arrow_len)`
  - `_emit_wind_zones(self, polygon, lines, tris, arrow_len)`
  - `_emit_distributed_patch(self, nodes, direction, length, color, lines, tris)`
  - `_resolve_area_direction(self, load, element)`
  - `_calculate_normal(nodes)`
  - `_emit_arrow_3d(self, origin, direction, length, color, lines, tris)`
  - `_perp_vector(d)`

### `render.mathmodelrenderer`

Path: `render/mathmodelrenderer.py`

#### Classes

- **RenderStats** (line 28)
- **MathModelRenderer** (line 35)
  - `__init__(self, pick_s, standard_s, node_s, simple_s, overlay_s, axes_s, w=1024, h=768, create_pick_pass=True)`
  - `set_cam(self, c)`
  - `set_grid(self, g)`
  - `set_math_model(self, math_model)`
  - `set_snap(self, s)`
  - `set_lighting(self, lighting)`
  - `set_node_point_size(self, px: float)`
  - `set_node_size(self, size: float, rebuild: bool=True)`
  - `set_engine(self, e)`
  - `resize(self, w, h)`
  - `update_geo(self, scene=None, progress_cb=None, *, frames=None, nodes=None, areas=None, links=None, polygons=None, lines=None)`
  - `update_element_color(self, element)`
  - `update_sel(self)`
  - `_get_final_color(self, element)`
  - `toggle_render_mode(self)`
  - `_apply_clip_uniforms(self, shader, plane)`
    - CLIP mode aktifse shader'a plane uniform'larını yazar.
  - `render(self, cam, target_fbo=0, force_id_pass=False, plane=None, visible_ids=None)`
  - `_render_shaded(self, mvp, cpos, v, p, visible_ids=None)`
  - `_render_simple(self, mvp, visible_ids=None)`
  - `_render_polygon_lines(self, mvp, visible_ids=None)`
  - `_render_id_pass(self, mvp, visible_ids=None)`
  - `get_bounds(self)`
  - `pick_async(self, x, y)`
  - `check_pick(self)`
  - `get_element_from_id(self, pick_id)`
  - `update_dirty(self)`
  - `_update_bounds(self)`
  - `cleanup(self)`
  - `set_render_mode(self, mode: str)`
  - `get_render_mode(self -> str)`
  - `set_assoc_preview(self, preview)`
    - Polygon assoc draft'ını renk katmanı olarak uygular.
  - `set_show(self, key: str, value: bool)`
  - `get_show(self -> dict)`
  - `set_use_lights(self, enabled: bool)`
  - `_element_in_section(self, el, camera=None, plane=None)`
  - `set_restraint_size(self, size: float -> bool)`
  - `_element_points(el)`

### `render.node_renderer`

Path: `render/node_renderer.py`

#### Classes

- **NodeRenderer** (BaseRenderer[Node]) (line 18)
  - `__init__(self, shader)`
  - `set_node_size(self, size: float -> bool)`
    - Shaded mesh boyutu (dünya birimi → ekran oranı). True → değişti.
  - `set_point_size(self, px: float -> bool)`
    - Simple modda piksel boyutu. True → değişti.
  - `build(self, n: Node)`
  - `build_simple(self, n: Node)`
  - `draw_mode(self -> int)`
  - `render(self, mvp, model=None, cam_pos=None, view=None, proj=None, visible_ids=None)`
  - `render_simple(self, mvp, shader, color=None, alpha=0.5, point_size=None, visible_ids=None)`
  - `update(self, raw)`
  - `_build_restraint_lines(self)`
    - Restraint'li node'lar için simple çizgiler üret.
  - `_upload_rlines(self, v, c, ids)`
  - `_cleanup_rlines(self)`
  - `render_simple_restraint_lines(self, mvp, shader, alpha=1.0)`
    - GL_LINES ile restraint sembolleri çiz.
  - `cleanup(self)`

### `render.offscreen_fbo`

Path: `render/offscreen_fbo.py`

ImGui pencerelerinde gösterilebilir bağımsız render target.

#### Classes

- **OffscreenFBO** (line 9)
  - Renk (+ opsiyonel ID) + depth render target. Texture olarak okunabilir.
  - `__init__(self, width: int=640, height: int=480, with_id: bool=False)`
  - `_create(self)`
  - `bind(self)`
  - `unbind()`
  - `clear(self, color=(0.1, 0.1, 0.12, 1.0))`
  - `resize(self, w: int, h: int)`
  - `texture_id(self -> int)`
  - `cleanup(self)`

### `render.orbit_camera`

Path: `render/orbit_camera.py`

#### Classes

- **OrbitCamera** (line 8)
  - Basit orbit kamera. Bir hedef noktası etrafında döner.
  - `__init__(self)`
  - `set_target(self, p)`
  - `get_position(self -> np.ndarray)`
  - `get_view_matrix(self)`
  - `get_projection_matrix(self)`
  - `render_info(self)`
    - MathModelRenderer._render_shaded için (cpos, v, p).

### `render.pickpass`

Path: `render/pickpass.py`

#### Classes

- **PickPass** (line 13)
  - `__init__(self)`
  - `_create_resources(self)`
  - `set_main_fbo(self, fbo)`
  - `register(self, pick_id, element, renderer)`
  - `unregister(self, pick_id)`
  - `clear_registry(self)`
  - `get_element(self, pick_id)`
  - `get_renderer(self, pick_id)`
  - `set_viewport(self, width, height)`
  - `_fbo_has_color_attachment1(self, fbo -> bool)`
  - `_drain_gl_errors(tag: str -> int)`
    - Bekleyen GL hatalarını tüket; son hatayı döndür.
  - `pick_async(self, x, y, source_fbo=None, viewport_size=None -> bool)`
  - `check_pick(self)`
  - `pick_rect(self, x0, y0, x1, y1, fbo, viewport_size -> list[int])`
    - Verilen viewport FBO'sundan dikdörtgen bölgedeki benzersiz ID'leri okur.
  - `cleanup(self)`

### `render.polygonrenderer`

Path: `render/polygonrenderer.py`

#### Classes

- **PolygonRenderer** (BaseRenderer[Polygon]) (line 13)
  - `__init__(self, shader)`
  - `build(self, p)`
  - `build_lines(self, p)`
  - `build_simple(self, p)`
  - `draw_mode(self)`
  - `render_pick(self, mvp, pick_shader, visible_ids=None)`

### `render.presentation_renderer`

Path: `render/presentation_renderer.py`

#### Classes

- **PresentationRenderer** (line 21)
  - `__init__(self, standard_shader, axes_shader, overlay_shader, simple_shader, grid_shader, math_model_renderer=None)`
  - `polygon(self)`
  - `lines(self)`
  - `pick_pass(self)`
  - `load_renderer(self)`
  - `set_engine(self, engine)`
  - `set_loads_enabled(self, enabled)`
  - `set_load_scale(self, scale)`
  - `set_projection(self, projection)`
  - `_compute_cam_scale(self)`
  - `set_scene_data(self, scene, polygons=None, lines=None, grid_axes=None)`
  - `render_scene_visuals(self, camera, model, scene, math_model, width, height, show, active_wind_vector=None)`
  - `update_polygons(self, polygons)`
  - `update_loads(self, math_model, camera_scale=1.0, scene_size=1.0, unit_system=None, wind_results=None)`
  - `_bind_grid(self, scene)`
  - `refresh_zones(self, polygons)`
  - `_update_zones(self, polygons)`
  - `_zone_scalar(self, zone)`
  - `_zone_color(self, zone, cpe_lo, cpe_hi)`
  - `_upload_zone_verts(self, verts)`
  - `_upload_zone_outline(self, verts)`
  - `_cleanup_zone_verts(self)`
  - `_cleanup_zone_outline(self)`
  - `_draw_zones(self, mvp, scene=None, math_model=None, wind_vector=None)`
  - `_draw_global_axis(self, cam, w, h)`
  - `_draw_local_axes(self, cam, scene, math_model)`
  - `_draw_labels(self, cam, scene, math_model, screen_h)`
  - `_grid_labels(self, cam)`
  - `_frame_labels(self, cam, math_model, screen_h)`
  - `_draw_wind_vector(self, mvp, vec, scene, math_model=None)`
  - `_ascii_safe(text: str -> str)`
    - LabelBatch LUT sadece ASCII — Unicode'ları ASCII'ye çevir.
  - `cleanup(self)`

### `render.scenerenderer`

Path: `render/scenerenderer.py`

#### Classes

- **SceneRenderer** (line 9)
  - `__init__(self, standard_shader, axes_shader, overlay_shader, simple_shader, grid_shader, math_model_renderer=None)`
  - `__getattr__(self, name)`
  - `pick_pass(self)`
  - `set_engine(self, engine)`
  - `set_cam(self, camera)`
  - `set_snap(self, snap)`
  - `resize(self, width, height)`
  - `update_geo(self, math_model, scene=None, progress_cb=None, polygons=None, lines=None, grid_axes=None, frames=None, nodes=None, areas=None, links=None)`
  - `set_scene_data(self, scene, polygons=None, lines=None, grid_axes=None)`
  - `render(self, camera, target_fbo=0, force_id_pass=False, viewport_name=None, plane=None, visible_ids=None)`
  - `render_scene_visuals(self, *args, **kwargs)`
  - `render_math_model(self, camera, target_fbo=0)`
  - `update_sel(self)`
  - `update_dirty(self)`
  - `remove_viewport(self, viewport_name)`
  - `cleanup(self)`

### `render.shaderprogram`

Path: `render/shaderprogram.py`

#### Classes

- **ShaderProgram** (line 11)
  - `__init__(self, name, vertex_path, fragment_path)`
  - `_read_file(self, path)`
  - `_compile(self, source, shader_type)`
  - `_create_program(self, vert_path, frag_path)`
  - `_compile_shader(self, source, shader_type)`
  - `use(self)`
  - `set_int(self, name: str, value: int)`
  - `get_uniform_location(self, name: str -> int)`
    - Uniform lokasyonunu cache'leyerek döndür
  - `get_loc(self, name: str -> int)`
  - `set_float(self, name: str, value: float)`
  - `set_vec3(self, name: str, x: float, y: float, z: float)`
  - `set_vec3_list(self, name: str, values)`
  - `set_mat3(self, name: str, mat)`
    - 3x3 matris gönder (normalMatrix için)
  - `set_mat4(self, name: str, matrix)`
  - `set_int_array(self, name: str, values, count: int)`
  - `set_float_array(self, name: str, values, count: int)`
  - `set_vec3_array(self, name: str, values, count: int)`
    - Vec3 array gönder
  - `cleanup(self)`

### `render.snapsquare`

Path: `render/snapsquare.py`

#### Classes

- **SnapSquareRenderer** (line 15)
  - `__init__(self)`
  - `_init_shader(self)`
  - `find_snap(self, engine, x, y, magnetic=False, cam=None, viewport_size=None)`
  - `_find_node(self, engine, x, y, cam=None, viewport_size=None)`
  - `_project_pt_with_size(self, cam, mvp, x, y, z, w, h)`
    - Kamera ve viewport özel boyutlarına göre 3D noktayı 2D ekran pikseline projeksiyon yapar.
  - `_find_frame(self, engine, x, y)`
  - `_find_grid_snap(self, engine, x, y, cam=None, viewport_size=None)`
  - `_project_pt(self, engine, mvp, x, y, z)`
  - `_vertex_from_node(node -> Vertex)`
  - `draw_snap(self, mouse_x, mouse_y, w, h, active=True, snap_type='default')`
  - `_find_polygon(self, engine, x, y)`
  - `_dist_to_segment(p, a, b)`
  - `cleanup(self)`
  - `draw_at_world_pos(self, engine, x, y, z, w, h, snap_type='default', active=True)`

### `structload`

Path: `structload/__init__.py`

Structload — yapısal yük analiz kütüphanesi.

Alt modüller:
- loads/      → kar, deprem yük hesabı
- windcalc/   → rüzgar yük hesabı (TS EN 1991-1-4)
- data/       → malzeme, default veriler
- gui/        → Kivy rapor görünümü
- utils/      → yardımcılar (meta tablolar, ReportDataFrame)

### `structload.analysis`

Path: `structload/analysis/__init__.py`

### `structload.analysis.analysis_runner`

Path: `structload/analysis/analysis_runner.py`

Analiz Modülleri Sarmalayıcı

#### Classes

- **AnalysisResult** (line 15)
  - Analiz çıktısını GUI'ye taşımak için basit taşıyıcı.
  - `__init__(self, key: str, title: str, report: Any=None, error: str | None=None, extra: dict | None=None)`
  - `success(self -> bool)`
  - `as_text(self -> str)`

#### Module Functions

- `run_wind(config: dict, data: dict -> AnalysisResult)`
- `run_snow(config: dict, data: dict -> AnalysisResult)`
- `run_earthquake(config: dict, data: dict -> AnalysisResult)`
- `show_spectrum_plot(earthquake_analysis -> dict)`
  - Spektrum grafiğini oluşturur ve gösterir.

### `structload.data`

Path: `structload/data/__init__.py`

### `structload.data.defaults`

Path: `structload/data/defaults.py`

### `structload.data.material_data`

Path: `structload/data/material_data.py`

Yük ve Malzeme Veritabanı (TS 498 / TS EN 1991-1-1 Uyumlu)

Birim Standartları:
- Volumetric : kN/m³ (Kalınlık 'm' ile çarpılarak alansal yüke çevrilir)
- Area       : kN/m² (Doğrudan alansal yük olarak eklenir)
- Live Loads : kN/m² (Doğrudan yönetmelik standart değerleri)

#### Module Functions

- `get_material_info(key: str -> dict)`
- `get_live_load_info(key: str -> dict)`

### `structload.data.mechanical`

Path: `structload/data/mechanical.py`

#### Classes

- **woodMaterial** (line 79)
  - `__init__(self, malzeme)`
- **osbMaterial** (line 89)
  - `__init__(self, malzeme, thickness_mm, direction='major')`
- **concreteMaterial** (line 113)
  - `__init__(self, malzeme)`
- **steelMaterial** (line 123)
  - `__init__(self, malzeme, thickness_mm=16)`

### `structload.data.preset_loader`

Path: `structload/data/preset_loader.py`

Hazır Yük Kütüphanesi Yükleyici

- Düz yükler (G / Q): LoadDefinition'a çevrilir.
- Kiriş/duvar senaryoları: WallLoadEngine ile hesaplanır,
  sonuç bir LoadDefinition olarak döner (value = kN/m).

#### Classes

- **PresetLibrary** (line 19)
  - `__init__(self, json_path: str | None=None)`
  - `_yukle(self)`
  - `kgf_to_kn(kgf: float, rounding: int=2 -> float)`
  - `kategori_listesi(self -> list[tuple[str, str, str]])`
  - `kategori_yukleri(self, kategori_id: str -> list[dict])`
  - `_kiriş_senaryolari(self, kategori_id: str -> list[dict])`
    - Kiriş senaryolarını WallLoadEngine ile hesaplar ve
  - `load_definition_olustur(self, kategori_id: str, item_index: int, load_id: str, load_type: str | None=None, source_ek: str='Hazır Kütüphane' -> LoadDefinition)`

### `structload.data.project_schema`

Path: `structload/data/project_schema.py`

**Parse error:** expected an indented block after 'except' statement on line 231 (project_schema.py, line 234)

### `structload.data.snow_data`

Path: `structload/data/snow_data.py`

Kar Yükü Verileri - TS EN 1991-1-3

### `structload.data.wind_data`

Path: `structload/data/wind_data.py`

#### Classes

- **SurfaceType** (Enum) (line 203)
- **WindRelation** (Enum) (line 208)
- **RoofType** (Enum) (line 221)

### `structload.gui`

Path: `structload/gui/__init__.py`

### `structload.gui.analysis_panels`

Path: `structload/gui/analysis_panels.py`

Analiz Sekmeleri İçin GUI Panelleri

- AnalysisDataPanel : Wind / Snow / Earthquake config formu
- ResultPanel       : Analiz sonuç metni

#### Classes

- **AnalysisDataPanel** (BoxLayout) (line 24)
  - Analiz config formu.
  - `__init__(self, title='', panel_key='', data=None, show_spectrum_button=False, **kwargs)`
  - `set_extra_enabled(self, enabled: bool)`
    - Rüzgâr için points/polygons uygunluğunu gösterir (görsel ipucu).
  - `_build(self)`
  - `_create_row(self, key, value)`
  - `_edit_complex(self, key)`
    - dict/list alanını popup içinde düzenlet.
  - `_convert(self, key, widget)`
  - `get_data(self -> dict)`
  - `set_data(self, data: dict)`
  - `reset(self, *args)`
  - `_calculate(self, *args)`
  - `_on_spectrum(self, *args)`
  - `set_spectrum_enabled(self, enabled: bool)`
  - `_popup(self, title, msg)`
- **ResultPanel** (BoxLayout) (line 306)
  - Alt kısımda analiz sonuç metni.
  - `__init__(self, **kwargs)`
  - `set_text(self, value: str)`

### `structload.gui.debug_panel`

Path: `structload/gui/debug_panel.py`

Debug/Log paneli.
StatusManager'daki log kayıtlarını renkli olarak gösterir.

#### Classes

- **DebugPanel** (BoxLayout) (line 24)
  - Log görüntüleme paneli.
  - `__init__(self, **kwargs)`
  - `yenile(self)`
  - `temizle(self, instance)`

### `structload.gui.file_dialog`

Path: `structload/gui/file_dialog.py`

JSON Dosya Aç / Kaydet Diyaloğu (Kivy)

Kullanım:
    dialog = FileDialog(mode="open", callback=func)
    popup  = Popup(title="...", content=dialog, size_hint=(0.95, 0.9))
    dialog.popup = popup
    popup.open()

#### Classes

- **FileDialog** (BoxLayout) (line 26)
  - mode = "open"  → mevcut JSON dosyasını seçer, callback(config_dict) çağırır.
  - `__init__(self, callback, mode='open', path=None, default_name='config.json', **kwargs)`
  - `_on_action(self, *args)`
  - `_open_file(self)`
  - `_save_file(self)`
  - `close(self, *args)`
  - `_msg(self, title, msg)`

### `structload.gui.hazir_yuk_karti`

Path: `structload/gui/hazir_yuk_karti.py`

Hazır yük detay kartı.
Sol taraftaki kütüphaneden seçilen yükü form halinde gösterir,
düzenlenebilir ve LoadManager'a kaydedilebilir.

#### Classes

- **KartBilesenSatiri** (BoxLayout) (line 77)
  - Kart içinde bir bileşen satırı: ad, malzeme, kalınlık, canlı değer.
  - `__init__(self, index: int, comp: dict, on_change=None, **kwargs)`
  - `tip_degisti(self, spinner, text)`
  - `_degisti(self, *args)`
  - `_guncelle_deger(self)`
  - `_kaldir(self, instance)`
  - `deger(self -> float)`
  - `load_component(self -> LoadComponent | None)`
- **HazirYukDetayKarti** (BoxLayout) (line 249)
  - Seçilen hazır yükü form halinde gösterir.
  - `__init__(self, **kwargs)`
  - `_update_bg(self, *args)`
  - `_bilesen_ekle(self, instance, comp: dict=None)`
  - `_yeniden_numaralandir(self)`
  - `_toplam_guncelle(self)`
  - `yuk_yukle(self, definition: LoadDefinition, kategori_id: str=None)`
    - LoadDefinition'ı kartta göster.
  - `_sil(self, instance)`
  - `_guncelle(self, instance)`
    - Formdaki bilgileri LoadManager'a yaz.
  - `temizle(self)`
  - `_get_app(self)`

#### Module Functions

- `_baslik_seridi(text, bg=(0.2, 0.35, 0.55, 1))`
  - Mavi zeminli başlık şeridi.
- `_etiketli_satir(etiket, widget, etiket_w=0.22)`

### `structload.gui.panels`

Path: `structload/gui/panels.py`

**Parse error:** expected an indented block after 'for' statement on line 1935 (panels.py, line 1944)

### `structload.gui.report_panel`

Path: `structload/gui/report_panel.py`

**Parse error:** expected an indented block after 'for' statement on line 366 (report_panel.py, line 369)

### `structload.gui.report_view`

Path: `structload/gui/report_view.py`

#### Classes

- **CardContainer** (BoxLayout) (line 43)
  - Yuvarlatılmış arka plana sahip kart kutusu.
  - `__init__(self, bg_color=THEME['bg_card'], radius=10, padding_dp=12, spacing_dp=10, **kwargs)`
  - `_update_rect(self, instance, value)`
- **AutoLabel** (Label) (line 67)
  - Metni genişliğe göre kıran dinamik Label.
  - `__init__(self, font_sp=FONT['body'], font_name=FONT['family'], is_bold=False, text_color=THEME['text_main'], **kwargs)`
  - `_update_text_size(self, instance, width)`
  - `_update_height(self, instance, texture_size)`
- **ReportView** (CardContainer) (line 97)
  - Her türlü veriyi (ReportDataFrame, Dict, List, Görsel, String) 
  - `__init__(self, data, **kwargs)`
  - `_render_data(self, data)`
    - Verinin tipini tespit edip uygun render metodunu çağırır.
  - `_render_report_dataframe(self, report)`
    - ReportDataFrame'i başlık, açıklama, tablo ve görselleriyle basar.
  - `_load_kivy_image(self, raw_graphic)`
  - `_measure_text(self, text, font_name, font_size, bold=False -> float)`
    - Metnin piksel genişliğini ölçer (tek satır).
  - `_measure_text_height(self, font_name, font_size, bold=False, lines=1 -> float)`
    - Bir metnin `lines` satırda kapladığı yüksekliği tahmin eder.
  - `_count_wrapped_lines(self, text, font_name, font_size, bold=False, max_width=100 -> int)`
    - Metnin `max_width` pikselde kaç satıra kırılacağını tahmin eder.
  - `_cell(text, bold=False, bg_color=THEME['tbl_row_even'], text_color=THEME['text_main'], font_sp=FONT['table'], col_width=dp(140))`

### `structload.gui.status_bar`

Path: `structload/gui/status_bar.py`

Alt durum çubuğu widget'ı.
StatusManager'a bağlı olarak renk ve mesaj günceller.

#### Classes

- **StatusBar** (BoxLayout) (line 24)
  - Alt durum çubuğu.
  - `__init__(self, on_log_button=None, **kwargs)`
  - `_update_bg(self, *args)`
  - `_on_message(self, instance, value)`
  - `_on_level(self, instance, value)`

### `structload.loads`

Path: `structload/loads/__init__.py`

### `structload.loads.load_definition`

Path: `structload/loads/load_definition.py`

#### Classes

- **LoadComponent** (line 8)
  - Bir G yükünün bileşeni.
  - `calculate(self, material_weights: dict[str, float] -> float)`
- **LoadDefinition** (line 51)
  - Projede kullanılabilecek G veya Q yük tanımı.
  - `calculate(self, material_weights -> float)`
  - `as_dict(self, material_weights: dict[str, float] | None=None -> dict[str, Any])`

### `structload.loads.load_manager`

Path: `structload/loads/load_manager.py`

#### Classes

- **LoadManager** (line 7)
  - Projedeki G/Q yük tanımlarını ve eleman atamalarını yönetir.
  - `__init__(self, material_weights: dict[str, float] | None=None)`
  - `add_definition(self, definition: LoadDefinition)`
  - `get_definition(self, load_id: str -> LoadDefinition)`
  - `get_value(self, load_id: str -> float)`
  - `assign(self, unique_id: int | str, load_id: str)`
  - `remove(self, unique_id: int | str, load_id: str)`
  - `clear_element(self, unique_id: int | str, load_type: str | None=None)`
  - `get_element_loads(self, unique_id: int | str -> dict[str, list[LoadDefinition]])`
  - `get_element_total(self, unique_id: int | str, load_type: str -> float)`
  - `used_definitions(self, load_type: str | None=None -> list[LoadDefinition])`
  - `definition_rows(self, load_type: str | None=None -> list[dict])`
  - `assignment_rows(self -> list[dict])`

### `structload.loads.snow_load`

Path: `structload/loads/snow_load.py`

Kar Yükü Motoru - TS EN 1991-1-3

#### Classes

- **SnowLoad** (line 14)
  - Kar Yükü Hesaplama Sınıfı
  - `__init__(self, config: dict[str, Any])`
    - Args:
  - `_calculate(self)`
    - Tüm kar yükü hesaplamalarını yapar
  - `_calculate_sk(self -> float)`
    - Karakteristik kar yükünü hesaplar
  - `_interpolate_sk(self, altitude: float -> float)`
    - Rakıma göre interpolasyon
  - `report(self -> ReportDataFrame)`
    - Kar yükü raporu
  - `get_load_patterns(self -> dict[str, float])`
    - SAP2000 yük kalıbı

### `structload.loads.spectrum`

Path: `structload/loads/spectrum.py`

TBDY 2018 Deprem Spektrumu Hesaplamaları

#### Classes

- **Spectrum** (line 13)
  - `__init__(self, data)`
  - `_calculate_period_params(self)`
  - `sae(T: float, SDS: float, SD1: float, TA: float, TB: float, TL: float=6.0 -> float)`
  - `run(self, T1: float=0 -> None)`
  - `calculate_tpA(self)`
  - `_create_spectrum(self -> None)`
  - `_calculate_lambda(self)`
  - `_create_tables(self -> None)`
  - `spectrum_plot(self, save: bool=False, filename: str='deprem_spektrumlari.png')`

### `structload.loads.wall_load_engine`

Path: `structload/loads/wall_load_engine.py`

Duvar / Kiriş Çizgisel Yük Hesap Motoru

Bir duvarın katmanlarını (sıva, beden, kaplama, yalıtım, cephe) toplayıp
kirişe etkiyen çizgisel yükü (kN/m) hesaplar.

MATERIAL_LIBRARY birimlerini dikkate alır:
- 'volumetric' → kalınlıkla çarpılır
- 'area'       → doğrudan eklenir

#### Classes

- **WallLoadEngine** (line 16)
  - `__init__(self, wall_name: str, wall_height_m: float=2.8, beam_depth_m: float=0.5)`
  - `add_layer(self, mat_key: str, thickness_m: float=0.0, custom_label: str=None)`
  - `total_area_load(self -> float)`
  - `line_load_kn_m(self -> float)`
  - `print_report(self)`

### `structload.main`

Path: `structload/main.py`

#### Classes

- **SectionHeader** (CardContainer) (line 21)
  - `__init__(self, title_text, icon_str='■', **kwargs)`
- **StructuralAnalysisApp** (App) (line 34)
  - `build(self)`

### `structload.utils`

Path: `structload/utils/__init__.py`

### `structload.utils.math_utils`

Path: `structload/utils/math_utils.py`

Ortak Matematik ve Mühendislik Araçları

#### Module Functions

- `interpolate_value(value: float, data: Mapping -> Any)`
  - Verilen sözlük veya Mapping nesnesinde lineer interpolasyon yapar.
- `interpolate_2d(x: float, xp: list[float], yp: list[float] -> float)`
  - 2D lineer interpolasyon.
- `calculate_wind_velocity_pressure(v_b0: float, rho: float=1.25 -> float)`
  - Temel rüzgar hızı basıncını hesaplar.
- `calculate_roughness_coefficient(z0: float, z: float, zmin: float -> tuple[float, float])`
  - Pürüzlülük katsayısını hesaplar.
- `calculate_exposure_coefficient(cr: float, ct: float -> float)`
  - Maruziyet katsayısını hesaplar.
- `calculate_turbulence_intensity(z0: float, z: float, zmin: float, kI: float=1.0 -> float)`
  - Türbülans şiddetini hesaplar.
- `calculate_snow_shape_coefficient(alpha: float -> float)`
  - Kar şekil katsayısını hesaplar (beşik çatı).
- `round_values(data: dict[str, Any], decimals: int=3 -> dict[str, Any])`
  - Dictionary'deki tüm sayısal değerleri yuvarlar.

### `structload.utils.meta_tables`

Path: `structload/utils/meta_tables.py`

#### Module Functions

- `katman_yuku(layer: dict -> tuple[float, str, float | None])`
  - Bir katmanın alansal yükünü ve meta bilgisini döner.
- `katman_raporu_df(layers: list[dict], title: str, desc: str='' -> ReportDataFrame)`
  - Katman listesini tek ReportDataFrame'e çevirir.
- `duvar_alansal_yuk(layers: list[dict] -> float)`
  - Duvar katmanlarının toplam alansal yükü (kN/m²).
- `calculate_wall_line_load(layers: list[dict], wall_height_m: float, beam_depth_m: float=0.0, opening_ratio: float=0.0 -> dict)`
  - Kiriş üstü duvar çizgi yükü (kN/m).
- `duvar_cizgi_yuk_raporu(layers: list[dict], wall_height_m: float, beam_depth_m: float=0.0, opening_ratio: float=0.0, title: str='Kiriş Üstü Duvar Çizgi Yükü', desc: str='' -> ReportDataFrame)`
  - 3 bölümlü duvar çizgi yükü raporu.
- `parse_project_loads(proje_data: dict -> dict[str, ReportDataFrame])`
  - proje_data'dan tüm rapor tablolarını üretir.
- `calculate_wall_line_load_safe(layers, h, hk, op -> dict)`
  - Validasyon hatası olursa boş dict döner.
- `_guze_etiket(k: str -> str)`
  - snake_case → 'Snake Case' (başlık için).
- `tablo_proje_bilgileri(pdata: dict -> ReportDataFrame)`
- `tablo_yonetmelikler( -> ReportDataFrame)`
- `tablo_saha_ve_deprem(pdata: dict -> ReportDataFrame)`
- `tablo_malzeme_siniflari(pdata: dict -> ReportDataFrame)`
- `tablo_ahsap_mekanik(pdata: dict -> ReportDataFrame)`
  - woodMaterial(config) → param ve units sözlüklerini tabloya çevirir.
- `create_meta_tables(pdata: dict -> list)`
  - Meta tablolar + tüm yük detayları (ölü, hareketli, duvar).

### `structload.utils.my_document`

Path: `structload/utils/my_document.py`

#### Classes

- **MyDocument** (line 8)
  - `__init__(self, filename: str | None=None)`
  - `apply_visual_settings(self, top_margin: float=2.0, bottom_margin: float=2.0, left_margin: float=2.0, right_margin: float=1.0, font_name: str='Calibri', font_size: int=11 -> None)`
  - `add_heading_numbered(self, text: str, level: int=1 -> Any)`
  - `add_paragraph(self, text: str, style: str | None=None -> Any)`
  - `add_page_break(self -> None)`
  - `add_table(self, data: list[list[Any]], headers: list[str], title: str | None=None -> None)`
  - `add_image(self, image_source: Any, width_cm: float=15.0 -> None)`
    - image_source: Dosya yolu (str) veya BytesIO nesnesi olabilir.
  - `save_report(self, path: str -> bool)`
  - `add_section_break(self -> None)`
  - `clear(self -> None)`

### `structload.utils.report_dataframe`

Path: `structload/utils/report_dataframe.py`

#### Classes

- **ReportDataFrame** (pd.DataFrame) (line 9)
  - `__init__(self, *args, **kwargs)`
  - `_constructor(self)`
  - `set_column_description(self, column: str, description: str -> ReportDataFrame)`
  - `set_column_unit(self, column: str, unit: str -> ReportDataFrame)`
  - `set_column_format(self, column: str, fmt: str -> ReportDataFrame)`
  - `add_graphic(self, data: BytesIO | bytes | None=None, image: BytesIO | bytes | None=None, title: str | None=None, description: str | None=None, width: float | None=None, height: float | None=None, format: str='png' -> ReportDataFrame)`
  - `clear_graphics(self -> ReportDataFrame)`
  - `_format_value(self, column: str, value: Any -> str)`
  - `_format_row(self, row: pd.Series -> list[str])`
  - `round_numeric(self, decimals: int=2 -> ReportDataFrame)`
  - `_repr_html_(self -> str)`
  - `save_to_docx(self, document, title: str | None=None, desc: str | None=None, level: int=2 -> None)`
  - `print(self -> None)`

### `structload.utils.status_manager`

Path: `structload/utils/status_manager.py`

Global durum çubuğu ve log yöneticisi.
Tüm paneller bu singleton üzerinden mesaj gönderebilir.

#### Classes

- **StatusManager** (EventDispatcher) (line 13)
  - Global durum ve log yöneticisi.
  - `__new__(cls)`
  - `set(self, message: str, level: str='info', log: bool=True)`
    - Durum mesajını günceller ve isteğe bağlı loglar.
  - `add_log(self, message: str, level: str='info')`
    - Log kaydı ekler.
  - `info(self, msg)`
  - `success(self, msg)`
  - `warning(self, msg)`
  - `error(self, msg)`
  - `debug(self, msg)`
  - `clear_log(self)`

### `structload.windcalc`

Path: `structload/windcalc/__init__.py`

### `structload.windcalc.analysis`

Path: `structload/windcalc/analysis.py`

**Parse error:** unmatched ')' (analysis.py, line 223)

### `structload.windcalc.edge`

Path: `structload/windcalc/edge.py`

#### Classes

- **Edge** (line 10)
  - Saf geometrik kenar verisi. Rüzgar analizi EdgeAnalyzer tarafından yapılır.
  - `is_shared(self -> bool)`
    - Kenarın başka bir yüzeyle tam olarak çakışıp çakışmadığını döndürür.
  - `from_points(cls, i: int, plane -> 'Edge')`
  - `same_axis_2d(self, other: 'Edge', angle_tol: float=2.0, distance_tol: float=1e-06 -> bool)`
  - `is_same_edge(self, other: 'Edge', tol: float=1e-06 -> bool)`
    - 3D düzlemde veya 2D düzlemde kenarların birebir aynı olup olmadığını kontrol eder.
  - `reset_analysis(self -> None)`
    - Rüzgar analizine bağlı alanları sıfırla.

### `structload.windcalc.geometry_utils`

Path: `structload/windcalc/geometry_utils.py`

#### Module Functions

- `close_polygon(polygon: np.ndarray, tol: float=1e-08 -> np.ndarray)`
  - Poligonu kapatır
- `polygon_centroid(polygon: np.ndarray -> np.ndarray)`
  - Poligonun merkezini hesaplar
- `_make_local_sys(poly_coords, tol=1e-09)`
  - Düzlemsel 3D bir poligon için sağ elli yerel koordinat sistemi oluşturur.
- `_project_3d_to_local_2d(poly_coords, local_sys)`
- `_unproject_local_2d_to_3d(pts_2d, local_sys)`
- `_close_polygon(polygon: np.ndarray, tol: float=TOL -> np.ndarray)`
  - Poligonu kapatır (ilk nokta == son nokta).
- `_open_polygon(polygon: np.ndarray, tol: float=TOL -> np.ndarray)`
  - Kapalı poligondan tekrar eden son noktayı kaldırır.
- `_area2(poly: np.ndarray -> float)`
  - İki katlı işaretli alan (shoelace).
- `_clean_vertices(pts: np.ndarray, tol: float=EPS -> np.ndarray)`
  - Ardışık mükerrer noktaları ve kapanış tekrarını temizler.
- `_split_by_line_2d(pts_2d, p1, p2, tol: float=EPS)`
  - Poligonu p1->p2 doğrusu boyunca ikiye böler (Sutherland-Hodgman).
- `_clip_line_to_polygon_2d(line_p1, line_p2, polygon)`
  - Sonsuz 2D çizginin poligon sınırıyla iki kesişimini döner.
- `_valid_polygon(poly -> bool)`
- `_offset_edge_2d(polygon_2d, p1_2d, p2_2d, w_vector_2d, d_L)`
  - Kenarı w yönünde offsetler ve poligona kırpar.
- `_create_edge_perp_2d(polygon_2d, p1_2d, p2_2d, w_vector_2d, d_L)`
  - Kenara dik iki yardımcı çizgi üretir.
- `_normalize_wind(wind_vector: np.ndarray | None -> np.ndarray | None)`
- `dict_tree(data, indent='')`

### `structload.windcalc.report`

Path: `structload/windcalc/report.py`

#### Module Functions

- `show_zones(zones, building, size=800)`
- `get_parameters_report(building -> ReportDataFrame)`
- `_first(v)`
- `_second(v)`
- `_iter_zones(results)`
- `_as_3d(vec -> np.ndarray)`
- `create_cpe_summary_df(zones, engine -> ReportDataFrame)`
- `create_wind_force_df(zones, engine -> ReportDataFrame)`

### `structload.windcalc.surface`

Path: `structload/windcalc/surface.py`

#### Classes

- **Surface** (line 17)
  - `__init__(self, polygon: list | np.ndarray, name: str='Test', tol: float=1e-06)`
    - 3B Düzlemsel Poligon Nesnesi
  - `_compute_normal(self -> tuple[np.ndarray, np.ndarray])`
  - `_compute_angle(self -> float)`
  - `_compute_pitch(self -> float)`
  - `properties(self -> dict)`
    - UI / raporlama için özet sözlük.
  - `_get_best_projection_plane(self)`
  - `polygon_direction_xy(self -> str)`
    - Poligonun XY düzlemindeki yönünü belirler.
  - `_build_edges(self -> dict[int, Edge])`
  - `get_upslope_vector_xy(self -> np.ndarray | None)`
    - Poligonun CCW/CW yapısından bağımsız olarak,
  - `analyze_wind_relation(self, w_vector: np.ndarray, angle_tol_deg: float=5.0 -> WindRelation)`
  - `_wind_to_local_2d(self, wind_vector: np.ndarray -> np.ndarray)`
    - Global 3B rüzgâr vektörünü Surface lokal 2B sistemine dönüştürür.
  - `analyze(self, wind_vector: np.ndarray | None -> None)`
  - `_compute_edge_metrics(self, edge: Edge -> None)`
  - `_is_exposed(self, edge -> bool)`
  - `_mark_leading(self)`

### `structload.windcalc.surface_analyzer`

Path: `structload/windcalc/surface_analyzer.py`

#### Module Functions

- `get_neighbors(surf, all_surfaces)`
- `has_global_leading_neighbor(surf, neighbors)`
- `classify_surface(surf, all_surfaces)`
- `_analysis_classify_all_surface(surfaces_items)`
- `_analysis_global_edges(surfaces_items)`
- `_are_edges_overlapping(e1, e2, tol: float=0.0001 -> bool)`
- `_analyze_shared_edges(surfaces_items, w_dir, tol=0.001 -> None)`

### `structload.windcalc.visualize`

Path: `structload/windcalc/visualize.py`

Sadece görselleştirme. Analiz YAPMAZ, zone ÜRETMEZ.
Girdi: ZoneBundle / ZoneResult

#### Module Functions

- `_edge_kind(edge -> str)`
- `draw_zone_result(ax, result, title_suffix: str='', show_points: bool=True, show_zone_labels: bool=True -> dict[str, Any])`
  - Tek bir ZoneResult'ı verilen 3D eksene çizer.
- `_equalize_axes(ax, points: dict[str, tuple] -> None)`
- `draw_bundle_grid(bundle, figsize=(12, 10), ncols: int=2)`
  - ZoneBundle'daki tüm sonuçları 2x2 grid üzerine çizer.
- `_attach_figure_legend(fig, legend_map: dict[str, Any] -> None)`

### `structload.windcalc.wind_analyzer`

Path: `structload/windcalc/wind_analyzer.py`

#### Classes

- **ZoneKind** (Enum) (line 21)
- **WindAnalyzer** (line 177)
  - `__init__(self, points, polygons, w_dir, **engine_kwargs)`
  - `analyze(self)`
  - `_create_surfaces(self)`
  - `_get_neighbors(self, surf)`
  - `_has_global_leading_neighbor(self, surf, neighbors)`
  - `_classify_surface(self, surf)`
  - `_classify_surfaces(self)`
  - `_analysis_global_edges(self)`
  - `_are_edges_overlapping(e1, e2, tol=0.0001)`
  - `_analyze_shared_edges(self, tol=0.001)`
  - `_generate_zones(self)`
    - Tüm yüzeyler için rüzgar bölgelerini üretir.
  - `_get_wall_zones(self, surface)`
    - Duvar yüzeyi için TS EN 1991-1-4 bölge geometrilerini üretir.
  - `_get_roof_zones(self, surface)`
    - Çatı yüzeyi için bölge geometrilerini üretir.

#### Module Functions

- `_zone_label(table_type, wind_relation, kind)`
  - Zone'un geometrik anlamından CPE tablo etiketini üretir.
- `_make_zone(plane1, coords, kind, *, index=None, table_type=None, pitch=0.0)`
  - Geometrik zone bilgisinden gerçek Zone domain nesnesini oluşturur.

### `structload.windcalc.wind_results`

Path: `structload/windcalc/wind_results.py`

#### Classes

- **WindReport** (line 359)
  - `__init__(self, proje_data)`
  - `analyze(self)`
  - `report(self)`

#### Module Functions

- `show_zones(zones, building, size=800)`
- `get_parameters_report(building -> ReportDataFrame)`
- `_first(v)`
- `_second(v)`
- `_iter_zones(results)`
- `_as_3d(vec -> np.ndarray)`
- `create_cpe_summary_df(zones, engine -> ReportDataFrame)`
- `create_wind_force_df(zones, engine -> ReportDataFrame)`

### `structload.windcalc.windengine`

Path: `structload/windcalc/windengine.py`

#### Classes

- **WindEngine** (line 13)
  - `__post_init__(self)`
  - `update_geometry(self -> None)`
    - Bina geometrisini ve yönlendirilmiş sınır kutusunu (OBB) rüzgar yönüne göre
  - `_calculate_wind_parameters(self -> None)`
  - `report(self)`

### `structload.windcalc.zone`

Path: `structload/windcalc/zone.py`

#### Classes

- **Zone** (line 11)
  - `cpe10(self)`
  - `cpe1(self)`
  - `interpolate(x, x1, x2, y1, y2)`
  - `interpolate_angle(self, data, angle)`
  - `_interpolate(self, cpe_type)`

### `structload.windcalc.zone_generator`

Path: `structload/windcalc/zone_generator.py`

#### Classes

- **ZoneKind** (Enum) (line 17)

#### Module Functions

- `_zone_label(table_type, wind_relation, kind)`
  - Zone'un geometrik anlamından CPE tablo etiketini üretir.
- `_make_zone(plane1, coords, kind, *, index=None, table_type=None, pitch=0.0)`
  - Geometrik zone bilgisinden gerçek Zone domain nesnesini oluşturur.
- `_get_wall_zones(plane1: Surface, e: float -> list[Zone])`
- `_get_roof_zones(plane1: Surface, e: float -> list[Zone])`
- `_analysis_all_zones(all_surfaces, e)`

### `tools.area_to_frame`

Path: `tools/area_to_frame.py`

#### Classes

- **TransferResult** (line 26)
- **AssocPreview** (line 34)
  - Ana renderer'a geçici renk katmanı sağlar. Model datasına dokunmaz.
  - `clear(self -> None)`
- **AssocDraft** (line 48)
  - Panel tarafından tutulan geçici assoc state'i.
- **_ZoneDictAdapter** (line 55)
  - zone_children_by_direction dict'ini zone objesi gibi sunar.
  - `__init__(self, data: dict)`
- **AreaToFrame** (line 71)
  - UI'dan bağımsız polygon→frame iş mantığı.
  - `__init__(self, project)`
  - `math_model(self)`
  - `_analysis_data(self, polygon: Polygon -> PolygonAnalysisData)`
  - `list_polygons(self -> list[Polygon])`
  - `list_frames(self -> dict[int, Frame])`
  - `get_polygon(self, polygon_id: int | None -> Polygon | None)`
  - `list_wind_zones(self, polygon: Polygon -> list[tuple[str, int, object]])`
    - Polygon'a ait zone'lar. Tek kaynak: polygon.zone_children_by_direction.
  - `polygon_loads_summary(self, polygon: Polygon -> dict)`
    - UI göstermek için özet.
  - `area_load_unit(self -> str)`
  - `length_unit(self -> str)`
  - `get_grid_settings(self -> tuple[float, int])`
  - `set_grid_settings(self, step: float, n_bins: int -> None)`
  - `new_draft(self, polygon: Polygon -> AssocDraft)`
  - `toggle(self, draft: AssocDraft, uid: int, on: bool -> None)`
  - `clear_draft(self, draft: AssocDraft -> None)`
  - `auto_assoc(self, polygon: Polygon, draft: AssocDraft, *, keep_excluded: bool=True -> dict)`
    - Eşik değerlerine ve polygon tipine göre uygun frame'leri draft'a ekler.
  - `add_selected_frames(self, polygon: Polygon, draft: AssocDraft, frame_ids: list[int] -> dict)`
    - Sahnede seçili frame'leri draft.associated'a ekler (hariçten çıkarır).
  - `apply(self, polygon: Polygon, draft: AssocDraft -> dict)`
    - Draft'ı polygon ve analysis_data'ya yazar.
  - `cancel(self, polygon: Polygon, draft: AssocDraft -> None)`
  - `transfer_area_loads(self, polygon: Polygon -> TransferResult)`
  - `transfer_wind_zone(self, surface: Polygon, direction_key: str, zone_index: int, zone, *, cpe_kind: str, cpi_pos: float, cpi_neg: float -> TransferResult)`
    - Zone'u (dict veya adapter) frame'lere aktar. Kaynak: polygon.zone_children_by_direction.
  - `_apply_frame_transfers(self, generated -> None)`

### `tools.debug_modal_full`

Path: `tools/debug_modal_full.py`

**Parse error:** unmatched ')' (debug_modal_full.py, line 465)

### `tools.debug_nodes`

Path: `tools/debug_nodes.py`

Node render debug komutu.

Kullanım (uygulama içinden veya Python konsolundan):
    from tools.debug_nodes import debug_nodes
    debug_nodes(app)

    # veya sadece engine ile:
    from tools.debug_nodes import debug_nodes
    debug_nodes(app=None, engine=engine)

#### Module Functions

- `debug_nodes(app=None, engine=None -> dict)`
  - Node render pipeline'ını tüm katmanlarda kontrol eder.
- `debug_nodes_pick(app, screen_x: int, screen_y: int -> int)`
  - Belirli bir ekran noktasında node pick ID'sini döndür (senkron okuma).

### `tools.draw_manager`

Path: `tools/draw_manager.py`

#### Classes

- **DrawManager** (line 19)
  - `__init__(self, engine)`
  - `start(self, mode: str='sequential')`
  - `cancel(self)`
  - `close(self)`
  - `on_mouse_move(self, x, y)`
  - `on_mouse_click(self, x, y -> bool)`
  - `on_key_press(self, key -> bool)`
  - `_click_line(self, target)`
  - `_close_line(self)`
  - `_close_rectangle(self)`
  - `_polygon_from_inside(self, start)`
  - `_finalize_polygon(self, polygon: Polygon)`
  - `_project(self)`
  - `_refresh_pr(self)`
  - `_find_target(self, x, y)`
  - `_find_node(self, x, y)`
  - `_find_snap(self, x, y)`
  - `_project_pt(self, mvp, x, y, z)`
  - `_vertex_from_node(node -> Vertex)`
  - `_same(a, b -> bool)`
  - `_ensure_buffer(self)`
  - `render_preview(self, mvp, shader)`
  - `_preview_endpoint(self -> Vertex | None)`
    - Aktif preview uç noktası: hover_node varsa onu, yoksa mouse_world_pos.
  - `_render_line_preview(self, color_loc)`
  - `_render_polygon_preview(self, color_loc)`
  - `_draw_points(self, color_loc, points, mode, color)`
  - `_draw_rectangle_preview(self, color_loc)`
  - `_upload_draw(self, color_loc, verts, mode, count, color)`
  - `handle_click(self, x, y, button -> bool)`
  - `handle_release(self, x, y, button -> bool)`
  - `handle_move(self, x, y, dx, dy -> bool)`
  - `handle_key(self, key, mods -> bool)`
  - `handle_scroll(self, delta -> bool)`
  - `cleanup(self)`

### `tools.filter_query`

Path: `tools/filter_query.py`

#### Classes

- **ElementFilterQuery** (line 9)
  - `is_empty(self -> bool)`
    - Filtre hiçbir kural içermiyor mu? (boşsa hiçbir şey filtreleme)
- **ModelFilterEngine** (line 64)
  - `evaluate_element(element, query: ElementFilterQuery -> bool)`
  - `filter_to_ids(cls, math_model, query: ElementFilterQuery -> frozenset[int])`
    - Filtreye uyan tüm element ID'lerini döndür.
  - `filter_project_elements(cls, math_model, query)`

#### Module Functions

- `classify_frame_subtype(frame -> str)`

### `tools.font_atlas`

Path: `tools/font_atlas.py`

Basit font atlas — TTF'den bitmap atlas üretir.
- Her karakter için UV + advance + bearing saklar.
- Tek texture olarak GPU'ya yüklenir.
- Binlerce label için tek draw call'lık sistemin temelidir.

#### Classes

- **Glyph** (line 21)
- **FontAtlas** (line 33)
  - Tek texture'da birden fazla glyph barındıran bitmap font atlası.
  - `__init__(self, ttf_path: str | None=None, size: int=32, chars: str | None=None, padding: int=2, supersample: int=1)`
    - Parameters
  - `_build(self)`
    - Atlas image'ını üretir, glyph metriklerini doldurur.
  - `upload(self)`
  - `measure(self, text: str, pixel_size: float -> tuple[float, float])`
    - Verilen metnin `pixel_size` yüksekliğinde piksel cinsinden boyutunu döner.
  - `cleanup(self)`

### `tools.frame_to_link`

Path: `tools/frame_to_link.py`

#### Module Functions

- `ensure_default_link_prop(project -> LinkPropLinear)`
  - Projede DefaultLink yoksa oluştur.
- `frame_to_link(frame: Frame, link_prop_name: str=DEFAULT_LINK_PROP_NAME -> tuple[Link | None, str | None])`
  - Bir Frame'i Link'e çevirir. Hata varsa (None, err) döner.
- `convert_frames_to_links(scene, project, frames: list[Frame], link_prop_name: str=DEFAULT_LINK_PROP_NAME, delete_original: bool=True -> dict)`
  - Seçili Frame listesini Link'e çevir. Sonuç raporu döndürür.

### `tools.gridsystem`

Path: `tools/gridsystem.py`

#### Classes

- **GridSystem** (line 44)
  - `__init__(self, shader_program)`
  - `origin_x(self -> float)`
  - `origin_y(self -> float)`
  - `origin_z(self -> float)`
  - `planes_visibility(self -> dict[str, bool])`
  - `set_origin(self, x, y, z)`
  - `set_coords(self, x_list, y_list, z_list)`
  - `set_plane(self, plane: GridPlane, visible=None)`
  - `_rebuild_plane(self, plane: GridPlane)`
  - `_upload_plane(self, plane: GridPlane, vertices: list)`
  - `_delete_plane_gpu(self, plane: GridPlane)`
  - `_clear_plane(self, plane: GridPlane)`
  - `draw(self, mvp_matrix)`
  - `cleanup(self)`
  - `info(self)`
  - `get_label_anchors(self)`
    - Her görünür plane için label anchor noktaları döner.
  - `get_bounds(self)`
    - Gridin min/max sınırlarını ve merkezini hesaplar.
  - `add_user_plane(self, pdef: GridPlaneDef)`
  - `set_user_planes(self, planes: list[GridPlaneDef])`
    - Replace runtime work planes with the project's persisted definitions.
  - `remove_user_plane(self, name: str)`
  - `get_user_plane(self, name: str -> GridPlaneDef | None)`
  - `set_active_user_plane(self, name: str | None)`
  - `rebuild_user_plane(self, pdef: GridPlaneDef)`
  - `rebuild_all(self)`
  - `_rebuild_user_plane(self, pdef: GridPlaneDef)`
  - `_upload_plane_by_key(self, key: str, vertices: list)`
  - `_delete_gpu_by_key(self, key: str)`

### `tools.perf_summary`

Path: `tools/perf_summary.py`

### `tools.polygon_frame_assoc`

Path: `tools/polygon_frame_assoc.py`

Polygon ↔ Frame otomatik ilişkilendirme için saf geometri yardımcıları.

Bu modül state tutmaz. `Polygon.refresh_assoc` tarafından çağrılır.
`plane` paketinden bağımsızdır.

#### Module Functions

- `segment_intersects_box(a, b, lower, upper, tol -> bool)`
  - Liang-Barsky: [a,b] segmenti 3B AABB [lower, upper] ile kesişiyor mu?
- `segment_hits_band_and_box(a_local, b_local, lower, upper, *, ignore_bounds: bool, tol: float -> bool)`
  - Segmentin depth bandı + (opsiyonel) uv kutusuyla kesişimi.
- `angle_to_axis_deg(vec: np.ndarray, axis: np.ndarray -> float)`
  - 0..90 derece arası mutlak açı. Sıfır vektör → 90 döner.
- `_axis_for(direction: DistType, plane_u, plane_v)`
- `passes_direction_filter(frame_vec: np.ndarray, plane_u: np.ndarray, plane_v: np.ndarray, direction: DistType, tol_deg: float -> bool)`
  - `direction` filtresine göre frame vektörü uygun mu?

### `tools.polygon_load_transfer`

Path: `tools/polygon_load_transfer.py`

Geometric transfer of polygon area loads to explicitly associated frames.

#### Module Functions

- `_t_to_effective_x(t_full: float, intervals: list[tuple[float, float]], full_len: float -> float)`
  - Tam frame üzerindeki t (0..1) → polygon içindeki x (0..eff_len).
- `_point_in_polygon_2d(point, polygon -> bool)`
  - 2D point-in-polygon testi (ray casting).
- `_point_segment_param(pt, a, b -> tuple[float, float])`
  - Nokta-doğru parçası mesafesi ve parametresi (t ∈ [0,1]).
- `build_polygon_frame_loads(math_model, polygon, loads=None, *, analysis_data=None, dist_type=None, step: float=200.0, n_bins: int=12 -> dict[int, dict[str, FrameDistributedLoad]])`
  - Build frame load sets from only the frame IDs explicitly associated to a polygon.
- `_polygon_coordinates(polygon)`
- `_project_frame(frame, origin, u, v, normal, polygon_2d)`
- `_segment_polygon_intervals(start, end, polygon)`
- `_point_in_polygon(point, polygon)`
- `_tributary_areas(polygon, frames, distribution)`
- `_tributary_q_profiles_grid(polygon, frame_data: list[dict], load_value: float, *, step: float=200.0, n_bins: int=12 -> dict[int, list[tuple[float, float, float, float]]])`
- `_clip_axis(polygon, axis, lower, upper)`
- `_clip_half_plane(polygon, normal, boundary)`
- `_polygon_area(polygon)`
- `_cross_2d(first, second)`
- `_frame_load_direction(direction)`
- `transfer_polygon_loads_to_frames(math_model, polygon, *, analysis_data, pattern: str | None=None -> dict[int, dict[str, FrameDistributedLoad]])`
  - Build and apply this polygon's area loads, replacing its prior contribution.

### `tools.s2k`

Path: `tools/s2k/__init__.py`

S2K import katmanı — temiz public API.

#### Module Functions

- `__getattr__(name: str)`

### `tools.s2k.context`

Path: `tools/s2k/context.py`

#### Classes

- **LoadContext** (line 26)
  - S2K handler'larının veri topladığı merkezi kutu.

### `tools.s2k.handlers`

Path: `tools/s2k/handlers/__init__.py`

Handler router + priority. Her handler (ctx, df) imzasında.

build_router() → {table_name: handler}
build_sorted_router() → [(table_name, handler)]  (önceliğe göre sıralı)

#### Module Functions

- `get_priority(table_name: str -> int)`
- `build_router( -> dict[str, Callable])`
- `build_sorted_router( -> list[tuple[str, Callable]])`

### `tools.s2k.handlers._colors`

Path: `tools/s2k/handlers/_colors.py`

S2K renk string → (R, G, B) 0-1 aralığında.

Desteklenen formatlar:
    - İsimli: "Red", "Cyan", "Gray8Dark", "Gray4", "Gray1Light", ...
    - Windows BGR sayısal: 16711808, 4227200, ...
    - Hex: "#FF0080"

#### Module Functions

- `color_from_string(s -> tuple[float, float, float])`
  - S2K Color alanı → (R, G, B). Bilinmeyen → DEFAULT_COLOR.

### `tools.s2k.handlers.areas`

Path: `tools/s2k/handlers/areas.py`

AREA CONNECTIVITY, ASSIGNMENTS.

#### Module Functions

- `_safe_float(row, key, default=0.0)`
- `handle_area_conn(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_area_assign(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_area_section_design(ctx: LoadContext, df: pd.DataFrame -> None)`
  - AREA SECTION PROPERTY DESIGN PARAMETERS.
- `handle_area_section_time_dep(ctx: LoadContext, df: pd.DataFrame -> None)`
  - AREA SECTION PROPERTY - TIME DEPENDENT.

### `tools.s2k.handlers.frames`

Path: `tools/s2k/handlers/frames.py`

FRAME CONNECTIVITY, ASSIGNMENTS, RELEASES, MODIFIERS, DESIGN PROCS, AUTO MESH.

#### Module Functions

- `_to_bool(v, default=False)`
- `_safe_float(row, key, default=0.0)`
- `handle_frame_conn(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_assign(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_releases(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_modifiers(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_design_procs(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_auto_mesh(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_output_stations(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME OUTPUT STATION ASSIGNMENTS.
- `handle_frame_insertion_points(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME INSERTION POINT ASSIGNMENTS.
- `handle_frame_end_offsets(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME OFFSET ALONG LENGTH ASSIGNMENTS.
- `handle_frame_local_axes(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL.
- `handle_frame_load_transfer(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME LOAD TRANSFER OPTIONS.
- `handle_frame_section_rebar_col(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME SECTION PROPERTIES 02 - CONCRETE COLUMN.
- `handle_frame_section_rebar_beam(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME SECTION PROPERTIES 03 - CONCRETE BEAM.
- `handle_frame_time_dependent(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME SECTION PROPERTIES 13 - TIME DEPENDENT.

### `tools.s2k.handlers.grids`

Path: `tools/s2k/handlers/grids.py`

GRID LINES.

#### Module Functions

- `_safe_float(row, key, default=0.0)`
- `handle_grid_lines(ctx: LoadContext, df: pd.DataFrame -> None)`

### `tools.s2k.handlers.links`

Path: `tools/s2k/handlers/links.py`

LINK PROPERTIES 01/02, CONNECTIVITY - LINK, LINK PROPERTY ASSIGNMENTS.

Birim sözleşmesi: S2K değerleri float (S2K CurrUnits).
`convert_project_units` LinkPropLinear.__unit_schema__ üzerinden dönüştürür.

#### Module Functions

- `_safe_float(row, key, default: float=0.0 -> float)`
- `_pick_name(row -> str)`
  - LINK satırından prop adını çıkar (v10/v25 uyumlu).
- `_pick_stiffness(row, i: int -> float)`
  - S2K'ta olası kolon adları: Ke1..Ke6 → K1..K6 → Stiff1..Stiff6.
- `_pick_damping(row, i: int -> float)`
  - S2K'ta olası kolon adları: Ce1..Ce6 → C1..C6 → Damp1..Damp6.
- `_pick_bool(row, key: str, default: bool=True -> bool)`
- `handle_link_props(ctx: LoadContext, df: pd.DataFrame -> None)`
  - LINK PROPERTIES 01 - GENERAL.
- `handle_link_props_linear(ctx: LoadContext, df: pd.DataFrame -> None)`
  - LINK PROPERTIES 02 - LINEAR.
- `handle_link_conn(ctx: LoadContext, df: pd.DataFrame -> None)`
  - CONNECTIVITY - LINK.
- `handle_link_assign(ctx: LoadContext, df: pd.DataFrame -> None)`
  - LINK PROPERTY ASSIGNMENTS.

### `tools.s2k.handlers.loads`

Path: `tools/s2k/handlers/loads.py`

JOINT/FRAME/AREA LOADS — tüm birim dönüşümü UnitConverter üzerinden.

#### Module Functions

- `_safe_float(row, key, default=0.0)`
- `_sap_dir_to_load_dir(s: str -> LoadDirection)`
- `_sap_frame_dir_code(s: str -> str)`
  - Frame dist load 'Dir' → SAP internal code '1'..'10'.
- `handle_joint_loads(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_gravity(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_distributed(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_points(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_temperature(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_area_uniform(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_area_uniform_to_frame(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_area_wind(ctx: LoadContext, df: pd.DataFrame -> None)`

### `tools.s2k.handlers.materials`

Path: `tools/s2k/handlers/materials.py`

MATERIAL PROPERTIES 01/02/03x/04/06/09 — v10 + v25 uyumlu.

#### Module Functions

- `_safe_float(row, key, default=0.0 -> float)`
- `_bool(row, key, default=False -> bool)`
- `_parse_mat_type(row -> MatType)`
  - v25: Type = Steel/Concrete/Rebar/Tendon/... ; v10: Type = Isotropic + DesignType = Concrete.
- `handle_material_props(ctx: LoadContext, df: pd.DataFrame -> None)`
  - MATERIAL PROPERTIES 01 - GENERAL.
- `handle_material_mech(ctx: LoadContext, df: pd.DataFrame -> None)`
  - MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES (yalnızca v25).
- `handle_material_steel(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_material_concrete(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_material_rebar(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_material_tendon(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_material_von_mises(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_material_design_concrete_v10(ctx: LoadContext, df: pd.DataFrame -> None)`
  - MATERIAL PROPERTIES 04 - DESIGN CONCRETE (v10).
- `handle_material_damping(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_material_acceptance(ctx: LoadContext, df: pd.DataFrame -> None)`

### `tools.s2k.handlers.nodes`

Path: `tools/s2k/handlers/nodes.py`

JOINT COORDINATES, RESTRAINTS, CONSTRAINTS, DIAPHRAGMS.

#### Module Functions

- `_safe_float(row, key, default=0.0)`
- `_bool(v, default=False -> bool)`
- `_make_constraint_def(row, ctype: ConstraintType -> ConstraintDefinition)`
- `handle_constraint_definitions(ctx, df, ctype: ConstraintType)`
  - Ortak: 9 constraint tablosu için tek handler.
- `handle_joint_springs(ctx: LoadContext, df: pd.DataFrame -> None)`
  - JOINT SPRING ASSIGNMENTS 1 - UNCOUPLED.
- `handle_joints(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_joint_restraints(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_joint_constraints(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_diaphragms(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_joint_loads(ctx: LoadContext, df: pd.DataFrame)`
  - S2K 'JOINT LOADS' tablosu.
- `handle_joint_added_mass(ctx: LoadContext, df: pd.DataFrame -> None)`
  - JOINT ADDED MASS ASSIGNMENTS.

### `tools.s2k.handlers.patterns`

Path: `tools/s2k/handlers/patterns.py`

LOAD PATTERN, CASE, COMBO, MASS SOURCE — v10 + v25 uyumlu.

#### Module Functions

- `_safe_float(row, key, default=0.0)`
- `_str(row, key, default='' -> str)`
- `_handle_load_patterns_v25(ctx: LoadContext, df: pd.DataFrame -> None)`
  - v25: LoadPat, DesignType, SelfWtMult.
- `_handle_load_patterns_v10(ctx: LoadContext, df: pd.DataFrame -> None)`
  - v10: LoadCase, DesignType, SelfWtMult — bu tablo LOAD PATTERN'dir.
- `_handle_load_cases_v25(ctx: LoadContext, df: pd.DataFrame -> None)`
  - v25: Case, Type, InitialCond, DesignType, ...
- `_handle_load_cases_v10(ctx: LoadContext, df: pd.DataFrame -> None)`
  - v10: ANALYSIS CASE DEFINITIONS — Case, Type, InitialCond, RunCase, ModalCase.
- `handle_load_patterns(ctx: LoadContext, df: pd.DataFrame -> None)`
  - LOAD PATTERN DEFINITIONS — v25 (v10'da bu tablo yok).
- `handle_load_cases(ctx: LoadContext, df: pd.DataFrame -> None)`
  - LOAD CASE DEFINITIONS — v25 (v10'da bu tablo LOAD PATTERN).
- `handle_analysis_cases_v10(ctx: LoadContext, df: pd.DataFrame -> None)`
  - v10: ANALYSIS CASE DEFINITIONS → LoadCase.
- `handle_static_assignments(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_modal_cases(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_combinations(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_mass_source(ctx: LoadContext, df: pd.DataFrame -> None)`

### `tools.s2k.handlers.program`

Path: `tools/s2k/handlers/program.py`

PROGRAM CONTROL, PROJECT INFORMATION.

#### Module Functions

- `handle_program_control(ctx, df)`
- `handle_project_information(ctx: LoadContext, df: pd.DataFrame -> None)`

### `tools.s2k.handlers.section_cuts`

Path: `tools/s2k/handlers/section_cuts.py`

SECTION CUTS 1/3.

#### Module Functions

- `_safe_float(row, key, default=0.0)`
- `handle_section_cuts_gen(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_section_cuts_quad(ctx: LoadContext, df: pd.DataFrame -> None)`

### `tools.s2k.handlers.sections`

Path: `tools/s2k/handlers/sections.py`

FRAME/AREA SECTION PROPERTIES, AUTO SELECT, SD geometry.

Birim sözleşmesi: S2K değerleri `float` (S2K CurrUnits).
`ProjectBuilder` S2K biriminde yaratır, `finalize_and_convert(N_MM)` dönüştürür.
Doğrulama `tools.section_checks.check_section` ile.

#### Module Functions

- `_safe_float(row, key, default=0.0 -> float)`
- `_dim_modifier(row, key: str, default: float=1.0 -> float)`
  - Boyutsuz modifier — 0 ise default.
- `_map_sap_to_local(row, sd_section=None -> tuple[SectionType, dict[str, float]])`
  - SAP satırını SectionType + params'a çevir. Değerler S2K biriminde (float).
- `_resolve_material(ctx: LoadContext, mat_name: str -> Material | None)`
  - S2K biriminde material — handler'lar `float` doldurur.
- `handle_frame_props(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_auto_select_lists(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_area_props(ctx: LoadContext, df: pd.DataFrame -> None)`
  - AREA SECTION PROPERTIES — AreaSection nesnesi üret.
- `handle_sd_general(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_sd_polygon(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_sd_rebar_rect(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_frame_section_rebar_col(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME SECTION PROPERTIES 02 - CONCRETE COLUMN.
- `handle_frame_section_rebar_beam(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME SECTION PROPERTIES 03 - CONCRETE BEAM.
- `handle_frame_section_time_dependent(ctx: LoadContext, df: pd.DataFrame -> None)`
  - FRAME SECTION PROPERTIES 13 - TIME DEPENDENT.
- `handle_sd_fiber_general(ctx: LoadContext, df: pd.DataFrame -> None)`
  - SECTION DESIGNER PROPERTIES 30 - FIBER GENERAL.

### `tools.s2k.handlers.spectra`

Path: `tools/s2k/handlers/spectra.py`

RESPONSE SPECTRUM FUNCTIONS/CASES, AUTO SEISMIC.

#### Module Functions

- `_safe_float(row, key, default=0.0)`
- `handle_spectrum_functions_TSC(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_spectrum_functions_file(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_spectrum_functions_user(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_response_spectrum_gen(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_response_spectrum_assign(ctx: LoadContext, df: pd.DataFrame -> None)`
- `handle_auto_seismic(ctx: LoadContext, df: pd.DataFrame -> None)`

### `tools.s2k.loader`

Path: `tools/s2k/loader.py`

S2K dosya parser'ı + yüksek seviye loader.

#### Classes

- **S2KMetadata** (line 30)
- **S2KParser** (line 42)
  - S2K dosyasını tablo DataFrame'lerine ayrıştırır.
  - `__init__(self, file_path: str | None=None)`
  - `_parse(self, file_path: str -> None)`
  - `_parse_rows(self, lines -> list)`
  - `get_table(self, name: str -> pd.DataFrame)`
  - `get_all_tables(self -> dict[str, pd.DataFrame])`
- **S2KLoader** (line 170)
  - S2K → Project dönüşümü.
  - `__init__(self, file_path: str | None=None)`
  - `load(self, project: Project | None=None -> Project)`
    - Dosyayı parse et + handler'ları çalıştır + project üret.
  - `load_with_metadata(self, project=None, *, ctx=None -> tuple[Project, S2KMetadata])`
  - `load_from_context(self, ctx: LoadContext, project: Project | None=None -> Project)`
    - Hazır LoadContext → Project. Değerler S2K biriminde KALIR.
  - `_build_metadata(self, ctx: LoadContext -> S2KMetadata)`
  - `_run_handlers(self -> LoadContext)`
    - Sıralı + kalan router ile tüm tabloları ctx'ye uygula.
  - `_safe_call(self, handler, ctx: LoadContext, df, table_name: str, prefix: str='')`
  - `_apply_ctx_to_builder(self, ctx: LoadContext, builder: ProjectBuilder -> None)`
    - ctx'teki tüm tanımları builder'a aktar.
  - `_apply_materials(self, ctx, builder)`
  - `_apply_sections(self, ctx, builder)`
  - `_apply_area_sections(self, ctx: LoadContext, builder: ProjectBuilder -> None)`
  - `_apply_load_patterns(self, ctx, builder)`
  - `_apply_load_cases(self, ctx, builder)`
  - `_apply_combinations(self, ctx, builder)`
  - `_apply_constraint_definitions(self, ctx: LoadContext, builder: ProjectBuilder -> None)`
  - `_apply_grid(self, ctx: LoadContext, builder: ProjectBuilder -> None)`
  - `_build_scene_into_builder(self, ctx: LoadContext, builder: ProjectBuilder -> None)`
  - `_sorted_router()`
    - build_sorted_router() sonucu — modül yüklenirken bir kez.
  - `_fallback_router()`
    - build_router() sonucu — modül yüklenirken bir kez.

#### Module Functions

- `_derive_params_from_sd(sd -> dict)`
  - SD polygon(lar)dan bbox + analitik özellik türet.

### `tools.s2k.s2k_scene_builder`

Path: `tools/s2k/s2k_scene_builder.py`

Scene inşası: node/frame/area/link + load assignment.

S2K değerleri float (S2K CurrUnits) — dönüşüm convert_project_units'te.

#### Module Functions

- `_order_polygon_nodes(nodes: list[Node] -> list[Node])`
  - Poligon düğümlerini sırala — kelebek düzeltir.
- `_safe_float(row, key, default=0.0)`
- `_opt_float(v -> float | None)`
- `_to_bool(v, default: bool=False -> bool)`
- `_parse_restraints(df: pd.DataFrame -> dict[str, dict])`
- `_parse_frame_assign(df, ctx -> dict[str, tuple[str, float]])`
- `_parse_frame_release(df -> dict[str, dict])`
- `_parse_area_assign(df -> dict[str, dict])`
  - AREA SECTION ASSIGNMENTS → {area_id: {section, mat_prop, thick_over, offset_over}}.
- `_parse_link_assign(df -> dict[str, str])`
- `_sap_area_dir(s: str -> LoadDirection)`
- `_fallback_section_name(builder, ctx -> str)`
- `create_nodes(builder, ctx: LoadContext -> dict[str, Node])`
- `_apply_joint_constraints(ctx: LoadContext, node_map: dict[str, Node] -> None)`
- `_apply_joint_springs(ctx, node_map: dict[str, Node] -> None)`
- `_apply_joint_added_mass(ctx: LoadContext, node_map: dict[str, Node] -> None)`
- `create_frames(builder, ctx: LoadContext, node_map: dict[str, Node] -> tuple[dict[str, Frame], int])`
- `_apply_frame_insertion_points(ctx, frame_map)`
- `_apply_frame_end_offsets(ctx, frame_map)`
- `_apply_frame_output_stations(ctx, frame_map)`
- `_apply_frame_load_transfer(ctx, frame_map)`
- `_apply_frame_local_axes(ctx, frame_map)`
- `_apply_frame_auto_mesh(ctx, frame_map)`
- `_apply_frame_modifiers(ctx, frame_map)`
- `_apply_frame_design_procs(ctx, frame_map)`
- `_apply_frame_time_dependent(ctx, frame_map)`
- `create_areas(builder, ctx: LoadContext, node_map: dict[str, Node] -> tuple[dict[str, Area], int])`
- `create_links(builder, ctx: LoadContext, node_map: dict[str, Node] -> int)`
- `assign_loads(ctx: LoadContext, node_map, frame_map, area_map -> None)`
- `assign_joint_loads(ctx: LoadContext, node_map -> int)`
  - ctx.joint_loads (dict) → node.loads. Tek kaynak.
- `_load_frame_loads(ctx: LoadContext, frame_map)`
- `_load_area_loads(ctx: LoadContext, area_map)`

### `tools.s2k_exporter`

Path: `tools/s2k_exporter.py`

S2K Exporter — Cad4 projesini SAP2000 .s2k formatına çevirir.

Kullanım:
    from tools.s2k_exporter import S2KExporter
    text = S2KExporter.export(project)                    # tüm sahne
    text = S2KExporter.export(project, selected_elements) # seçili elemanlar

Kısmi export: SAP2000'de "Add to existing model" ile birleştirilebilir.
Aynı label'lı tanımlar çakışırsa SAP import dialog'unda Replace/Ignore seçilir.

#### Classes

- **S2KExporter** (line 15)
  - `export(cls, project, selected_elements: list | None=None -> str)`
  - `save(cls, project, filepath: str, selected_elements: list | None=None -> str)`
  - `_collect_used(cls, scene, project, selected_elements=None -> dict[str, set])`
    - Hangi node / section / material / pattern kullanılıyor?
  - `_program_control(cls, project -> str)`
  - `_active_dof(cls -> str)`
  - `_materials(cls, project, used -> str)`
  - `_sections(cls, project, used -> str)`
  - `_link_props(cls, project, used -> str)`
  - `_load_patterns(cls, project, used, scene -> str)`
  - `_load_cases(cls, project, used, scene -> str)`
  - `_combinations(cls, project, used -> str)`
  - `_joint_coordinates(cls, scene, used -> str)`
  - `_joint_restraints(cls, scene, used -> str)`
  - `_frame_connectivity(cls, scene, used -> str)`
  - `_frame_section_assignments(cls, scene, used -> str)`
  - `_frame_local_axes(cls, scene, used -> str)`
  - `_frame_loads_distributed(cls, scene, used -> str)`
  - `_area_connectivity(cls, scene, used -> str)`
  - `_area_section_properties(cls, scene, used -> str)`
    - Sahnedeki area'ların 'section_name'lerinden benzersiz olanları
  - `_area_section_assignments(cls, scene, used -> str)`
  - `_link_connectivity(cls, scene, used -> str)`
  - `_link_assignments(cls, scene, used -> str)`
  - `_g(v -> str)`
  - `_sap_coordsys(cs -> str)`
  - `_joint_springs(cls, scene, used -> str)`
  - `_joint_added_mass(cls, scene, used -> str)`
  - `_joint_constraint_assignments(cls, scene, used -> str)`
  - `_sd_section_tables(cls, project, used -> str)`
    - SECTION DESIGNER PROPERTIES 01 + 16 + (opsiyonel 30).
  - `_color_to_sap(rgb -> str)`
    - (r,g,b) 0-1 → SAP renk ismi veya BGR.
  - `_constraint_definitions(cls, project -> str)`
  - `_frame_insertion_points(cls, scene, used -> str)`
  - `_frame_end_offsets(cls, scene, used -> str)`
  - `_frame_output_stations(cls, scene, used -> str)`
  - `_frame_auto_mesh(cls, scene, used -> str)`
  - `_frame_modifiers(cls, scene, used -> str)`
  - `_frame_design_procs(cls, scene, used -> str)`
  - `_frame_load_transfer(cls, scene, used -> str)`

### `tools.sap2000_mass_compare`

Path: `tools/sap2000_mass_compare.py`

**Parse error:** unindent does not match any outer indentation level (sap2000_mass_compare.py, line 149)

### `tools.section_checks`

Path: `tools/section_checks.py`

Kesit özellikleri — derin doğrulama.

Katmanlar:
    1. Temel kontrol (core.units.validate_section_properties) — Area>0, r33 makul
    2. Analitik formüller (I, RECT, TUBE, PIPE) — profil boyutlarından I33/I22/J
    3. Katalog karşılaştırma — section.catalog_props varsa

Tüm fonksiyonlar saf: Section → list[str]. Yan etki yok, exception fırlatmaz.

Kullanım:
    from tools.section_checks import check_section
    for msg in check_section(section, strict=False):
        logger.info("[SectionCheck] %s", msg)

#### Module Functions

- `analytical_i_section(h: float, b: float, tw: float, tf: float -> dict[str, float])`
  - I-profile analitik özellikler (mm cinsinden giriş).
- `analytical_rect_section(h: float, b: float -> dict[str, float])`
  - Dolu dikdörtgen. h: yükseklik (I33 ekseni), b: genişlik.
- `analytical_tube_section(h: float, b: float, t: float -> dict[str, float])`
  - Dikdörtgen kutu (içi boş). t: et kalınlığı (tek).
- `analytical_pipe_section(ro: float, ri: float -> dict[str, float])`
  - Dairesel boru. ro: dış yarıçap, ri: iç yarıçap.
- `analytical_properties(section -> dict[str, float] | None)`
  - Kesit tipine göre analitik özellikleri döndür.
- `_compare(section, reference: dict[str, float], tol_by_prop: dict[str, float], source: str -> list[str])`
  - section.profile_params ile reference sözlüğünü karşılaştır.
- `_check_invariants(section -> list[str])`
  - Genel kesit değişmezleri — analitik olmayan tipler için de geçerli.
- `_check_unit_suspicion(section -> list[str])`
  - Birim hatası belirtileri — değerler tipik aralığın çok dışındaysa.
- `check_section(section, *, strict: bool=False -> list[str])`
  - Tek kesit için tam doğrulama.
- `check_all_sections(sections: dict[str, Section], *, strict: bool=False, logger=None -> dict[str, list[str]])`
  - Tüm kesitleri doğrula.

### `tools.section_preview`

Path: `tools/section_preview.py`

Kesit 2D önizleme çizici.
Section.profile_type + profile_params + color'dan otomatik avatar üretir.

#### Classes

- **_DrawListAdapter** (line 16)
  - `__init__(self, draw_list)`
  - `add_rect_filled(self, x1, y1, x2, y2, color)`
  - `add_rect(self, x1, y1, x2, y2, color, *, thickness=1.0)`
  - `add_circle_filled(self, x, y, radius, color)`
  - `add_circle(self, x, y, radius, color, *, num_segments=0, thickness=1.0)`

#### Module Functions

- `_fit_dims(params_w, params_h, avail_w, avail_h, margin=4.0)`
  - Profil boyutlarını (w, h) verilen alana oranlı sığdır.
- `_color_u32(color, alpha=1.0)`
  - (r, g, b) tuple → packed ImU32.
- `_color_u32_dark(color, factor=0.4, alpha=1.0)`
  - Koyulaştırılmış renk — içi boş profillerde kenar için.
- `_draw_rect(dl, x0, y0, aw, ah, color, p)`
- `_draw_circle(dl, x0, y0, aw, ah, color, p)`
- `_draw_pipe(dl, x0, y0, aw, ah, color, p)`
- `_draw_box(dl, x0, y0, aw, ah, color, p)`
- `_draw_i(dl, x0, y0, aw, ah, color, p)`
- `_draw_c(dl, x0, y0, aw, ah, color, p)`
- `_draw_l(dl, x0, y0, aw, ah, color, p)`
- `_draw_t(dl, x0, y0, aw, ah, color, p)`
- `_draw_fallback(dl, x0, y0, aw, ah, _color, _params)`
  - Bilinmeyen tip — gri dolu kutu.
- `_draw_sd(draw_list, origin, avail_w, avail_h, params, color, sd_section=None)`
  - SD Section — polygon'lardan kesit önizleme.
- `draw_section_preview(section, avail_w=200, avail_h=150)`

### `tools.wind_manager`

Path: `tools/wind_manager.py`

#### Classes

- **WindManager** (line 16)
  - `__init__(self, app: CadApp)`
  - `wind_state(self -> dict)`
  - `run_wind(self -> None)`
  - `select_wind_direction(self, w_dir -> None)`
  - `_wind_key(self, w_dir -> str)`
  - `_start_wind_analysis(self, direction_key: str, direction -> None)`
  - `process_queue(self -> None)`

### `tools.wind_scene_adapter`

Path: `tools/wind_scene_adapter.py`

#### Classes

- **WindSceneAdapter** (line 13)
  - Translate CAD geometry (Project Polygons / Vertices) to the wind calculator.
  - `_coefficient_pair(value: Any -> tuple[float, float])`
  - `build_inputs(project -> tuple[dict[str, list[float]], dict[str, list[str]], dict[str, Any]])`
  - `analyze(points: dict[str, list[float]], polygons: dict[str, list[str]], wind_config: dict[str, Any], w_dir: tuple[float, float, float] -> tuple[list[Any], dict[str, Any]])`
  - `store_zones(project, direction_key: str, zones: list[Any], engine_data: dict[str, Any] | None=None, direction: tuple[float, float, float] | None=None -> None)`
    - Analiz önbelleği: project.loads.wind_zones + wind_results.
  - `update_direction_result(result: WindDirectionResult, zones: list[Any], engine_data: dict[str, Any] -> None)`
  - `build_inputs_for_polygons(project, polygons)`
    - Seçili polygon'lardan structload input.

### `ui`

Path: `ui/__init__.py`

### `ui.actions_registry`

Path: `ui/actions_registry.py`

#### Classes

- **ActionSpec** (line 15)

#### Module Functions

- `build_commands(host: 'UIHost' -> dict[str, Callable])`
  - ActionSpec listesinden runtime dispatch tablosu üret.
- `build_panel_states(host: 'UIHost' -> dict[str, Callable[[], bool]])`
  - Panel görünürlük ve aksiyon aktiflik durumları.

### `ui.base`

Path: `ui/base/__init__.py`

### `ui.base.panel_base`

Path: `ui/base/panel_base.py`

#### Classes

- **Category** (StrEnum) (line 12)
- **PanelBase** (line 26)
  - `__init_subclass__(cls, **kwargs)`
  - `__init__(self, app=None, **overrides)`
  - `open(self, **kw -> None)`
  - `close(self -> None)`
  - `set_context(self, ctx: dict -> None)`
  - `_on_context_ready(self -> None)`
    - Alt sınıf override eder — context geldiğinde bir kez.
  - `_refresh_draft(self -> None)`
  - `reset(self -> None)`
  - `apply(self -> bool)`
  - `_emit_commands(self -> None)`
  - `draw(self -> None)`
  - `_draw_apply_bar(self -> None)`
  - `has_pending_changes(self -> bool)`
  - `_on_apply_clicked(self -> None)`
  - `on_apply_action(self -> None)`
  - `_on_reset_clicked(self -> None)`
  - `on_reset_action(self -> None)`
  - `draw_content(self -> None)`
  - `draw_standard_layout(self -> None)`
  - `draw_header(self -> None)`
    - 1. Seçili eleman özeti. Override eder.
  - `draw_settings(self -> None)`
    - 2. Form alanları (enum, input). Override eder.
  - `draw_visual(self -> None)`
    - 3. Görsel (canvas/plot). Opsiyonel — override etmezse atlanır.
  - `draw_table(self -> None)`
    - 4. Tablo. Opsiyonel — override etmezse atlanır.
  - `draw_actions(self -> None)`
    - 5. Alt butonlar ([UYGULA] [Temizle] [Yenile]). Override eder.
  - `_has_visual(self -> bool)`
  - `_has_table(self -> bool)`
  - `section_label(self, text: str -> None)`
  - `action_button(self, label: str, width: int=80, enabled: bool=True -> bool)`
  - `status_line(self, text: str, kind: str='info' -> None)`
  - `mark_dirty(self -> None)`
  - `queue(self)`
  - `_apply_preview(self, active: bool -> None)`

### `ui.helpers`

Path: `ui/helpers/__init__.py`

### `ui.helpers.adapters`

Path: `ui/helpers/adapters.py`

#### Module Functions

- `node_to_values(node -> dict)`
- `values_to_node(node, v: dict -> None)`
- `_segments_to_text(segments -> str)`
- `_text_to_segments(text: str -> list)`
- `frame_to_values(frame -> dict)`
- `values_to_frame(frame, v: dict -> None)`
- `area_to_values(area -> dict)`
- `values_to_area(area, v: dict -> None)`
- `link_to_values(link -> dict)`
- `values_to_link(link, v: dict -> None)`
- `polygon_to_values(poly, analysis_data=None -> dict)`
- `values_to_polygon(poly, v: dict, analysis_data=None -> None)`
- `line_to_values(line -> dict)`
- `values_to_line(line, v: dict -> None)`
- `element_to_values(obj, *, analysis_data=None -> dict)`
- `_apply_extras(obj, values)`
- `values_to_element(obj, values: dict, *, analysis_data=None -> None)`
- `elements_to_common_values(elements -> dict)`

### `ui.helpers.apply_bar`

Path: `ui/helpers/apply_bar.py`

#### Module Functions

- `draw_apply_bar(dirty: bool, on_apply: Callable[[], None], on_reset: Callable[[], None] -> bool | None)`
  - Apply/Reset buton barı.

### `ui.helpers.schema`

Path: `ui/helpers/schema.py`

Şema tanımları — ImGui'den bağımsız, sadece veri.

#### Classes

- **Field** (line 8)
- **Group** (line 21)

#### Module Functions

- `get_path(d: dict, path: str)`
- `set_path(d: dict, path: str, value)`

### `ui.helpers.schemas`

Path: `ui/helpers/schemas.py`

Her element tipi için hazır şemalar.

#### Module Functions

- `node_schema()`
- `frame_schema()`
- `area_schema()`
- `link_schema()`
- `polygon_schema()`
- `line_schema()`
- `grid_schema()`
- `plane_schema()`
- `schema_for(element_type: str)`
- `multi_schema_for(elements)`

### `ui.panels`

Path: `ui/panels/__init__.py`

### `ui.panels.area_to_frame_panel`

Path: `ui/panels/area_to_frame_panel.py`

Area to Frame paneli — standart layout + collapsing sections.

#### Classes

- **AreaToFramePanel** (PanelBase) (line 16)
  - `__init__(self, app=None, on_transfer_complete=None, **overrides)`
  - `_on_context_ready(self -> None)`
  - `close(self -> None)`
  - `draw_header(self -> None)`
  - `_draw_summary(self, polygon: Polygon -> None)`
  - `draw_settings(self -> None)`
  - `_selected_polygon(self -> Polygon | None)`
  - `draw_table(self -> None)`
  - `_draw_assoc_list_table(self, draft: AssocDraft -> None)`
  - `_draw_wind_zone_table(self, polygon: Polygon, entries: list -> None)`
  - `_draw_grid_section(self -> None)`
  - `draw_actions(self -> None)`
  - `_ensure_selected(self, polygons: list[Polygon] -> Polygon | None)`
  - `_handle_result(self, result: TransferResult -> None)`
  - `_engine(self)`
  - `_sync_preview(self -> None)`
  - `_clear_preview(self -> None)`
  - `_selected_frames_from_scene(self -> list[Frame])`
  - `_polygon_label(p: Polygon -> str)`

### `ui.panels.debug_panel`

Path: `ui/panels/debug_panel.py`

#### Classes

- **DebugPanel** (PanelBase) (line 10)
  - `draw_header(self -> None)`
  - `draw_settings(self -> None)`
  - `_draw_input(self, inp -> None)`
  - `_draw_context_sensitivity(self, eng -> None)`
  - `_draw_handlers(self, inp -> None)`
  - `_draw_tools(self, eng -> None)`
  - `_draw_bindings(self, inp -> None)`

### `ui.panels.definition_panel`

Path: `ui/panels/definition_panel.py`

#### Classes

- **DefinitionPanel** (PanelBase) (line 185)
  - `__init__(self, app=None, **overrides)`
  - `_on_draft_refreshed(self -> None)`
  - `_get_hints(self, cls -> dict[str, Any])`
  - `draw_content(self -> None)`
  - `_draw_type_selector(self)`
  - `_draw_toolbar(self, container, container_attr: str)`
  - `_draw_list(self, container)`
  - `_draw_editor(self, cls, container, project)`
  - `_commit_edit(self, container, name_key)`
  - `_draw_field(self, obj, f, hints, project -> bool)`
  - `_render_input(self, obj, name, tp, cur, project -> bool)`
  - `_render_enum(self, obj, name, tp, cur -> bool)`
  - `_render_dataclass_ref(self, obj, name, tp, cur, project -> bool)`
  - `_render_float_tuple(self, obj, name, args, cur -> bool)`
  - `_mark_unsupported(self, obj, name, tp, cur)`
  - `_draw_section_type_editor(self, section -> bool)`
  - `_draw_section_params(self, section -> bool)`
  - `_compute_section_props(self, section)`
  - `_find_container_by_type(self, cls, project -> dict | None)`
  - `_create_new(self)`
  - `_duplicate(self, container)`
  - `_select_existing(self, obj)`
  - `_draw_delete_confirm(self, container)`
  - `_draw_diagnostics(self)`
  - `_draw_material_name_with_catalog(self, material -> bool)`
  - `_draw_section_catalog_popup(self, section -> bool)`
  - `_draw_linkprop_type_editor(self, prop -> bool)`
  - `_draw_linkprop_dict(self, prop, name: str -> bool)`
  - `_select_by_section(self, section_name: str, target: str='frames')`
  - `_select_by_definition(self, cls, name: str, container_attr: str)`
  - `_draw_sd_section_summary(self, section -> bool)`
  - `_draw_rebar_dict(self, section, name: str -> bool)`
  - `_draw_time_dependent(self, section -> bool)`
  - `_draw_areasec_prop_type(self, sec -> bool)`
  - `_draw_constraint_type_editor(self, cd -> bool)`
  - `_draw_float_named(self, obj, name: str, label: str, step: float=1.0 -> bool)`
  - `_draw_bool_named(self, obj, name: str, label: str -> bool)`
  - `_draw_combination_items(self, combo -> bool)`
  - `_draw_sd_preview(self, sd, avail_w: float=280, avail_h: float=200)`
  - `_emit_commands(self -> None)`

#### Module Functions

- `_unique_name(container: dict, base: str -> str)`
- `_is_enum_type(tp -> bool)`
- `_is_union(origin -> bool)`
- `_strip_optional(tp)`
- `_name_attr(obj -> str)`

### `ui.panels.frame_load_panel`

Path: `ui/panels/frame_load_panel.py`

#### Classes

- **_DrawListAdapter** (line 15)
  - `__init__(self, draw_list)`
  - `add_rect_filled(self, x1, y1, x2, y2, color)`
  - `add_rect(self, x1, y1, x2, y2, color, rounding=0.0, flags=0, thickness=1.0)`
  - `add_line(self, x1, y1, x2, y2, color, thickness=1.0)`
  - `add_quad_filled(self, x1, y1, x2, y2, x3, y3, x4, y4, color)`
  - `add_circle_filled(self, x, y, radius, color)`
  - `add_circle(self, x, y, radius, color, num_segments=0, thickness=1.0)`
  - `add_text(self, x, y, color, text)`
- **FrameLoadPanel** (PanelBase) (line 57)
  - `__init__(self, app=None, **overrides)`
  - `_on_context_ready(self -> None)`
  - `open(self, **kw -> None)`
  - `close(self -> None)`
  - `set_target_frames(self, frames: list[Frame])`
  - `_load_from_target(self)`
    - Hedef frame'lerin ilkinden mevcut yükü yükle.
  - `_ensure_set_type(self, raw)`
    - dict gelirse FrameDistributedLoad'a çevir + segment'leri düzelt.
  - `_new_empty_set(self)`
  - `_ensure_default_segments(self)`
  - `draw_content(self -> None)`
  - `_draw_header(self)`
  - `_draw_load_settings(self)`
    - 2 satır halinde kompakt ayarlar.
  - `_draw_canvas(self)`
  - `_draw_grid(self, dl, ox, oy, cw, ch)`
  - `_q_to_y(self, q, oy, ch, beam_y)`
  - `_draw_segments(self, dl, ox, oy, cw, ch, beam_y)`
  - `_draw_axis_labels(self, dl, ox, oy, cw, ch)`
  - `_handle_canvas_input(self, ox, oy, cw, ch, beam_y, cpos, cend)`
  - `_find_nearest_handle(self, mouse, ox, oy, cw, ch, beam_y)`
  - `_drag_handle(self, seg_idx, side, mouse, ox, cw, oy, ch, beam_y)`
  - `_split_segment(self, idx, mouse, ox, cw)`
  - `_update_q_range(self)`
  - `_draw_segment_table(self)`
  - `_add_segment_after_selected(self)`
  - `_make_uniform(self)`
  - `_draw_actions(self)`
  - `_apply_to_frames(self -> None)`
  - `refresh_targets(self)`
    - Aktif seçimi sahne üzerinden yeniden oku.
  - `on_scene_selection_changed(self, selected)`
    - CadApp seçim değiştiğinde bunu çağırır (opsiyonel hook).

#### Module Functions

- `_color_u32(r, g, b, a=1.0)`

### `ui.panels.frame_preview_panel`

Path: `ui/panels/frame_preview_panel.py`

#### Classes

- **FramePreviewPanel** (BasePanel) (line 15)
  - Seçili frame'i bağımsız bir FBO'da shaded çizer.
  - `__init__(self, standard_shader=None)`
  - `set_context(self, ctx)`
  - `_load_frame(self, frame)`
  - `draw_content(self)`
  - `_render_scene(self)`
  - `close(self)`

### `ui.panels.grid_panel`

Path: `ui/panels/grid_panel.py`

#### Classes

- **GridPanel** (PanelBase) (line 12)
  - `__init__(self, app=None)`
  - `grid(self -> Grid | None)`
  - `renderer(self)`
  - `open(self, **kw)`
  - `_reset_draft(self)`
  - `_blank_oblique( -> dict)`
  - `draw_content(self)`
  - `_ortho_section(self)`
  - `_apply_ortho(self)`
  - `_oblique_section(self)`
  - `_add_oblique(self)`
  - `_label_section(self)`
  - `_dirty(self)`
  - `_f(v: float -> str)`
  - `_floats(text: str -> list[float])`
  - `_strs(text: str -> list[str])`
  - `_pairs(text: str -> list[tuple[float, float]])`

### `ui.panels.joint_load_panel`

Path: `ui/panels/joint_load_panel.py`

#### Classes

- **JointLoadPanel** (PanelBase) (line 25)
  - `__init__(self, app=None, **overrides)`
  - `_on_context_ready(self -> None)`
  - `draw_header(self -> None)`
  - `draw_settings(self -> None)`
  - `draw_table(self -> None)`
  - `draw_actions(self -> None)`
  - `_apply(self -> None)`
  - `_clear(self -> None)`
  - `_refresh_targets(self -> None)`
  - `on_scene_selection_changed(self, selected: list -> None)`

### `ui.panels.line_properties_panel`

Path: `ui/panels/line_properties_panel.py`

#### Classes

- **LinePropertiesPanel** (BasePanel) (line 12)
  - `__init__(self)`
  - `set_context(self, ctx: dict)`
  - `on_selection_changed(self, selected: list)`
  - `_lines(self -> list[Line])`
  - `_refresh(self)`
  - `_manager(self)`
  - `draw_content(self)`
  - `_toolbar(self)`
  - `_properties_single(self, ln: Line)`
  - `_properties_multi(self, items: list[Line])`
  - `_apply_batch(self, items: list[Line])`
  - `_line_style(self, ln: Line)`
  - `_endpoint_inputs(self, ln: Line)`
  - `_column_inputs(self, ln: Line)`
  - `_recompute_column(self, ln: Line)`
  - `_start_drawing(self)`
  - `_create_column(self)`
  - `_to_frame(self, ln: Line)`
  - `_to_link(self, ln: Line)`
  - `_delete(self, ln: Line)`

### `ui.panels.load_assign_panel`

Path: `ui/panels/load_assign_panel.py`

#### Classes

- **LoadAssignPanel** (PanelBase) (line 20)
  - `__init__(self, app=None, **overrides)`
  - `_on_context_ready(self -> None)`
  - `draw_header(self -> None)`
  - `draw_settings(self -> None)`
  - `draw_table(self -> None)`
  - `_draw_existing_assignments_table(self -> None)`
  - `draw_actions(self -> None)`
  - `_load_presets(self -> None)`
  - `_matching_patterns(self, load_type: str -> list[str])`
  - `_sync_pattern_choices(self -> None)`
  - `_available_default_name(self, load_type: str, base_name: str -> str)`
  - `_draw_pattern_selector(self, load_type: str, label: str -> None)`
  - `_ensure_pattern(self, load_type: str -> str)`
  - `_apply_selected_presets(self -> int)`

### `ui.panels.load_display_panel`

Path: `ui/panels/load_display_panel.py`

#### Classes

- **LoadDisplayPanel** (PanelBase) (line 12)
  - `__init__(self, app=None, **overrides)`
  - `_on_context_ready(self -> None)`
  - `set_loads_visible(self, enabled: bool, renderer=None, math_model=None -> None)`
  - `draw_settings(self -> None)`
  - `draw_table(self -> None)`
  - `draw_actions(self -> None)`
  - `_refresh_patterns(self -> None)`
  - `_count_pattern_usage(self, pattern: str -> int)`
  - `_apply(self -> None)`

### `ui.panels.load_manager_panel`

Path: `ui/panels/load_manager_panel.py`

#### Classes

- **_PatternSubPanel** (line 17)
  - Load Manager → Pattern'lar sekmesi. Gömülü — kendi draft'ı yok.
  - `__init__(self)`
  - `set_queue(self, queue -> None)`
  - `set_context(self, project -> None)`
  - `draw_content(self -> None)`
  - `_draw_pattern_table(self -> None)`
  - `_draw_add_form(self -> None)`
  - `_add_pattern(self, name: str, type_idx: int -> None)`
  - `_count_pattern_usage(self, pattern: str -> int)`
  - `section_label(text: str -> None)`
- **LoadManagerPanel** (PanelBase) (line 201)
  - `__init__(self, app=None, **overrides)`
  - `_on_context_ready(self -> None)`
  - `draw_content(self -> None)`
  - `_draw_sub_panel(self, sub_panel -> None)`

### `ui.panels.material_panel`

Path: `ui/panels/material_panel.py`

#### Classes

- **MaterialPanel** (PanelBase) (line 12)
  - `__init__(self, app=None, **overrides)`
  - `_on_draft_refreshed(self -> None)`
  - `draw_header(self -> None)`
  - `draw_settings(self -> None)`
  - `_draw_editor(self, container: dict -> None)`
  - `draw_actions(self -> None)`
  - `_draw_delete_confirm(self -> None)`
  - `_create_new(self -> None)`
  - `_duplicate(self, container: dict -> None)`
  - `_select_existing(self, mat: Material -> None)`
  - `_commit_edit(self, container: dict -> None)`
  - `_emit_commands(self -> None)`

### `ui.panels.polygon_properties_panel`

Path: `ui/panels/polygon_properties_panel.py`

#### Classes

- **PolygonPropertiesPanel** (PanelBase) (line 21)
  - `__init__(self, app=None, **overrides)`
  - `_on_context_ready(self -> None)`
  - `_update_context_pick_handler(self)`
  - `open(self, polygon: Polygon | None=None -> None)`
  - `close(self -> None)`
  - `on_selection_changed(self, selected: list)`
  - `_refresh(self, selected: list)`
  - `_sync_from_selection(self)`
  - `_polygons(self -> list[Polygon])`
  - `_refresh_polygons(self)`
  - `_load_presets(self)`
  - `_matching_patterns(self, load_type: str -> list[str])`
  - `_sync_pattern_choices(self)`
  - `draw_content(self)`
  - `_ensure_draft(self, p: Polygon)`
  - `_draw_single_polygon_ui(self, p: Polygon)`
  - `_draw_tab_geometry(self, p: Polygon)`
  - `_draw_tab_assoc(self, p: Polygon)`
  - `_draw_tab_loads(self, p: Polygon)`
  - `_apply_single_load(self, polygon: Polygon, analysis_data, preset_item: dict)`
    - Seçili pattern + preset + editbox değeri ile tek yük ata.
  - `_draw_pattern_selector(self, load_type: str, label: str)`
  - `_apply_selected_presets(self, polygon: Polygon)`
  - `_draw_tab_zones(self, p: Polygon)`
  - `_draw_multi_polygon_ui(self, items: list[Polygon])`
  - `_engine(self)`
  - `_sync_preview(self)`
  - `_is_assoc_edit_mode(self -> bool)`
  - `_viewport_assoc_click(self, x, y, button -> bool)`
    - Panel assoc modunda viewport tıklaması → frame toggle.
  - `_clear_preview(self)`

### `ui.panels.project_panels`

Path: `ui/panels/project_panels.py`

#### Classes

- **AnalysisManagerPanel** (BasePanel) (line 18)
  - Analiz yöneticisi — thread'li çalıştırma + hata bandı + progress.
  - `__init__(self)`
  - `open(self)`
  - `close(self)`
  - `set_context(self, ctx: dict)`
  - `_project(self)`
  - `_scene(self)`
  - `_refresh_spectrum_list(self)`
  - `_run_analysis(self)`
  - `_poll_result(self)`
  - `draw(self)`
  - `_draw_options(self)`
  - `_draw_error_banner(self)`
  - `_draw_results(self)`
  - `_draw_results(self)`
  - `_draw_tab_genel(self)`
  - `_draw_tab_kütle(self)`
  - `_draw_tab_modal(self)`
  - `_draw_tab_spectral(self)`
  - `_draw_tab_metraj(self)`
- **ReportPanel** (BasePanel) (line 533)
  - `__init__(self)`
  - `open(self, rep=None)`
- **ProjectInfoPanel** (BasePanel) (line 543)
  - `__init__(self)`
  - `open(self, info=None, general_info=None, site_info=None, on_apply=None)`
  - `draw_content(self)`
  - `_field(self, label, attr, obj)`
  - `_field_float(self, label, attr, obj)`
- **ProjectConfigPanel** (BasePanel) (line 621)
  - `__init__(self)`
  - `open(self, config=None, on_apply=None)`
  - `draw_content(self)`
  - `_float(self, label, obj, attr, step=0.1)`
  - `_combo(self, label, obj, attr, choices)`

### `ui.panels.project_settings_panel`

Path: `ui/panels/project_settings_panel.py`

#### Classes

- **ProjectSettingsPanel** (BasePanel) (line 11)
  - Sol tarafta ağaç menüsü, sağ tarafta seçilen config/bilgi düzenleyicisi olan merkezi panel.
  - `__init__(self)`
  - `set_context(self, ctx: dict -> None)`
  - `draw_content(self)`
  - `_draw_general_info_form(self, g)`
  - `_draw_site_info_form(self, s)`
  - `_draw_metadata_form(self, i)`
  - `_draw_wind_config_form(self, w)`
  - `_draw_snow_config_form(self, s)`
  - `_draw_seismic_config_form(self, e)`
  - `_field(self, label, obj, attr)`
  - `_field_float(self, label, obj, attr, step=0.1)`
  - `_field_int(self, label, obj, attr, step=1)`
  - `_combo(self, label, obj, attr, choices)`
  - `_dict_float(self, label, d, key, step=0.01)`

### `ui.panels.render_settings_panel`

Path: `ui/panels/render_settings_panel.py`

#### Classes

- **RenderSettingsPanel** (BasePanel) (line 12)
  - `__init__(self)`
  - `set_context(self, ctx: dict)`
  - `_sync(self)`
  - `open(self)`
  - `close(self)`
  - `draw(self)`
  - `_draw(self)`
  - `_draw_render_mode(self)`
  - `_draw_visibility(self)`
  - `_draw_grid(self)`
  - `_draw_polygon_style(self)`
  - `_draw_nodes(self)`
  - `_draw_global_axis(self)`
  - `_draw_local_axes(self)`
  - `_draw_lighting(self)`
  - `_draw_plane_preview(self)`
  - `_draw_debug(self)`
  - `_refresh(self)`

### `ui.panels.report_panel`

Path: `ui/panels/report_panel.py`

#### Classes

- **ReportPanel** (PanelBase) (line 17)
  - `__init__(self, app=None)`
  - `_on_context_ready(self)`
  - `open(self, rep=None)`
  - `_generate_default_reports(self, project -> None)`
    - Mevcut proje geometrisi ve rüzgar verilerinden WindSceneAdapter kullanarak güvenli şekilde rapor üretir.
  - `draw_content(self)`

### `ui.panels.s2k_panel`

Path: `ui/panels/s2k_panel.py`

... (docstring aynı) ...

#### Classes

- **S2KPanel** (PanelBase) (line 30)
  - S2K import ve export'u tek arayüzde birleştirir.
  - `__init__(self, app=None, on_import_complete: Callable[[Project], None] | None=None, get_project: Callable[[], Project | None] | None=None, get_selected_elements: Callable[[], list] | None=None)`
  - `_on_context_ready(self)`
  - `open(self, mode: str | None=None, file_path: str | None=None)`
  - `close(self)`
  - `_log_info(self, msg: str)`
  - `_log_warn(self, msg: str)`
  - `_log_error(self, msg: str)`
  - `_open_import_dialog(self)`
  - `_open_export_dialog(self)`
  - `_load_import_file(self, file_path: str)`
    - S2K dosyasını parse et, tablo listesini hazırla.
  - `_execute_import(self)`
  - `_run_handlers(self -> LoadContext)`
    - Seçili tabloları sıralı + kalan router ile ctx'ye aktar.
  - `_should_process(self, name: str -> bool)`
  - `_apply_handler(self, ctx: LoadContext, name: str, df: pd.DataFrame, handler)`
  - `_set_export_path(self, file_path: str)`
  - `_resolve_project(self -> Project | None)`
  - `_resolve_selected(self -> list)`
  - `_build_export_text(self -> bool)`
  - `_parse_table_summary(text: str -> list[tuple])`
    - TABLO: "NAME" başlıklarını ve satır sayılarını çıkar.
  - `_write_export_file(self)`
  - `draw(self)`
  - `_draw_mode_selector(self)`
  - `_draw_import_ui(self)`
  - `_draw_export_ui(self)`
  - `_draw_log_area(self)`

### `ui.panels.sd_convert_panel`

Path: `ui/panels/sd_convert_panel.py`

SD Section → Area Dönüşüm Paneli.

Akış:
  1. Seçili SD frame'i tespit et
  2. "Area'ya Çevir" → sd_frame_to_areas ile area listesi üret (sahneye EKLEME)
  3. 2D canvas'ta önizleme (tıkla-seç, Ctrl ile çoklu seçim)
  4. Seçili / tümünü sil
  5. "Modele Aktar" → önce node'lar, sonra area'lar sahneye eklenir

#### Classes

- **SDConvertPanel** (BasePanel) (line 71)
  - `__init__(self)`
  - `open(self)`
  - `close(self)`
  - `_clear_preview(self)`
  - `_get_target_frame(self -> Frame | None)`
  - `_is_sd_frame(frame: Frame -> bool)`
  - `_get_polygon(frame: Frame)`
  - `draw(self)`
  - `_draw_panel_content(self, expanded: bool, opened: bool)`
  - `_draw_source_ui(self)`
  - `_draw_preview_ui(self)`
  - `_draw_source_polygon_2d(self, poly)`
  - `_draw_edges_canvas(self)`
  - `_ctrl_pressed(self -> bool)`
    - Ctrl basılı mı? key_ctrl yerine keys_down (daha güvenilir).
  - `_convert_edges_and_commit(self)`
    - Seçili kenarları Area'ya çevir ve doğrudan sahneye aktar.
  - `_hit_test_area_screen(self, mx: float, my: float, p0: tuple[float, float], scale: float, cx: float, cy: float -> Area | None)`
    - Ekran noktası → hangi area?
  - `_build_preview(self, frame: Frame)`
  - `_refresh_preview_nodes(self)`
    - Area silindikten sonra paylaşılan node listesini yeniden hesapla.
  - `_commit_to_scene(self)`
  - `_draw_polygon_or_areas(self, point_list, is_preview=False)`
    - Basit polygon önizlemesi (kaynak için).

#### Module Functions

- `_dist_point_segment(p, a, b)`
- `_node_key(nd: Node -> tuple[float, float, float])`
  - Aynı 3D konumdaki node'ları birleştirmek için anahtar.
- `_dedupe_area_nodes(areas: list[Area] -> list[Node])`
  - Aynı konumdaki node'ları tek Node nesnesine indirger.
- `_color_u32(r: float, g: float, b: float, a: float=1.0 -> int)`
- `_point_in_polygon(p: tuple[float, float], poly: list[tuple[float, float]] -> bool)`
  - Ray-casting nokta-in-polygon testi.

### `ui.panels.selection_panel`

Path: `ui/panels/selection_panel.py`

#### Classes

- **SelectionPanel** (PanelBase) (line 20)
  - `__init__(self, app=None, **overrides)`
  - `draw_content(self -> None)`
  - `_draw_status(self, sm -> None)`
  - `_draw_basic_actions(self, sm -> None)`
  - `_draw_mode_info(self -> None)`
  - `_draw_saved_sets(self, sm -> None)`
  - `_draw_undo_redo(self, sm -> None)`
  - `_draw_visibility_actions(self -> None)`

### `ui.panels.test_panel`

Path: `ui/panels/test_panel.py`

#### Classes

- **TestPanel** (PanelBase) (line 9)
  - `__init__(self, app=None, **overrides)`
  - `draw_header(self -> None)`
  - `draw_settings(self -> None)`
  - `_draw_editor(self, container: dict -> None)`

### `ui.panels.view_filter_panel`

Path: `ui/panels/view_filter_panel.py`

ViewFilterPanel — Kamera + Görünüm Aralığı (aktif UCS'ye göre).

#### Classes

- **ViewFilterPanel** (PanelBase) (line 12)
  - `__init__(self, app=None, on_apply: Callable | None=None)`
  - `open(self, camera=None)`
  - `draw_content(self)`
  - `_draw_camera_group(self)`
  - `_draw_projection_group(self)`
  - `_draw_view_presets_group(self)`
  - `_draw_section_group(self)`
  - `_input_float(label: str, value: float, step: float=0.1)`
  - `_apply_preset(self)`
  - `_apply_section(self)`

### `ui.panels.visibility_panel`

Path: `ui/panels/visibility_panel.py`

VisibilityPanel — PanelBase türevi. Sahne elemanlarını tip bazlı gruplarla listeler.

#### Classes

- **VisibilityPanel** (PanelBase) (line 10)
  - `__init__(self, app=None, on_apply=None)`
  - `open(self, scene=None)`
  - `close(self)`
  - `has_changes(self -> bool)`
  - `apply_changes(self)`
  - `draw_content(self)`
  - `_draw_groups(self)`
  - `_draw_group_header(self, display_name, coll_name, items, force_open=False, disabled=False)`
  - `_draw_element_row(self, el)`
  - `_current_visibility(self, el -> bool)`
  - `_set_all(self, state: bool)`

### `ui.panels.wind_analysis_panel`

Path: `ui/panels/wind_analysis_panel.py`

Rüzgar analiz paneli — surface seç + yön + zone oluştur ve sonuçları görselleştir.

#### Classes

- **WindAnalysisPanel** (PanelBase) (line 19)
  - `__init__(self, app=None, **overrides)`
  - `has_pending_changes(self -> bool)`
    - Projedeki wind zone'larından farklı bir şey var mı?
  - `_snapshot_wind_data(self -> dict)`
  - `on_apply_action(self -> None)`
    - Zone değişiklikleri zaten projede; sadece snapshot güncelle.
  - `on_reset_action(self -> None)`
    - Analizi tamamen temizle.
  - `set_context(self, ctx: dict -> None)`
  - `open(self, **kw -> None)`
  - `close(self -> None)`
  - `_project(self)`
  - `_get_engine(self)`
  - `_apply_math_preview(self, active: bool -> None)`
  - `draw_content(self -> None)`
  - `_reset_analysis(self)`
  - `_draw_surface_selection(self)`
  - `_draw_directions(self)`
  - `_remove_direction(self, key: str)`
  - `_wind_state(self -> dict)`
  - `_add_default_direction(self)`
  - `_run_analysis_all(self)`
  - `_assign_zones_to_polygons(self, zones, surfaces, dir_key)`
  - `_draw_zone_editor_table(self)`
  - `_open_wind_report_table(self, dir_rec, target_key: str)`

### `ui.registry`

Path: `ui/registry.py`

#### Classes

- **PanelSpec** (line 10)

#### Module Functions

- `discover_panels(package -> list['PanelSpec'])`
- `validate(specs: list, actions: list -> None)`

### `ui.ui_host`

Path: `ui/ui_host.py`

#### Classes

- **UIHost** (line 53)
  - ImGui frame, dock space, panel yönetimi, event bridge.
  - `__init__(self, app: CadApp)`
  - `on_panel_applied(self, panel -> None)`
    - Panel Apply'a bastı. Kuyruğa sadece bir 'geometry refresh' at.
  - `on_engine_ready(self -> None)`
    - Engine hazır olduğunda çağrılır.
  - `on_selection_changed(self, selected: list -> None)`
  - `on_wind_analysis_done(self, key: str -> None)`
  - `on_unit_changed(self -> None)`
  - `_init_registry(self -> None)`
  - `get_panel(self, name: str)`
  - `prepare_panel(self, name: str, panel -> None)`
  - `_resolve_context(self, keys: list[str] -> dict)`
  - `toggle_panel(self, name: str -> None)`
  - `open_panel(self, name: str, **kwargs -> None)`
  - `frame(self, dt: float -> None)`
  - `_reset_gl_state_for_imgui(self -> None)`
  - `_draw_panels(self -> None)`
  - `_draw_dock_space(self -> None)`
  - `_forward_active_viewport_events(self -> None)`
  - `_forward_imgui_events(self, panel -> None)`
  - `_any_viewport_active(self -> bool)`
  - `_forward_keys(self, eng -> None)`
  - `_sync_input_state(eng, io, item_hovered: bool -> None)`
  - `toggle_draw(self, sender=None)`
  - `toggle_plane(self)`
  - `toggle_local_axes(self)`
  - `toggle_loads(self)`
  - `open_viewport(self, preset: str)`
  - `close_all_viewports(self)`
  - `_consume_plane_completion(self)`
  - `open_open_dialog(self)`
  - `open_save_dialog(self)`
  - `_build_view_menu(self)`
  - `_toggle_row(self, label: str, key: str, current: bool -> None)`
  - `close_app(self -> None)`
  - `open_s2k_import(self -> None)`
  - `open_s2k_export(self -> None)`
  - `start_plane_3pt(self -> None)`
  - `start_plane_2pt_z(self -> None)`
  - `open_plane_source_dialog(self -> None)`
  - `toggle_view_2d(self -> None)`
  - `shutdown(self -> None)`
  - `on_viewport_panel_closed(self, panel -> None)`
  - `_draw_marquee_overlays(self -> None)`
  - `reset_all(self -> None)`
    - Tüm sistemi (yeni proje, paneller, viewport'lar) sıfırdan kurar.
  - `on_project_changed(self -> None)`
  - `get_interaction_debug_info(self -> dict)`
    - Debug panel için anlık UI ve Viewport etkileşim bağlamını döndürür.
  - `on_hover_changed(self, element_id: int -> None)`

### `ui.widgets.base_panel`

Path: `ui/widgets/base_panel.py`

#### Classes

- **BasePanel** (line 5)
  - Tüm panellerin ortak tabanı — Dinamik başlık ve sabit status bar destekli.
  - `__init__(self, title: str='Panel', width: float=420.0, height: float=480.0, pos_first_use: tuple[float, float]=(100.0, 100.0), **kwargs)`
  - `open(self, **kwargs)`
  - `close(self)`
  - `set_context(self, ctx: dict)`
  - `set_title(self, title: str)`
    - Pencere başlığını dinamik olarak değiştirir.
  - `set_status(self, text: str, kind: str='info')`
    - Durum çubuğuna mesaj yazar (info, success, warning, error).
  - `draw(self)`
  - `draw_content(self)`
    - Alt sınıf override eder.

### `ui.widgets.color_picker`

Path: `ui/widgets/color_picker.py`

Renk editörü widget'ı.
- imgui.color_edit3 ile popup renk seçici
- Hızlı erişim için 12 renkli palet
- Tuple[float, float, float] formatında çalışır

#### Module Functions

- `color_edit3(label: str, color, palette=DEFAULT_PALETTE, show_popup: bool=True, expanded: bool=False)`

### `ui.widgets.file_dialog`

Path: `ui/widgets/file_dialog.py`

#### Classes

- **_Entry** (line 16)
- **ImGuiFileDialog** (line 22)
  - Basit ImGui dosya seçici.
  - `__init__(self -> None)`
  - `open(self, mode: Mode='open', filters: list[str] | None=None, title: str='Dosya Seç', initial_dir: str | None=None, default_name: str='', on_select: Callable[[str], None] | None=None, on_cancel: Callable[[], None] | None=None -> None)`
  - `close(self, cancelled: bool=False -> None)`
    - Pencereyi kapat. `cancelled=True` ise `on_cancel` tetiklenir.
  - `draw(self -> None)`
  - `_draw_dir_bar(self -> None)`
  - `_draw_entry_list(self -> None)`
  - `_draw_footer(self -> None)`
  - `_navigate_to(self, path: str -> None)`
  - `_confirm(self -> None)`
  - `_matches_filter(self, name: str -> bool)`
  - `_refresh_entries(self -> None)`

### `ui.widgets.icon_manager`

Path: `ui/widgets/icon_manager.py`

#### Classes

- **IconManager** (line 13)
  - `__init__(self -> None)`
  - `get_texture(self, icon_name)`

### `ui.widgets.plane_2d_loads`

Path: `ui/widgets/plane_2d_loads.py`

2D view'da yük gösterim katmanı.

#### Classes

- **LoadOverlay** (line 12)
  - Frame/node/area yüklerini 2D view'da çizer.
  - `__init__(self)`
  - `draw(self, dl, plane, scene, frame_map, node_map, to_screen, selected_set, hover)`
  - `_draw_frame_loads(self, dl, plane, frame_map, to_screen, selected, hover)`
  - `_draw_dist_segment(self, dl, p0, p1, seg, col, plane, load_set)`
    - Bir yayılı yük segmenti — trapezoid + oklar.
  - `_draw_arrow(self, dl, base, tip, col, head_size=4.0)`
    - Ok başı çiz.
  - `_draw_node_loads(self, dl, plane, node_map, to_screen, selected, hover)`
  - `_alpha(col, a)`
    - ABGR → alfa azalt.
  - `_draw_text(self, dl, screen_pos, text, col)`

### `ui.widgets.plane_2d_tools`

Path: `ui/widgets/plane_2d_tools.py`

#### Classes

- **ToolKind** (Enum) (line 11)
- **ToolContext** (line 24)
- **Tool** (Protocol) (line 32)
  - `on_click(self, ctx: ToolContext, scene, plane -> bool)`
  - `on_move(self, ctx: ToolContext, scene, plane -> None)`
  - `on_right_click(self, ctx: ToolContext -> None)`
  - `draw_preview(self, dl, to_screen, ctx: ToolContext -> None)`
  - `draw_ui(self, plane, scene -> None)`
  - `cancel(self -> None)`
  - `is_active(self -> bool)`
- **PlaceDistLoadTool** (line 48)
  - Frame yayılı yük yerleştir.
  - `on_click(self, ctx: ToolContext, scene, plane -> bool)`
    - Frame'e tıkla → pending olarak işaretle.
  - `on_move(self, ctx: ToolContext, scene, plane -> None)`
  - `on_right_click(self, ctx: ToolContext -> None)`
    - Sağ tık — formu sıfırla.
  - `is_active(self -> bool)`
  - `cancel(self -> None)`
  - `draw_preview(self, dl, to_screen, ctx: ToolContext -> None)`
    - Seçili frame üzerine önizleme trapezoid çiz.
  - `draw_ui(self, plane, scene -> None)`
    - Panelde gösterilecek form — aktif olduğunda.
  - `_apply_to_frame(self, frame, scene -> None)`
  - `_reset_form(self -> None)`
  - `set_patterns(self, patterns: list[str] -> None)`
    - Panelden doldurulur — projede tanımlı pattern'lar.

### `ui.widgets.plane_2d_view`

Path: `ui/widgets/plane_2d_view.py`

Plane2DView — Plane üzerindeki assoc elemanları 2D canvas'ta gösterir.

- Koordinat sistemi: plane.to_2d / plane.to_3d
- View rotasyonu (orthogonal, sadece görüntü)
- Pan / zoom
- Seçim (node / frame / poly / area / link)
- Pending ADD draft'ları sarı kesikli (henüz çizim araçları yok, sadece görsel)

Model verisine YAZMAZ.

#### Classes

- **Plane2DView** (line 32)
  - `__init__(self)`
  - `_get_mods(self)`
  - `_is_over_canvas(mx, my, cx, cy, cw, ch -> bool)`
  - `selected(self)`
    - sel_mgr varsa oradan oku, yoksa kendi set'inden.
  - `selected(self, value)`
    - Panel eski koddan set ediyorsa — geri uyumluluk için.
  - `bind_selection(self, sel_mgr)`
    - Sahne sel_mgr'sini bağla.
  - `_uid_to_kind(self, uid -> str | None)`
    - unique_id → kind. Scene'deki 5 dict'ten türet.
  - `_kind_id_to_element(self, kind, eid)`
  - `load_plane(self, plane: Plane, scene, project=None)`
  - `refresh(self)`
  - `rotate_view(self, delta_deg: float, absolute=False)`
  - `zoom_at_center(self, factor: float)`
  - `fit_to_content(self, view_w=800.0, view_h=500.0, margin=0.85)`
  - `reset_view(self)`
  - `_compute_bounds(self)`
  - `_iter_assoc_ids(self)`
    - (kind, id) — assoc'takiler (excluded değil).
  - `_iter_excluded_ids(self)`
  - `_iter_pending_add_ids(self)`
    - (kind, id, data) — pending ADD draft'ları.
  - `_element_uvs(self, kind: str, eid -> list[tuple[float, float]])`
    - Bir elemanın 2D noktaları (assoc veya excluded).
  - `_points_3d_of(el, kind: str -> list[np.ndarray])`
  - `_factory(self, cx, cy, cw, ch)`
  - `draw(self, imgui_ctx, draw_list, canvas_pos, canvas_size)`
  - `_draw_background(self, dl, cx, cy, cw, ch)`
  - `_draw_all_elements(self, dl, to_screen)`
  - `_draw_rubber(self, dl)`
  - `_draw_load_overlay(self, dl, to_screen)`
  - `_draw_annotations(self, dl, to_screen)`
  - `_draw_measurements(self, dl, to_screen)`
  - `_draw_active_tool(self, dl, imgui_ctx, to_screen, from_screen, cx, cy, cw, ch)`
  - `set_tool(self, kind: ToolKind, **kwargs)`
  - `_draw_tool_preview(self, dl, to_screen, ctx)`
    - Aktif tool'un canlı preview'ı.
  - `_compute_snap(self, uv_mouse, to_screen -> tuple[float, float])`
    - Snap: node > midpoint > grid > ham uv.
  - `_current_grid_step(self -> float)`
    - Grid adımını döndür (zoom'a göre).
  - `_draw_grid(self, dl, cx, cy, cw, ch, to_screen, from_screen)`
  - `_draw_axes(self, dl, to_screen)`
  - `_draw_element(self, dl, kind: str, eid, to_screen, mode='assoc')`
  - `_draw_draft(self, dl, kind: str, eid: str, data: dict, to_screen)`
    - Pending ADD draft'ları — sarı, kesikli/özel.
  - `_handle_input(self, imgui_ctx, cx, cy, cw, ch, to_screen, from_screen)`
  - `_finish_rubber(self, to_screen)`
  - `_apply_zoom(self, wheel, mx, my, cx, cy, cw, ch)`
  - `_hit_test(self, mx, my, to_screen)`
  - `_is_space(imgui_ctx)`
  - `_is_over_canvas(mx, my, cx, cy, cw, ch -> bool)`
  - `_make_tool_context(self, imgui_ctx, cx, cy, cw, ch, to_screen, from_screen)`
    - Aktif tool için ToolContext üret. Canvas dışındaysa uv/snap None.

#### Module Functions

- `_rot(v, deg)`
- `_dist_point_segment(p, a, b)`
- `_point_in_polygon(point, vertices)`
- `_segment_intersects_rect(a, b, rect)`
- `_element_intersects_rect(kind, points, rect)`

### `ui.widgets.toolbar`

Path: `ui/widgets/toolbar.py`

#### Classes

- **Toolbar** (line 23)
  - `__init__(self, commands: dict[str, Callable], panel_states: dict[str, Callable[[], bool]], specs: list[Any] | None=None, categories: list[str] | None=None, extra_menus=None -> None)`
  - `_compose_buckets(self -> dict[str, list])`
  - `set_specs(self, specs: list[Any], categories: list[str] | None=None -> None)`
  - `draw(self, model_text: str='', current_unit=None, project=None -> None)`
  - `_draw_menus(self -> None)`
  - `_draw_menu_item(self, spec: Any -> None)`
  - `_draw_quick_icons(self -> None)`
  - `_state(self, key: str -> bool)`
  - `_icon(self, name: str | None -> int | None)`
  - `_draw_unit_selector(self -> None)`
  - `_draw_model_label(self -> None)`

#### Module Functions

- `_tex_ref(tex_id: int)`
- `_v4(r, g, b, a=1.0)`
- `_vec2(x, y)`

### `viewport`

Path: `viewport/__init__.py`

### `viewport.viewport`

Path: `viewport/viewport.py`

#### Classes

- **Viewport** (line 17)
  - Bağımsız kamera + FBO. Renderer'lar ortaktır (VAO paylaşımı).
  - `__init__(self, name: str, width: int=640, height: int=480, camera: Camera | None=None)`
  - `resize(self, w: int, h: int)`
  - `bind(self)`
  - `unbind(self)`
  - `texture_id(self -> int)`
  - `pick_at(self, pick_pass, x_px: int, y_px: int)`
    - FBO'nun ID attachment'ından piksel oku → element döndür.
  - `pick_rect(self, pick_pass, x0, y0, x1, y1 -> list)`
    - Kutu içindeki elementleri döndürür (filter'a tabi).
  - `pick_at_neighborhood(self, pick_pass, x_px: int, y_px: int, radius: int=3)`
    - Merkez piksel etrafındaki en yakın elementi döndür.
  - `set_element_filter(self, query)`
    - Element filtresini ayarla. None → filtreyi kaldır.
  - `invalidate_visible_ids(self)`
  - `cleanup(self)`

### `viewport.viewport_manager`

Path: `viewport/viewport_manager.py`

#### Classes

- **ViewportManager** (line 10)
  - Eşit viewport'lar. "Ana" yok. Tüm viewport'lar `engine` renderer'larını paylaşır.
  - `__init__(self, engine)`
  - `create_viewport(self, name=None, width=640, height=480, preset: str | None=None, plane=None -> Viewport)`
  - `next_name(self, base: str -> str)`
    - 'top 2', 'top 3' gibi çakışmayan isim üretir.
  - `remove_viewport(self, name: str -> bool)`
  - `get(self, name: str -> Viewport | None)`
  - `active(self -> Viewport | None)`
  - `set_active(self, name: str -> None)`
  - `_ensure_visible_ids(self, vp -> None)`
  - `render_all(self -> None)`
  - `invalidate_all_visible_ids(self -> None)`
  - `cleanup(self)`

### `viewport.viewport_panel`

Path: `viewport/viewport_panel.py`

#### Classes

- **ViewportPanel** (line 13)
  - `__init__(self, host: 'UIHost', viewport_name: str, manager: 'ViewportManager' -> None)`
  - `draw(self -> None)`
  - `_draw_image(self, vp -> None)`
  - `_close(self -> None)`

## Internal Dependencies

- `app.cad_app` → `core.units`
- `app.cad_app` → `core.units`
- `app.cad_app` → `domain.definition`
- `app.cad_app` → `domain.definition`
- `app.cad_app` → `domain.project`
- `app.cad_app` → `domain.project`
- `app.cad_app` → `tools.wind_manager`
- `app.cad_app` → `logging_config`
- `app.cad_window` → `logging_config`
- `app.commands.camera` → `app.commands.result`
- `app.commands.camera` → `core.commands.project_commands`
- `app.commands.definitions` → `core.commands.project_commands`
- `app.commands.definitions` → `app.commands.result`
- `app.commands.elements` → `app.commands.result`
- `app.commands.elements` → `core.commands.project_commands`
- `app.commands.engine_flags` → `app.commands.result`
- `app.commands.engine_flags` → `core.commands.project_commands`
- `app.commands.project` → `app.commands.result`
- `app.commands.project` → `core.commands.project_commands`
- `app.commands.registry` → `core.commands.base`
- `app.commands.registry` → `app.commands.result`
- `app.commands.selection` → `app.commands.result`
- `app.commands.selection` → `core.commands.project_commands`
- `app.commands.signals` → `app.commands.result`
- `app.commands.signals` → `core.commands.project_commands`
- `app.commands.visibility` → `app.commands.result`
- `app.commands.visibility` → `core.commands.project_commands`
- `app.input_bindings` → `core.commands.project_commands`
- `core.analysis` → `core.analysis.mass_assembly`
- `core.analysis` → `core.analysis.mass_assembly`
- `core.analysis` → `core.analysis.mass_assembly`
- `core.analysis` → `core.analysis.material_takeoff`
- `core.analysis` → `core.analysis.material_takeoff`
- `core.analysis` → `core.analysis.solver`
- `core.analysis` → `core.analysis.solver`
- `core.analysis` → `core.analysis.stiffness_assembly`
- `core.analysis` → `core.analysis.stiffness_assembly`
- `core.analysis` → `core.analysis.stiffness_assembly`
- `core.analysis` → `core.analysis.stiffness_assembly`
- `core.analysis` → `core.analysis.structuralanalysis`
- `core.analysis` → `core.analysis.structuralanalysis`
- `core.analysis.mass_assembly` → `core.analysis.stiffness_assembly`
- `core.analysis.mass_assembly` → `core.units`
- `core.analysis.mass_assembly` → `core.units`
- `core.analysis.mass_assembly` → `domain.definition`
- `core.analysis.mass_assembly` → `logging_config`
- `core.analysis.material_takeoff` → `core.units`
- `core.analysis.material_takeoff` → `core.units`
- `core.analysis.material_takeoff` → `domain.element`
- `core.analysis.material_takeoff` → `domain.element`
- `core.analysis.material_takeoff` → `domain.math_model`
- `core.analysis.material_takeoff` → `logging_config`
- `core.analysis.modal_analysis` → `core.units`
- `core.analysis.modal_analysis` → `core.analysis.solver`
- `core.analysis.run` → `core.analysis.material_takeoff`
- `core.analysis.run` → `core.analysis.material_takeoff`
- `core.analysis.run` → `core.analysis.modal_analysis`
- `core.analysis.run` → `core.analysis.structuralanalysis`
- `core.analysis.run` → `core.analysis.structuralanalysis`
- `core.analysis.spectrum` → `logging_config`
- `core.analysis.structuralanalysis` → `core.analysis.mass_assembly`
- `core.analysis.structuralanalysis` → `core.analysis.mass_assembly`
- `core.analysis.structuralanalysis` → `core.analysis.solver`
- `core.analysis.structuralanalysis` → `core.analysis.solver`
- `core.analysis.structuralanalysis` → `core.analysis.stiffness_assembly`
- `core.analysis.structuralanalysis` → `core.analysis.stiffness_assembly`
- `core.analysis.structuralanalysis` → `core.analysis.unit_guard`
- `core.analysis.unit_guard` → `core.units`
- `core.analysis.unit_guard` → `core.units`
- `core.analysis.validation` → `core.units`
- `core.camera` → `logging_config`
- `core.camera_controller` → `core.input_manager`
- `core.camera_controller` → `core.input_manager`
- `core.camera_controller` → `core.input_manager`
- `core.commands` → `core.commands.base`
- `core.commands` → `core.commands.base`
- `core.commands` → `core.commands.bulk_update`
- `core.commands` → `core.commands.create`
- `core.commands` → `core.commands.delete`
- `core.commands` → `core.commands.update`
- `core.commands.base` → `logging_config`
- `core.commands.bulk_update` → `core.commands.base`
- `core.commands.bulk_update` → `logging_config`
- `core.commands.create` → `core.commands.base`
- `core.commands.create` → `logging_config`
- `core.commands.delete` → `core.commands.base`
- `core.commands.delete` → `logging_config`
- `core.commands.update` → `core.commands.base`
- `core.commands.update` → `logging_config`
- `core.edit.edit_controller` → `core.commands`
- `core.edit.edit_controller` → `core.commands`
- `core.edit.edit_controller` → `core.commands`
- `core.edit.edit_controller` → `core.commands`
- `core.edit.edit_controller` → `core.commands`
- `core.edit.edit_controller` → `logging_config`
- `core.engine` → `core.input_manager`
- `core.engine` → `core.engine.gl_context`
- `core.engine` → `core.engine.renderer_pipeline`
- `core.engine` → `core.engine.camera_rig`
- `core.engine` → `core.engine.hover_system`
- `core.engine` → `core.engine.plane_mode`
- `core.engine` → `core.engine.tools_registry`
- `core.engine` → `render.snapsquare`
- `core.engine` → `plane.plane_creation_tool`
- `core.engine` → `logging_config`
- `core.engine.camera_rig` → `core.camera`
- `core.engine.gl_context` → `render.shaderprogram`
- `core.engine.gl_context` → `logging_config`
- `core.engine.hover_system` → `core.commands.project_commands`
- `core.engine.plane_mode` → `core.commands.project_commands`
- `core.engine.renderer_pipeline` → `core.mrt`
- `core.engine.renderer_pipeline` → `render.interactionrenderer`
- `core.engine.renderer_pipeline` → `render.mathmodelrenderer`
- `core.engine.renderer_pipeline` → `render.scenerenderer`
- `core.engine.renderer_pipeline` → `geometry.geometry_processor`
- `core.engine.renderer_pipeline` → `logging_config`
- `core.engine.tools_registry` → `core.selection_manager`
- `core.engine.tools_registry` → `core.selection_policy`
- `core.engine.tools_registry` → `core.marquee_selector`
- `core.engine.tools_registry` → `core.edit.edit_controller`
- `core.engine.tools_registry` → `tools.draw_manager`
- `core.engine.tools_registry` → `plane.plane_creation_tool`
- `core.engine.tools_registry` → `render.snapsquare`
- `core.input_manager` → `logging_config`
- `core.marquee_selector` → `logging_config`
- `core.marquee_selector` → `domain.element`
- `core.marquee_selector` → `domain.element`
- `core.marquee_selector` → `domain.element`
- `core.marquee_selector` → `domain.element`
- `core.marquee_selector` → `domain.line`
- `core.marquee_selector` → `domain.polygon`
- `core.mrt` → `logging_config`
- `core.selection_manager` → `core.commands`
- `core.selection_manager` → `core.commands`
- `core.selection_manager` → `core.selection_policy`
- `core.selection_policy` → `logging_config`
- `data.materials_catalog` → `data.enums`
- `data.materials_catalog` → `structload.data.mechanical`
- `data.materials_catalog` → `structload.data.mechanical`
- `data.materials_catalog` → `structload.data.mechanical`
- `data.materials_catalog` → `structload.data.mechanical`
- `data.materials_catalog` → `structload.data.mechanical`
- `data.materials_catalog` → `structload.data.mechanical`
- `data.materials_catalog` → `structload.data.mechanical`
- `data.materials_catalog` → `structload.data.mechanical`
- `data.section_catalog` → `data.enums`
- `data.section_catalog` → `domain.definition`
- `data.section_catalog` → `logging_config`
- `data.serializer` → `core.units`
- `data.serializer` → `data.enums`
- `data.serializer` → `data.enums`
- `data.serializer` → `domain.grid`
- `data.serializer` → `domain.grid`
- `data.serializer` → `domain.grid`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.definition`
- `data.serializer` → `domain.element`
- `data.serializer` → `domain.element`
- `data.serializer` → `domain.element`
- `data.serializer` → `domain.element`
- `data.serializer` → `domain.lighting`
- `data.serializer` → `domain.lighting`
- `data.serializer` → `domain.math_model`
- `data.serializer` → `domain.math_model`
- `data.serializer` → `domain.polygon`
- `data.serializer` → `plane.plane`
- `data.serializer` → `plane.plane`
- `data.serializer` → `plane.plane`
- `data.serializer` → `plane.plane`
- `data.serializer` → `domain.scene`
- `data.serializer` → `domain.vertex`
- `data.serializer` → `domain.line`
- `data.serializer` → `logging_config`
- `domain.definition` → `core.units`
- `domain.definition` → `core.units`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.enums`
- `domain.definition` → `data.seismic`
- `domain.element` → `core.id_manager`
- `domain.element` → `core.units`
- `domain.element` → `data.enums`
- `domain.element` → `domain.definition`
- `domain.grid` → `core.units`
- `domain.line` → `core.id_manager`
- `domain.line` → `domain.element`
- `domain.line` → `domain.vertex`
- `domain.math_model` → `data.enums`
- `domain.math_model` → `domain.bounds`
- `domain.math_model` → `domain.element`
- `domain.math_model` → `domain.element`
- `domain.math_model` → `domain.element`
- `domain.math_model` → `domain.element`
- `domain.math_model` → `domain.element`
- `domain.math_model` → `domain.line`
- `domain.math_model` → `domain.polygon`
- `domain.polygon` → `core.id_manager`
- `domain.polygon` → `data.enums`
- `domain.polygon` → `domain.element`
- `domain.polygon` → `domain.vertex`
- `domain.polygon` → `tools.polygon_frame_assoc`
- `domain.polygon` → `tools.polygon_frame_assoc`
- `domain.polygon` → `tools.polygon_frame_assoc`
- `domain.project` → `core.units`
- `domain.project` → `data.serializer`
- `domain.project` → `data.serializer`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.definition`
- `domain.project` → `domain.grid`
- `domain.project` → `domain.line`
- `domain.project` → `domain.math_model`
- `domain.project` → `domain.math_model`
- `domain.project` → `plane.plane`
- `domain.project` → `domain.polygon`
- `domain.project` → `domain.scene`
- `domain.scene` → `domain.grid`
- `domain.scene` → `domain.bounds`
- `domain.scene` → `domain.lighting`
- `domain.scene` → `domain.lighting`
- `domain.vertex` → `core.id_manager`
- `geometry.area_builder` → `domain.element`
- `geometry.area_builder` → `logging_config`
- `geometry.frame_builder` → `domain.element`
- `geometry.frame_builder` → `geometry.profile_generator`
- `geometry.frame_builder` → `logging_config`
- `geometry.geometry_processor` → `plane.plane_policy`
- `geometry.geometry_processor` → `logging_config`
- `geometry.link_builder` → `domain.element`
- `geometry.node_builder` → `domain.element`
- `geometry.node_builder` → `logging_config`
- `geometry.polygon_builder` → `domain.polygon`
- `geometry.polygon_builder` → `logging_config`
- `geometry.profile_generator` → `domain.definition`
- `geometry.profile_generator` → `logging_config`
- `geometry.project_builder` → `core.units`
- `geometry.project_builder` → `core.units`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.definition`
- `geometry.project_builder` → `domain.element`
- `geometry.project_builder` → `domain.element`
- `geometry.project_builder` → `domain.element`
- `geometry.project_builder` → `domain.element`
- `geometry.project_builder` → `domain.project`
- `geometry.project_builder` → `geometry.scenebuilder`
- `geometry.scenebuilder` → `data.enums`
- `geometry.scenebuilder` → `data.enums`
- `geometry.scenebuilder` → `data.enums`
- `geometry.scenebuilder` → `domain.definition`
- `geometry.scenebuilder` → `domain.definition`
- `geometry.scenebuilder` → `domain.definition`
- `geometry.scenebuilder` → `domain.definition`
- `geometry.scenebuilder` → `domain.definition`
- `geometry.scenebuilder` → `domain.element`
- `geometry.scenebuilder` → `domain.element`
- `geometry.scenebuilder` → `domain.element`
- `geometry.scenebuilder` → `domain.element`
- `geometry.scenebuilder` → `domain.project`
- `geometry.scenebuilder` → `logging_config`
- `geometry.sd_to_areas` → `domain.definition`
- `geometry.sd_to_areas` → `domain.definition`
- `geometry.sd_to_areas` → `domain.definition`
- `geometry.sd_to_areas` → `domain.element`
- `geometry.sd_to_areas` → `domain.element`
- `geometry.sd_to_areas` → `domain.element`
- `geometry.sd_to_areas` → `logging_config`
- `inspector` → `inspector.window`
- `inspector.schema_bridge` → `ui.helpers.adapters`
- `inspector.schema_bridge` → `ui.helpers.adapters`
- `inspector.schema_bridge` → `ui.helpers.adapters`
- `inspector.schema_bridge` → `ui.helpers.adapters`
- `inspector.schema_bridge` → `ui.helpers.schemas`
- `inspector.schema_bridge` → `ui.helpers.schemas`
- `inspector.widgets` → `domain.definition`
- `inspector.widgets` → `domain.definition`
- `inspector.widgets` → `domain.definition`
- `inspector.widgets` → `domain.definition`
- `inspector.widgets` → `domain.definition`
- `inspector.widgets` → `domain.vertex`
- `inspector.widgets` → `inspector.fields`
- `inspector.widgets` → `inspector.fields`
- `inspector.widgets` → `inspector.fields`
- `inspector.window` → `core.selection_policy`
- `inspector.window` → `inspector.controller`
- `inspector.window` → `inspector.fields`
- `inspector.window` → `inspector.topbar`
- `inspector.window` → `inspector.widgets`
- `inspector.window` → `inspector.widgets`
- `inspector.window` → `inspector.widgets`
- `inspector.window` → `inspector.widgets`
- `inspector.window` → `inspector.widgets`
- `inspector.window` → `inspector.widgets`
- `inspector.window` → `inspector.widgets`
- `inspector.window` → `inspector.widgets`
- `inspector.window` → `logging_config`
- `loads.wind_zone_distribution_service` → `data.enums`
- `loads.wind_zone_distribution_service` → `data.enums`
- `loads.wind_zone_distribution_service` → `plane.plane`
- `loads.wind_zone_distribution_service` → `domain.definition`
- `loads.wind_zone_distribution_service` → `domain.definition`
- `loads.wind_zone_distribution_service` → `logging_config`
- `main` → `logging_config`
- `plane` → `plane.plane`
- `plane` → `plane.plane`
- `plane` → `plane.plane`
- `plane` → `plane.plane`
- `plane` → `plane.plane`
- `plane` → `plane.plane`
- `plane` → `plane.plane`
- `plane` → `plane.plane`
- `plane` → `plane.plane`
- `plane` → `plane.plane_policy`
- `plane` → `plane.plane_policy`
- `plane.plane` → `core.units`
- `plane.plane` → `core.units`
- `plane.plane` → `core.units`
- `plane.plane` → `plane.plane_policy`
- `plane.plane` → `plane.plane_policy`
- `plane.plane` → `logging_config`
- `plane.plane_creation_tool` → `domain.element`
- `plane.plane_creation_tool` → `plane.plane`
- `plane.plane_creation_tool` → `domain.vertex`
- `plane.plane_creation_tool` → `logging_config`
- `plane.plane_manager_panel` → `plane.plane`
- `plane.plane_manager_panel` → `logging_config`
- `plane.plane_manager_panel` → `ui.widgets.base_panel`
- `plane.plane_manager_panel` → `viewport.viewport_panel`
- `plane.plane_source_dialog` → `domain.element`
- `plane.plane_source_dialog` → `domain.element`
- `plane.plane_source_dialog` → `domain.polygon`
- `plane.plane_source_dialog` → `plane.plane`
- `render.axes_renderer` → `logging_config`
- `render.base_renderer` → `domain.element`
- `render.base_renderer` → `domain.element`
- `render.base_renderer` → `domain.element`
- `render.base_renderer` → `geometry.area_builder`
- `render.base_renderer` → `geometry.frame_builder`
- `render.base_renderer` → `geometry.link_builder`
- `render.base_renderer` → `logging_config`
- `render.base_renderer` → `render.gl_utils`
- `render.global_axis_renderer` → `logging_config`
- `render.grid_renderer` → `render.gl_utils`
- `render.interactionrenderer` → `domain.element`
- `render.interactionrenderer` → `domain.element`
- `render.interactionrenderer` → `domain.element`
- `render.interactionrenderer` → `domain.element`
- `render.interactionrenderer` → `domain.polygon`
- `render.interactionrenderer` → `logging_config`
- `render.label_batch` → `render.gl_utils`
- `render.light_ubo` → `logging_config`
- `render.lightingsystem` → `domain.lighting`
- `render.line_renderer` → `domain.line`
- `render.line_renderer` → `render.base_renderer`
- `render.line_renderer` → `render.base_renderer`
- `render.load_renderer` → `logging_config`
- `render.mathmodelrenderer` → `render.base_renderer`
- `render.mathmodelrenderer` → `render.base_renderer`
- `render.mathmodelrenderer` → `render.base_renderer`
- `render.mathmodelrenderer` → `render.base_renderer`
- `render.mathmodelrenderer` → `render.light_ubo`
- `render.mathmodelrenderer` → `render.lightingsystem`
- `render.mathmodelrenderer` → `render.node_renderer`
- `render.mathmodelrenderer` → `render.line_renderer`
- `render.mathmodelrenderer` → `render.polygonrenderer`
- `render.mathmodelrenderer` → `render.pickpass`
- `render.mathmodelrenderer` → `render.gl_utils`
- `render.mathmodelrenderer` → `logging_config`
- `render.node_renderer` → `domain.element`
- `render.node_renderer` → `geometry.node_builder`
- `render.node_renderer` → `render.base_renderer`
- `render.node_renderer` → `render.base_renderer`
- `render.node_renderer` → `logging_config`
- `render.pickpass` → `logging_config`
- `render.polygonrenderer` → `domain.polygon`
- `render.polygonrenderer` → `geometry.polygon_builder`
- `render.polygonrenderer` → `render.base_renderer`
- `render.polygonrenderer` → `render.base_renderer`
- `render.presentation_renderer` → `render.axes_renderer`
- `render.presentation_renderer` → `render.global_axis_renderer`
- `render.presentation_renderer` → `render.grid_renderer`
- `render.presentation_renderer` → `render.grid_renderer`
- `render.presentation_renderer` → `render.label_batch`
- `render.presentation_renderer` → `render.load_renderer`
- `render.presentation_renderer` → `tools.font_atlas`
- `render.presentation_renderer` → `logging_config`
- `render.scenerenderer` → `render.presentation_renderer`
- `render.shaderprogram` → `logging_config`
- `render.snapsquare` → `domain.vertex`
- `render.snapsquare` → `logging_config`
- `structload.analysis.analysis_runner` → `structload.loads.snow_load`
- `structload.analysis.analysis_runner` → `structload.loads.spectrum`
- `structload.analysis.analysis_runner` → `structload.windcalc.wind_results`
- `structload.data.preset_loader` → `structload.loads.load_definition`
- `structload.data.preset_loader` → `structload.loads.wall_load_engine`
- `structload.gui.debug_panel` → `structload.utils.status_manager`
- `structload.gui.hazir_yuk_karti` → `structload.data.material_data`
- `structload.gui.hazir_yuk_karti` → `structload.loads.load_definition`
- `structload.gui.hazir_yuk_karti` → `structload.loads.load_definition`
- `structload.gui.hazir_yuk_karti` → `structload.utils.status_manager`
- `structload.gui.status_bar` → `structload.utils.status_manager`
- `structload.loads.load_manager` → `structload.loads.load_definition`
- `structload.loads.snow_load` → `structload.data.snow_data`
- `structload.loads.snow_load` → `structload.utils.math_utils`
- `structload.loads.snow_load` → `structload.utils.math_utils`
- `structload.loads.snow_load` → `structload.utils.report_dataframe`
- `structload.loads.spectrum` → `structload.utils.report_dataframe`
- `structload.loads.wall_load_engine` → `structload.data.material_data`
- `structload.main` → `structload.data.defaults`
- `structload.main` → `structload.gui.report_view`
- `structload.main` → `structload.gui.report_view`
- `structload.main` → `structload.gui.report_view`
- `structload.main` → `structload.gui.report_view`
- `structload.main` → `structload.gui.report_view`
- `structload.main` → `structload.loads.snow_load`
- `structload.main` → `structload.loads.spectrum`
- `structload.main` → `structload.utils.meta_tables`
- `structload.main` → `structload.windcalc.wind_results`
- `structload.utils.meta_tables` → `structload.data.material_data`
- `structload.utils.meta_tables` → `structload.data.material_data`
- `structload.utils.meta_tables` → `structload.data.material_data`
- `structload.utils.meta_tables` → `structload.data.material_data`
- `structload.utils.meta_tables` → `structload.data.mechanical`
- `structload.utils.meta_tables` → `structload.utils.report_dataframe`
- `structload.windcalc.geometry_utils` → `structload.data.wind_data`
- `structload.windcalc.geometry_utils` → `structload.data.wind_data`
- `structload.windcalc.report` → `structload.data.wind_data`
- `structload.windcalc.report` → `structload.data.wind_data`
- `structload.windcalc.report` → `structload.utils.report_dataframe`
- `structload.windcalc.surface` → `structload.data.wind_data`
- `structload.windcalc.surface` → `structload.data.wind_data`
- `structload.windcalc.surface` → `structload.data.wind_data`
- `structload.windcalc.surface` → `structload.windcalc.edge`
- `structload.windcalc.surface` → `structload.windcalc.geometry_utils`
- `structload.windcalc.surface` → `structload.windcalc.geometry_utils`
- `structload.windcalc.surface` → `structload.windcalc.geometry_utils`
- `structload.windcalc.surface` → `structload.windcalc.geometry_utils`
- `structload.windcalc.surface` → `structload.windcalc.geometry_utils`
- `structload.windcalc.surface_analyzer` → `structload.data.wind_data`
- `structload.windcalc.surface_analyzer` → `structload.data.wind_data`
- `structload.windcalc.wind_analyzer` → `structload.data.wind_data`
- `structload.windcalc.wind_analyzer` → `structload.data.wind_data`
- `structload.windcalc.wind_analyzer` → `structload.windcalc.geometry_utils`
- `structload.windcalc.wind_analyzer` → `structload.windcalc.geometry_utils`
- `structload.windcalc.wind_analyzer` → `structload.windcalc.geometry_utils`
- `structload.windcalc.wind_analyzer` → `structload.windcalc.geometry_utils`
- `structload.windcalc.wind_analyzer` → `structload.windcalc.geometry_utils`
- `structload.windcalc.wind_analyzer` → `structload.windcalc.geometry_utils`
- `structload.windcalc.wind_analyzer` → `structload.windcalc.surface`
- `structload.windcalc.wind_analyzer` → `structload.windcalc.windengine`
- `structload.windcalc.wind_analyzer` → `structload.windcalc.zone`
- `structload.windcalc.wind_results` → `structload.data.defaults`
- `structload.windcalc.wind_results` → `structload.data.wind_data`
- `structload.windcalc.wind_results` → `structload.data.wind_data`
- `structload.windcalc.wind_results` → `structload.utils.report_dataframe`
- `structload.windcalc.wind_results` → `structload.windcalc.wind_analyzer`
- `structload.windcalc.wind_results` → `structload.windcalc.windengine`
- `structload.windcalc.windengine` → `structload.data.wind_data`
- `structload.windcalc.zone` → `structload.data.wind_data`
- `structload.windcalc.zone_generator` → `structload.windcalc.geometry_utils`
- `structload.windcalc.zone_generator` → `structload.windcalc.geometry_utils`
- `structload.windcalc.zone_generator` → `structload.windcalc.geometry_utils`
- `structload.windcalc.zone_generator` → `structload.windcalc.geometry_utils`
- `structload.windcalc.zone_generator` → `structload.windcalc.geometry_utils`
- `structload.windcalc.zone_generator` → `structload.windcalc.geometry_utils`
- `structload.windcalc.zone_generator` → `structload.windcalc.surface`
- `structload.windcalc.zone_generator` → `structload.windcalc.zone`
- `tools.area_to_frame` → `core.units`
- `tools.area_to_frame` → `core.units`
- `tools.area_to_frame` → `core.units`
- `tools.area_to_frame` → `data.enums`
- `tools.area_to_frame` → `data.enums`
- `tools.area_to_frame` → `data.enums`
- `tools.area_to_frame` → `domain.definition`
- `tools.area_to_frame` → `domain.definition`
- `tools.area_to_frame` → `domain.element`
- `tools.area_to_frame` → `domain.element`
- `tools.area_to_frame` → `domain.math_model`
- `tools.area_to_frame` → `domain.polygon`
- `tools.area_to_frame` → `tools.polygon_load_transfer`
- `tools.area_to_frame` → `logging_config`
- `tools.debug_nodes` → `logging_config`
- `tools.draw_manager` → `domain.vertex`
- `tools.draw_manager` → `domain.line`
- `tools.draw_manager` → `domain.polygon`
- `tools.draw_manager` → `logging_config`
- `tools.font_atlas` → `logging_config`
- `tools.frame_to_link` → `domain.definition`
- `tools.frame_to_link` → `domain.definition`
- `tools.frame_to_link` → `domain.element`
- `tools.frame_to_link` → `domain.element`
- `tools.frame_to_link` → `logging_config`
- `tools.gridsystem` → `data.enums`
- `tools.gridsystem` → `domain.definition`
- `tools.gridsystem` → `logging_config`
- `tools.polygon_frame_assoc` → `data.enums`
- `tools.polygon_load_transfer` → `data.enums`
- `tools.polygon_load_transfer` → `data.enums`
- `tools.polygon_load_transfer` → `domain.definition`
- `tools.polygon_load_transfer` → `domain.definition`
- `tools.polygon_load_transfer` → `domain.polygon`
- `tools.s2k` → `tools.s2k.context`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.context` → `domain.definition`
- `tools.s2k.handlers` → `data.enums`
- `tools.s2k.handlers` → `tools.s2k.handlers.areas`
- `tools.s2k.handlers` → `tools.s2k.handlers.frames`
- `tools.s2k.handlers` → `tools.s2k.handlers.grids`
- `tools.s2k.handlers` → `tools.s2k.handlers.links`
- `tools.s2k.handlers` → `tools.s2k.handlers.loads`
- `tools.s2k.handlers` → `tools.s2k.handlers.materials`
- `tools.s2k.handlers` → `tools.s2k.handlers.nodes`
- `tools.s2k.handlers` → `tools.s2k.handlers.patterns`
- `tools.s2k.handlers` → `tools.s2k.handlers.program`
- `tools.s2k.handlers` → `tools.s2k.handlers.section_cuts`
- `tools.s2k.handlers` → `tools.s2k.handlers.sections`
- `tools.s2k.handlers` → `tools.s2k.handlers.spectra`
- `tools.s2k.handlers.areas` → `tools.s2k.context`
- `tools.s2k.handlers.frames` → `tools.s2k.context`
- `tools.s2k.handlers.grids` → `tools.s2k.context`
- `tools.s2k.handlers.links` → `data.enums`
- `tools.s2k.handlers.links` → `domain.definition`
- `tools.s2k.handlers.links` → `tools.s2k.context`
- `tools.s2k.handlers.loads` → `data.enums`
- `tools.s2k.handlers.loads` → `tools.s2k.context`
- `tools.s2k.handlers.materials` → `data.enums`
- `tools.s2k.handlers.materials` → `domain.definition`
- `tools.s2k.handlers.materials` → `tools.s2k.context`
- `tools.s2k.handlers.materials` → `tools.s2k.handlers._colors`
- `tools.s2k.handlers.nodes` → `data.enums`
- `tools.s2k.handlers.nodes` → `domain.definition`
- `tools.s2k.handlers.nodes` → `domain.definition`
- `tools.s2k.handlers.nodes` → `tools.s2k.context`
- `tools.s2k.handlers.patterns` → `domain.definition`
- `tools.s2k.handlers.patterns` → `domain.definition`
- `tools.s2k.handlers.patterns` → `domain.definition`
- `tools.s2k.handlers.patterns` → `domain.definition`
- `tools.s2k.handlers.patterns` → `domain.definition`
- `tools.s2k.handlers.patterns` → `domain.definition`
- `tools.s2k.handlers.patterns` → `tools.s2k.context`
- `tools.s2k.handlers.program` → `domain.definition`
- `tools.s2k.handlers.program` → `domain.definition`
- `tools.s2k.handlers.program` → `tools.s2k.context`
- `tools.s2k.handlers.section_cuts` → `data.enums`
- `tools.s2k.handlers.section_cuts` → `data.enums`
- `tools.s2k.handlers.section_cuts` → `domain.definition`
- `tools.s2k.handlers.section_cuts` → `domain.definition`
- `tools.s2k.handlers.section_cuts` → `tools.s2k.context`
- `tools.s2k.handlers.sections` → `data.enums`
- `tools.s2k.handlers.sections` → `data.enums`
- `tools.s2k.handlers.sections` → `domain.definition`
- `tools.s2k.handlers.sections` → `domain.definition`
- `tools.s2k.handlers.sections` → `domain.definition`
- `tools.s2k.handlers.sections` → `domain.definition`
- `tools.s2k.handlers.sections` → `domain.definition`
- `tools.s2k.handlers.sections` → `tools.s2k.context`
- `tools.s2k.handlers.sections` → `tools.section_checks`
- `tools.s2k.handlers.sections` → `tools.s2k.handlers._colors`
- `tools.s2k.handlers.sections` → `tools.s2k.handlers._colors`
- `tools.s2k.handlers.spectra` → `data.enums`
- `tools.s2k.handlers.spectra` → `domain.definition`
- `tools.s2k.handlers.spectra` → `domain.definition`
- `tools.s2k.handlers.spectra` → `domain.definition`
- `tools.s2k.handlers.spectra` → `domain.definition`
- `tools.s2k.handlers.spectra` → `tools.s2k.context`
- `tools.s2k.loader` → `core.units`
- `tools.s2k.loader` → `domain.project`
- `tools.s2k.loader` → `geometry.project_builder`
- `tools.s2k.loader` → `logging_config`
- `tools.s2k.loader` → `tools.s2k.context`
- `tools.s2k.loader` → `tools.s2k.handlers`
- `tools.s2k.loader` → `tools.s2k.handlers`
- `tools.s2k.loader` → `tools.s2k.s2k_scene_builder`
- `tools.s2k.loader` → `tools.s2k.s2k_scene_builder`
- `tools.s2k.loader` → `tools.s2k.s2k_scene_builder`
- `tools.s2k.loader` → `tools.s2k.s2k_scene_builder`
- `tools.s2k.loader` → `tools.s2k.s2k_scene_builder`
- `tools.s2k.loader` → `tools.s2k.s2k_scene_builder`
- `tools.s2k.s2k_scene_builder` → `domain.definition`
- `tools.s2k.s2k_scene_builder` → `domain.definition`
- `tools.s2k.s2k_scene_builder` → `domain.definition`
- `tools.s2k.s2k_scene_builder` → `domain.definition`
- `tools.s2k.s2k_scene_builder` → `domain.definition`
- `tools.s2k.s2k_scene_builder` → `domain.definition`
- `tools.s2k.s2k_scene_builder` → `domain.definition`
- `tools.s2k.s2k_scene_builder` → `domain.definition`
- `tools.s2k.s2k_scene_builder` → `domain.element`
- `tools.s2k.s2k_scene_builder` → `domain.element`
- `tools.s2k.s2k_scene_builder` → `domain.element`
- `tools.s2k.s2k_scene_builder` → `tools.s2k.context`
- `tools.s2k.s2k_scene_builder` → `tools.s2k.handlers.loads`
- `tools.section_checks` → `data.enums`
- `tools.section_checks` → `domain.definition`
- `tools.section_preview` → `data.enums`
- `tools.section_preview` → `logging_config`
- `tools.wind_manager` → `domain.definition`
- `tools.wind_manager` → `tools.wind_scene_adapter`
- `tools.wind_scene_adapter` → `core.units`
- `tools.wind_scene_adapter` → `core.units`
- `tools.wind_scene_adapter` → `core.units`
- `tools.wind_scene_adapter` → `data.enums`
- `tools.wind_scene_adapter` → `domain.definition`
- `tools.wind_scene_adapter` → `domain.definition`
- `tools.wind_scene_adapter` → `structload.windcalc.wind_analyzer`
- `ui.actions_registry` → `ui.base.panel_base`
- `ui.base.panel_base` → `ui.helpers.apply_bar`
- `ui.helpers.adapters` → `data.enums`
- `ui.helpers.adapters` → `domain.definition`
- `ui.helpers.adapters` → `domain.definition`
- `ui.helpers.adapters` → `domain.definition`
- `ui.helpers.adapters` → `domain.definition`
- `ui.helpers.adapters` → `ui.helpers.schema`
- `ui.helpers.adapters` → `ui.helpers.schema`
- `ui.helpers.schemas` → `ui.helpers.schema`
- `ui.helpers.schemas` → `ui.helpers.schema`
- `ui.panels.area_to_frame_panel` → `domain.element`
- `ui.panels.area_to_frame_panel` → `domain.polygon`
- `ui.panels.area_to_frame_panel` → `tools.area_to_frame`
- `ui.panels.area_to_frame_panel` → `tools.area_to_frame`
- `ui.panels.area_to_frame_panel` → `tools.area_to_frame`
- `ui.panels.area_to_frame_panel` → `tools.area_to_frame`
- `ui.panels.area_to_frame_panel` → `logging_config`
- `ui.panels.area_to_frame_panel` → `ui.base.panel_base`
- `ui.panels.area_to_frame_panel` → `ui.base.panel_base`
- `ui.panels.debug_panel` → `ui.base.panel_base`
- `ui.panels.debug_panel` → `ui.base.panel_base`
- `ui.panels.definition_panel` → `core.commands.project_commands`
- `ui.panels.definition_panel` → `data.enums`
- `ui.panels.definition_panel` → `data.enums`
- `ui.panels.definition_panel` → `data.enums`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `domain.definition`
- `ui.panels.definition_panel` → `logging_config`
- `ui.panels.definition_panel` → `tools.section_checks`
- `ui.panels.definition_panel` → `tools.section_checks`
- `ui.panels.definition_panel` → `tools.section_preview`
- `ui.panels.definition_panel` → `ui.base.panel_base`
- `ui.panels.definition_panel` → `ui.base.panel_base`
- `ui.panels.definition_panel` → `ui.widgets.color_picker`
- `ui.panels.frame_load_panel` → `data.enums`
- `ui.panels.frame_load_panel` → `domain.definition`
- `ui.panels.frame_load_panel` → `domain.definition`
- `ui.panels.frame_load_panel` → `domain.element`
- `ui.panels.frame_load_panel` → `ui.base.panel_base`
- `ui.panels.frame_load_panel` → `ui.base.panel_base`
- `ui.panels.frame_load_panel` → `core.commands.project_commands`
- `ui.panels.frame_preview_panel` → `render.base_renderer`
- `ui.panels.frame_preview_panel` → `render.offscreen_fbo`
- `ui.panels.frame_preview_panel` → `core.camera`
- `ui.panels.frame_preview_panel` → `ui.widgets.base_panel`
- `ui.panels.grid_panel` → `domain.grid`
- `ui.panels.grid_panel` → `domain.grid`
- `ui.panels.grid_panel` → `ui.base.panel_base`
- `ui.panels.grid_panel` → `ui.base.panel_base`
- `ui.panels.joint_load_panel` → `core.commands.project_commands`
- `ui.panels.joint_load_panel` → `domain.definition`
- `ui.panels.joint_load_panel` → `domain.element`
- `ui.panels.joint_load_panel` → `logging_config`
- `ui.panels.joint_load_panel` → `ui.base.panel_base`
- `ui.panels.joint_load_panel` → `ui.base.panel_base`
- `ui.panels.line_properties_panel` → `domain.line`
- `ui.panels.line_properties_panel` → `domain.vertex`
- `ui.panels.line_properties_panel` → `ui.widgets.base_panel`
- `ui.panels.line_properties_panel` → `ui.widgets.color_picker`
- `ui.panels.load_assign_panel` → `core.units`
- `ui.panels.load_assign_panel` → `core.units`
- `ui.panels.load_assign_panel` → `core.units`
- `ui.panels.load_assign_panel` → `domain.definition`
- `ui.panels.load_assign_panel` → `domain.definition`
- `ui.panels.load_assign_panel` → `domain.definition`
- `ui.panels.load_assign_panel` → `domain.definition`
- `ui.panels.load_assign_panel` → `domain.polygon`
- `ui.panels.load_assign_panel` → `logging_config`
- `ui.panels.load_assign_panel` → `structload.data.preset_loader`
- `ui.panels.load_assign_panel` → `ui.base.panel_base`
- `ui.panels.load_assign_panel` → `ui.base.panel_base`
- `ui.panels.load_display_panel` → `logging_config`
- `ui.panels.load_display_panel` → `ui.base.panel_base`
- `ui.panels.load_display_panel` → `ui.base.panel_base`
- `ui.panels.load_manager_panel` → `core.commands.project_commands`
- `ui.panels.load_manager_panel` → `domain.definition`
- `ui.panels.load_manager_panel` → `logging_config`
- `ui.panels.load_manager_panel` → `ui.base.panel_base`
- `ui.panels.load_manager_panel` → `ui.base.panel_base`
- `ui.panels.material_panel` → `core.commands.project_commands`
- `ui.panels.material_panel` → `domain.definition`
- `ui.panels.material_panel` → `data.enums`
- `ui.panels.material_panel` → `ui.base.panel_base`
- `ui.panels.material_panel` → `ui.base.panel_base`
- `ui.panels.polygon_properties_panel` → `data.enums`
- `ui.panels.polygon_properties_panel` → `data.enums`
- `ui.panels.polygon_properties_panel` → `domain.polygon`
- `ui.panels.polygon_properties_panel` → `tools.area_to_frame`
- `ui.panels.polygon_properties_panel` → `tools.area_to_frame`
- `ui.panels.polygon_properties_panel` → `structload.data.preset_loader`
- `ui.panels.polygon_properties_panel` → `ui.base.panel_base`
- `ui.panels.polygon_properties_panel` → `ui.base.panel_base`
- `ui.panels.polygon_properties_panel` → `ui.widgets.color_picker`
- `ui.panels.polygon_properties_panel` → `core.units`
- `ui.panels.polygon_properties_panel` → `core.units`
- `ui.panels.polygon_properties_panel` → `core.units`
- `ui.panels.polygon_properties_panel` → `domain.definition`
- `ui.panels.polygon_properties_panel` → `domain.definition`
- `ui.panels.polygon_properties_panel` → `domain.definition`
- `ui.panels.polygon_properties_panel` → `logging_config`
- `ui.panels.project_panels` → `core.analysis.run`
- `ui.panels.project_panels` → `core.analysis.run`
- `ui.panels.project_panels` → `core.analysis.run`
- `ui.panels.project_panels` → `logging_config`
- `ui.panels.project_panels` → `ui.widgets.base_panel`
- `ui.panels.project_settings_panel` → `ui.widgets.base_panel`
- `ui.panels.project_settings_panel` → `logging_config`
- `ui.panels.render_settings_panel` → `logging_config`
- `ui.panels.render_settings_panel` → `ui.widgets.base_panel`
- `ui.panels.report_panel` → `data.seismic`
- `ui.panels.report_panel` → `structload.loads.snow_load`
- `ui.panels.report_panel` → `structload.loads.spectrum`
- `ui.panels.report_panel` → `structload.utils.meta_tables`
- `ui.panels.report_panel` → `structload.windcalc.report`
- `ui.panels.report_panel` → `structload.windcalc.report`
- `ui.panels.report_panel` → `structload.windcalc.report`
- `ui.panels.report_panel` → `structload.windcalc.wind_analyzer`
- `ui.panels.report_panel` → `structload.windcalc.windengine`
- `ui.panels.report_panel` → `tools.wind_scene_adapter`
- `ui.panels.report_panel` → `ui.base.panel_base`
- `ui.panels.report_panel` → `ui.base.panel_base`
- `ui.panels.report_panel` → `logging_config`
- `ui.panels.s2k_panel` → `domain.project`
- `ui.panels.s2k_panel` → `logging_config`
- `ui.panels.s2k_panel` → `tools.s2k`
- `ui.panels.s2k_panel` → `tools.s2k`
- `ui.panels.s2k_panel` → `tools.s2k`
- `ui.panels.s2k_panel` → `tools.s2k.handlers`
- `ui.panels.s2k_panel` → `tools.s2k.handlers`
- `ui.panels.s2k_panel` → `tools.s2k_exporter`
- `ui.panels.s2k_panel` → `ui.base.panel_base`
- `ui.panels.s2k_panel` → `ui.base.panel_base`
- `ui.panels.s2k_panel` → `ui.widgets.file_dialog`
- `ui.panels.sd_convert_panel` → `domain.definition`
- `ui.panels.sd_convert_panel` → `domain.element`
- `ui.panels.sd_convert_panel` → `domain.element`
- `ui.panels.sd_convert_panel` → `domain.element`
- `ui.panels.sd_convert_panel` → `geometry.sd_to_areas`
- `ui.panels.sd_convert_panel` → `logging_config`
- `ui.panels.sd_convert_panel` → `ui.widgets.base_panel`
- `ui.panels.selection_panel` → `core.selection_policy`
- `ui.panels.selection_panel` → `logging_config`
- `ui.panels.selection_panel` → `ui.base.panel_base`
- `ui.panels.selection_panel` → `ui.base.panel_base`
- `ui.panels.test_panel` → `ui.base.panel_base`
- `ui.panels.test_panel` → `ui.base.panel_base`
- `ui.panels.view_filter_panel` → `ui.base.panel_base`
- `ui.panels.view_filter_panel` → `ui.base.panel_base`
- `ui.panels.visibility_panel` → `ui.base.panel_base`
- `ui.panels.visibility_panel` → `ui.base.panel_base`
- `ui.panels.wind_analysis_panel` → `core.units`
- `ui.panels.wind_analysis_panel` → `core.units`
- `ui.panels.wind_analysis_panel` → `core.units`
- `ui.panels.wind_analysis_panel` → `data.enums`
- `ui.panels.wind_analysis_panel` → `logging_config`
- `ui.panels.wind_analysis_panel` → `ui.base.panel_base`
- `ui.panels.wind_analysis_panel` → `ui.base.panel_base`
- `ui.panels.wind_analysis_panel` → `tools.wind_scene_adapter`
- `ui.panels.wind_analysis_panel` → `domain.definition`
- `ui.registry` → `ui.base.panel_base`
- `ui.registry` → `ui.base.panel_base`
- `ui.ui_host` → `core.commands.project_commands`
- `ui.ui_host` → `core.commands.command_queue`
- `ui.ui_host` → `core.commands.project_commands`
- `ui.ui_host` → `domain.element`
- `ui.ui_host` → `domain.element`
- `ui.ui_host` → `domain.element`
- `ui.ui_host` → `domain.element`
- `ui.ui_host` → `domain.polygon`
- `ui.ui_host` → `logging_config`
- `ui.ui_host` → `ui.actions_registry`
- `ui.ui_host` → `ui.actions_registry`
- `ui.ui_host` → `ui.actions_registry`
- `ui.ui_host` → `viewport.viewport_panel`
- `ui.widgets.plane_2d_loads` → `domain.definition`
- `ui.widgets.plane_2d_view` → `plane.plane`
- `ui.widgets.plane_2d_view` → `plane.plane`
- `ui.widgets.plane_2d_view` → `ui.widgets.plane_2d_loads`
- `ui.widgets.plane_2d_view` → `ui.widgets.plane_2d_tools`
- `ui.widgets.plane_2d_view` → `ui.widgets.plane_2d_tools`
- `ui.widgets.plane_2d_view` → `ui.widgets.plane_2d_tools`
- `ui.widgets.toolbar` → `ui.widgets.icon_manager`
- `viewport` → `viewport.viewport`
- `viewport` → `viewport.viewport_manager`
- `viewport` → `viewport.viewport_panel`
- `viewport.viewport` → `core.camera`
- `viewport.viewport` → `render.offscreen_fbo`
- `viewport.viewport` → `logging_config`
- `viewport.viewport_manager` → `logging_config`
- `viewport.viewport_manager` → `viewport.viewport`

## Inheritance

- `core.commands.base.Command` extends `ABC`
- `core.commands.bulk_update.BulkUpdateCommand` extends `Command`
- `core.commands.create.CreateElementCommand` extends `Command`
- `core.commands.delete.DeleteElementsCommand` extends `Command`
- `core.commands.update.UpdateElementCommand` extends `Command`
- `core.selection_policy.SelectionMode` extends `Enum`
- `core.units.Dimension` extends `Enum`
- `core.units.UnitSystem` extends `Enum`
- `data.enums.ConstraintType` extends `Enum`
- `data.enums.MatType` extends `IntEnum`
- `data.enums.SectionType` extends `Enum`
- `data.enums.LinkPropType` extends `IntEnum`
- `data.enums.ElementType` extends `Enum`
- `data.enums.ObjType` extends `Enum`
- `data.enums.LoadPatternType` extends `Enum`
- `data.enums.LoadCaseType` extends `Enum`
- `data.enums.ComboType` extends `Enum`
- `data.enums.GridPlane` extends `IntEnum`
- `data.enums.SectionCutDefinedBy` extends `str`
- `data.enums.SectionCutDefinedBy` extends `Enum`
- `data.enums.SectionCutResultType` extends `str`
- `data.enums.SectionCutResultType` extends `Enum`
- `data.enums.PropAreaType` extends `IntEnum`
- `data.enums.PropType` extends `IntEnum`
- `data.enums.SymType` extends `IntEnum`
- `data.enums.SpectrumSourceType` extends `Enum`
- `data.enums.LoadType` extends `Enum`
- `data.enums.LoadDirection` extends `Enum`
- `data.enums.DistType` extends `Enum`
- `data.enums.PolygonType` extends `Enum`
- `data.serializer.DomainJSONEncoder` extends `json.JSONEncoder`
- `domain.definition.LinkPropLinear` extends `LinkProp`
- `domain.element.Node` extends `Element`
- `domain.element.Frame` extends `Element`
- `domain.element.Area` extends `Element`
- `domain.element.Link` extends `Element`
- `domain.line.Line` extends `Element`
- `domain.polygon.Polygon` extends `Element`
- `geometry.base_builder.BaseGeometryBuilder` extends `ABC`
- `geometry.base_builder.BaseGeometryBuilder` extends `Generic[T]`
- `inspector.schema_bridge.Catalog` extends `Protocol`
- `logging_config.DuplicateMessageFilter` extends `logging.Filter`
- `logging_config._ColorFormatter` extends `logging.Formatter`
- `plane.plane_manager_panel.PlaneManagerPanel` extends `BasePanel`
- `plane.plane_policy.SectionFilterMode` extends `str`
- `plane.plane_policy.SectionFilterMode` extends `Enum`
- `render.base_renderer.BaseRenderer` extends `ABC`
- `render.base_renderer.BaseRenderer` extends `Generic[T]`
- `render.base_renderer.FrameRenderer` extends `BaseRenderer[Frame]`
- `render.base_renderer.AreaRenderer` extends `BaseRenderer[Area]`
- `render.base_renderer.LinkRenderer` extends `BaseRenderer[Link]`
- `render.line_renderer.LineRenderer` extends `BaseRenderer[Line]`
- `render.node_renderer.NodeRenderer` extends `BaseRenderer[Node]`
- `render.polygonrenderer.PolygonRenderer` extends `BaseRenderer[Polygon]`
- `structload.data.wind_data.SurfaceType` extends `Enum`
- `structload.data.wind_data.WindRelation` extends `Enum`
- `structload.data.wind_data.RoofType` extends `Enum`
- `structload.gui.analysis_panels.AnalysisDataPanel` extends `BoxLayout`
- `structload.gui.analysis_panels.ResultPanel` extends `BoxLayout`
- `structload.gui.debug_panel.DebugPanel` extends `BoxLayout`
- `structload.gui.file_dialog.FileDialog` extends `BoxLayout`
- `structload.gui.hazir_yuk_karti.KartBilesenSatiri` extends `BoxLayout`
- `structload.gui.hazir_yuk_karti.HazirYukDetayKarti` extends `BoxLayout`
- `structload.gui.report_view.CardContainer` extends `BoxLayout`
- `structload.gui.report_view.AutoLabel` extends `Label`
- `structload.gui.report_view.ReportView` extends `CardContainer`
- `structload.gui.status_bar.StatusBar` extends `BoxLayout`
- `structload.main.SectionHeader` extends `CardContainer`
- `structload.main.StructuralAnalysisApp` extends `App`
- `structload.utils.report_dataframe.ReportDataFrame` extends `pd.DataFrame`
- `structload.utils.status_manager.StatusManager` extends `EventDispatcher`
- `structload.windcalc.wind_analyzer.ZoneKind` extends `Enum`
- `structload.windcalc.zone_generator.ZoneKind` extends `Enum`
- `ui.base.panel_base.Category` extends `StrEnum`
- `ui.panels.area_to_frame_panel.AreaToFramePanel` extends `PanelBase`
- `ui.panels.debug_panel.DebugPanel` extends `PanelBase`
- `ui.panels.definition_panel.DefinitionPanel` extends `PanelBase`
- `ui.panels.frame_load_panel.FrameLoadPanel` extends `PanelBase`
- `ui.panels.frame_preview_panel.FramePreviewPanel` extends `BasePanel`
- `ui.panels.grid_panel.GridPanel` extends `PanelBase`
- `ui.panels.joint_load_panel.JointLoadPanel` extends `PanelBase`
- `ui.panels.line_properties_panel.LinePropertiesPanel` extends `BasePanel`
- `ui.panels.load_assign_panel.LoadAssignPanel` extends `PanelBase`
- `ui.panels.load_display_panel.LoadDisplayPanel` extends `PanelBase`
- `ui.panels.load_manager_panel.LoadManagerPanel` extends `PanelBase`
- `ui.panels.material_panel.MaterialPanel` extends `PanelBase`
- `ui.panels.polygon_properties_panel.PolygonPropertiesPanel` extends `PanelBase`
- `ui.panels.project_panels.AnalysisManagerPanel` extends `BasePanel`
- `ui.panels.project_panels.ReportPanel` extends `BasePanel`
- `ui.panels.project_panels.ProjectInfoPanel` extends `BasePanel`
- `ui.panels.project_panels.ProjectConfigPanel` extends `BasePanel`
- `ui.panels.project_settings_panel.ProjectSettingsPanel` extends `BasePanel`
- `ui.panels.render_settings_panel.RenderSettingsPanel` extends `BasePanel`
- `ui.panels.report_panel.ReportPanel` extends `PanelBase`
- `ui.panels.s2k_panel.S2KPanel` extends `PanelBase`
- `ui.panels.sd_convert_panel.SDConvertPanel` extends `BasePanel`
- `ui.panels.selection_panel.SelectionPanel` extends `PanelBase`
- `ui.panels.test_panel.TestPanel` extends `PanelBase`
- `ui.panels.view_filter_panel.ViewFilterPanel` extends `PanelBase`
- `ui.panels.visibility_panel.VisibilityPanel` extends `PanelBase`
- `ui.panels.wind_analysis_panel.WindAnalysisPanel` extends `PanelBase`
- `ui.widgets.plane_2d_tools.ToolKind` extends `Enum`
- `ui.widgets.plane_2d_tools.Tool` extends `Protocol`

## Important Notes

- This document is generated using Python AST.
- Import relationships are statically inferred.
- Dynamic imports and runtime relationships may not appear.
- Class ownership and architectural responsibilities require human documentation.
- Refer to the source code for authoritative implementation details.

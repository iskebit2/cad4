# app - Project Context

Generated: 2026-11-19T22:20:08

## Project Overview

- Name: app
- Python files: 48

## Architecture Notes

- CAD4 is a structural engineering CAD application.
- The project uses Python and OpenGL.

## Module Structure

### `cad_app`

Path: `cad_app.py`

#### Classes

- **CadApp** (line 27)
  - Orkestratör. İş mantığı servislerde; sadece yaşam döngüsü + komut akışı.
  - `__init__(self, width: int=1200, height: int=800)`
  - `ui(self -> UIHost | None)`
  - `current_project(self -> Project)`
  - `command_registry(self)`
  - `section_catalog(self -> dict)`
  - `init_engine(self -> None)`
  - `attach_ui(self, ui_host: 'UIHost' -> None)`
  - `resize(self, width: int, height: int -> None)`
  - `tick(self, dt: float -> None)`
  - `request_quit(self -> None)`
  - `shutdown(self -> None)`
  - `put_command(self, cmd -> None)`
  - `log_command_result(self, msg: str, level: str='info' -> None)`
  - `_drain_commands(self -> None)`
  - `_update_scene_if_dirty(self -> None)`
  - `_refresh_hover_listener_flag(self -> None)`

### `cad_window`

Path: `cad_window.py`

#### Classes

- **CadWindow** (line 12)
  - Saf GLFW penceresi. ImGui, UIHost veya CadApp bilmez.
  - `__init__(self, width: int=1200, height: int=800, title: str='CAD4')`
  - `create(self -> None)`
  - `_wire_callbacks(self -> None)`
  - `_cb_resize(self, win, w: int, h: int -> None)`
  - `_cb_key(self, win, key: int, scancode: int, action: int, mods: int -> None)`
  - `_cb_mouse_button(self, win, button: int, action: int, mods: int -> None)`
  - `_cb_mouse_move(self, win, x: float, y: float -> None)`
  - `_cb_scroll(self, win, xoff: float, yoff: float -> None)`
  - `_cb_char(self, win, codepoint: int -> None)`
  - `_cb_focus(self, win, focused: bool -> None)`
  - `poll_events(self -> None)`
  - `swap_buffers(self -> None)`
  - `request_close(self -> None)`
  - `should_close(self -> bool)`
  - `shutdown(self -> None)`

### `commands`

Path: `commands/__init__.py`

### `commands.analysis`

Path: `commands/analysis/__init__.py`

### `commands.analysis.mass_assembly`

Path: `commands/analysis/mass_assembly.py`

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

### `commands.analysis.material_takeoff`

Path: `commands/analysis/material_takeoff.py`

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

### `commands.analysis.modal_analysis`

Path: `commands/analysis/modal_analysis.py`

#### Classes

- **SpectralModeResult** (line 16)
  - `__inspector_tree__(self)`
- **SpectralResult** (line 52)
  - `__inspector_tree__(self)`

#### Module Functions

- `_direction_vector(modal_dofs, direction)`
- `response_spectrum_solve(modal: ModalResult, M_global, num_dofs, spectrum, n_modes=None)`

### `commands.analysis.run`

Path: `commands/analysis/run.py`

Yüksek seviye analiz servisi — UI'nin tek giriş noktası.

    from core.analysis.run import AnalysisService
    result = AnalysisService.run(scene, project, options)

#### Classes

- **AnalysisOptions** (line 18)
- **AnalysisBundle** (line 29)
  - `ok(self -> bool)`
- **AnalysisService** (line 41)
  - `run(scene, project, options: AnalysisOptions -> AnalysisBundle)`

### `commands.analysis.solver`

Path: `commands/analysis/solver.py`

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

### `commands.analysis.spectrum`

Path: `commands/analysis/spectrum.py`

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

### `commands.analysis.stiffness_assembly`

Path: `commands/analysis/stiffness_assembly.py`

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

### `commands.analysis.structuralanalysis`

Path: `commands/analysis/structuralanalysis.py`

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

### `commands.analysis.unit_guard`

Path: `commands/analysis/unit_guard.py`

#### Module Functions

- `ensure_nmm(project -> None)`
  - Solver öncesi project'i N_MM'ye çevir.

### `commands.analysis.validation`

Path: `commands/analysis/validation.py`

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

### `commands.base`

Path: `commands/base.py`

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

### `commands.bulk_update`

Path: `commands/bulk_update.py`

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

### `commands.camera`

Path: `commands/camera.py`

#### Module Functions

- `_fit(app, cmd: PC.FitView -> CommandResult)`
- `_zoom(app, cmd: PC.ZoomExtents -> CommandResult)`
- `_preset(app, cmd: PC.SetCameraPreset -> CommandResult)`
- `_set_preset(args: list[str])`

### `commands.command_queue`

Path: `commands/command_queue.py`

#### Classes

- **CommandQueue** (line 6)
  - `__init__(self -> None)`
  - `put(self, command: Any -> None)`
  - `drain(self -> list[Any])`

### `commands.create`

Path: `commands/create.py`

#### Classes

- **CreateElementCommand** (Command) (line 11)
  - Yeni bir eleman oluşturup scene'e ekler.
  - `__init__(self, scene, element_type: str, factory: Callable[[dict[str, Any]], Any], values: dict[str, Any])`
  - `execute(self)`
  - `undo(self)`
  - `name(self -> str)`

### `commands.definitions`

Path: `commands/definitions.py`

#### Module Functions

- `_add(app, cmd: PC.AddDefinition -> CommandResult)`
- `_update(app, cmd: PC.UpdateDefinition -> CommandResult)`
- `_remove(app, cmd: PC.RemoveDefinition -> CommandResult)`
- `_rename(app, cmd: PC.RenameDefinition -> CommandResult)`

### `commands.delete`

Path: `commands/delete.py`

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

### `commands.draw`

Path: `commands/draw.py`

#### Classes

- **AddDrawnElementCommand** (Command) (line 14)
  - DrawManager tarafından üretilen Line veya Polygon nesnesini
  - `__init__(self, project, engine, element: Any -> None)`
  - `execute(self -> None)`
  - `undo(self -> None)`
  - `_sync_view(self -> None)`
  - `name(self -> str)`

#### Module Functions

- `_start_draw(app, cmd: PC.StartDrawTool -> CommandResult)`
- `_commit_drawn(app, cmd: PC.CommitDrawnElement -> CommandResult)`
- `_f_draw(args: list[str])`
- `_f_draw_line(args: list[str])`
- `_f_draw_poly(args: list[str])`
- `_f_draw_rect(args: list[str])`

### `commands.edit_controller`

Path: `commands/edit_controller.py`

#### Classes

- **EditResult** (line 19)
- **EditController** (line 26)
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
  - `replicate(self, elements, dx: float, dy: float, dz: float, count: int=1, select_created: bool=True -> EditResult)`

### `commands.elements`

Path: `commands/elements.py`

#### Module Functions

- `_delete_selected(app, cmd: PC.DeleteSelected -> CommandResult)`
- `_replicate_selected(app, cmd: PC.ReplicateSelected -> CommandResult)`
- `_f_replicate(args: list[str])`
- `_delete(app, cmd: PC.DeleteElements -> CommandResult)`
- `_update_fields(app, cmd: PC.UpdateElementFields -> CommandResult)`
- `_add_node(app, cmd: PC.AddNode -> CommandResult)`
- `_add_frame(app, cmd: PC.AddFrame -> CommandResult)`
- `_f_add_node(args: list[str])`
- `_f_delete_selected(args: list[str])`
- `_convert_frames_to_links(app, cmd: PC.ConvertFramesToLinks -> CommandResult)`

### `commands.engine_flags`

Path: `commands/engine_flags.py`

#### Module Functions

- `_hover(app, cmd: PC.HoverChanged -> CommandResult)`
  - Hover durumu değişti. Panel'lere yayınla; UIHost'a dokunma.
- `_start_plane(app, cmd: PC.StartPlaneTool -> CommandResult)`
- `_undo(app, cmd: PC.Undo -> CommandResult)`
- `_redo(app, cmd: PC.Redo -> CommandResult)`
- `_toggle_2d(app, cmd: PC.Toggle2D -> CommandResult)`
- `_loads(app, cmd: PC.ToggleLoadsVisible -> CommandResult)`
- `_local_axes(app, cmd: PC.ToggleLocalAxes -> CommandResult)`
- `_render_flag(app, cmd: PC.ToggleRenderFlag -> CommandResult)`
- `_render_mode(app, cmd: PC.SetRenderMode -> CommandResult)`
- `_f_set_render_mode(args: list[str])`
- `_f_toggle_flag(args: list[str])`
- `_start_plane_3pt(app, cmd: PC.StartPlane3pt -> CommandResult)`
- `_start_plane_2pt_z(app, cmd: PC.StartPlane2ptZ -> CommandResult)`
- `_toggle_render_mode(app, cmd: PC.ToggleRenderMode -> CommandResult)`

### `commands.file_ops`

Path: `commands/file_ops.py`

#### Module Functions

- `_new(app, cmd: PC.NewProject -> CommandResult)`
- `_open(app, cmd: PC.OpenProject -> CommandResult)`
- `_save(app, cmd: PC.SaveProject -> CommandResult)`
- `_save_as(app, cmd: PC.SaveProjectAs -> CommandResult)`
- `_close(app, cmd: PC.CloseProject -> CommandResult)`
- `_import_s2k(app, cmd: PC.ImportS2K -> CommandResult)`
- `_export_s2k(app, cmd: PC.ExportS2K -> CommandResult)`
- `_f_open(args)`
- `_f_save(args)`
- `_f_save_as(args)`
- `_f_import_s2k(args)`
- `_f_export_s2k(args)`
- `_quit(app, cmd: PC.QuitApp -> CommandResult)`

### `commands.geometry_ops`

Path: `commands/geometry_ops.py`

#### Module Functions

- `_propagate_geometry(app, cmd: PC.PropagateGeometryChange -> CommandResult)`
- `_fallback_cascade(model, nodes -> int)`

### `commands.inspector`

Path: `commands/inspector.py`

#### Module Functions

- `_open_inspector(app, cmd: PC.OpenInspector -> CommandResult)`

### `commands.panels`

Path: `commands/panels.py`

#### Module Functions

- `_toggle_panel(app, cmd: PC.TogglePanel -> CommandResult)`
- `_open_panel(app, cmd: PC.OpenPanel -> CommandResult)`
- `_close_panel(app, cmd: PC.ClosePanel -> CommandResult)`
- `_f_panel(args: list[str])`

### `commands.project`

Path: `commands/project.py`

#### Module Functions

- `_replace(app, cmd: PC.ReplaceProject -> CommandResult)`
- `_set_unit(app, cmd: PC.SetUnitSystem -> CommandResult)`
- `_f_set_unit(args)`

### `commands.project_commands`

Path: `commands/project_commands.py`

#### Classes

- **OpenPanel** (line 7)
- **ClosePanel** (line 12)
- **TogglePanel** (line 16)
- **ReplicateSelected** (line 21)
- **AddDefinition** (line 28)
- **UpdateDefinition** (line 35)
- **RemoveDefinition** (line 43)
- **RenameDefinition** (line 49)
- **UpdateElementFields** (line 57)
- **DeleteElements** (line 63)
- **AddNode** (line 68)
- **AddFrame** (line 77)
- **ReplaceProject** (line 87)
- **SetUnitSystem** (line 93)
- **FitView** (line 100)
- **ZoomExtents** (line 104)
- **SetCameraPreset** (line 108)
- **Toggle2D** (line 113)
- **ToggleLoadsVisible** (line 117)
- **ToggleLocalAxes** (line 122)
- **ClearSelection** (line 126)
- **SelectElements** (line 130)
- **RefreshGeometry** (line 136)
- **ShowOnly** (line 140)
- **HideElements** (line 145)
- **ShowEntireModel** (line 150)
- **OpenInspector** (line 153)
- **ToggleRenderFlag** (line 156)
- **SetRenderMode** (line 161)
- **ToggleRenderMode** (line 165)
- **DeleteSelected** (line 170)
- **StartDrawTool** (line 175)
- **CommitDrawnElement** (line 179)
- **StartPlaneTool** (line 183)
- **Undo** (line 188)
- **Redo** (line 193)
- **HoverChanged** (line 197)
- **NewProject** (line 201)
- **OpenProject** (line 204)
- **SaveProject** (line 208)
- **SaveProjectAs** (line 212)
- **CloseProject** (line 216)
- **ImportS2K** (line 219)
- **ExportS2K** (line 224)
- **QuitApp** (line 228)
- **StartPlane3pt** (line 231)
- **StartPlane2ptZ** (line 234)
- **ConvertFramesToLinks** (line 237)
- **PropagateGeometryChange** (line 242)

### `commands.registry`

Path: `commands/registry.py`

#### Classes

- **CommandRegistry** (line 36)
  - `__init__(self -> None)`
  - `register(self, cmd_type: type, handler: CommandHandler -> None)`
  - `get_usage(self, name: str -> str)`
  - `get_command_catalog(self -> list[tuple[str, str]])`
    - (komut_adi, kullanim_imzasi) çiftlerini alfabetik döndürür.
  - `add_factory(self, name: str, factory: CommandFactory -> None)`
  - `list_names(self -> list[str])`
  - `list_types(self -> list[type])`
  - `has_factory(self, name: str -> bool)`
  - `has_handler(self, cmd_type: type -> bool)`
  - `build_by_name(self, name: str, args: list[str] -> Any | None)`
  - `dispatch(self, app: 'CadApp', cmd: Any -> CommandResult)`
  - `conflicts(self -> list[str])`

#### Module Functions

- `_snake(name: str -> str)`
- `_no_args_factory(cmd_type: type -> CommandFactory)`
- `command(cmd_type: type -> Callable[[CommandHandler], CommandHandler])`
- `factory(name: str -> Callable[[CommandFactory], CommandFactory])`
- `_discover_modules( -> list[str])`
- `_import_command_modules( -> None)`
- `build_registry( -> CommandRegistry)`
- `_auto_factory(cmd_type: type -> tuple[CommandFactory, str])`
  - Dataclass alanlarından otomatik CLI parser ve kullanım imzası üretir.
- `get_registry( -> CommandRegistry)`
  - Süreç başına tek registry. build_registry() import maliyetini tekrarlamaz.

### `commands.replicate`

Path: `commands/replicate.py`

#### Classes

- **ReplicateElementsCommand** (Command) (line 14)
  - Seçili elemanları (dx, dy, dz) artımla `count` kez çoğaltır.
  - `__init__(self, scene, elements: list[Any], dx: float, dy: float, dz: float, count: int=1 -> None)`
  - `execute(self -> None)`
  - `undo(self -> None)`
  - `_build_and_add(self -> None)`
  - `all_created(self -> list[Any])`
  - `name(self -> str)`

### `commands.result`

Path: `commands/result.py`

#### Classes

- **CommandResult** (line 8)

### `commands.selection`

Path: `commands/selection.py`

#### Module Functions

- `_clear(app, cmd: PC.ClearSelection -> CommandResult)`
- `_select(app, cmd: PC.SelectElements -> CommandResult)`
- `_f_select(args: list[str])`

### `commands.signals`

Path: `commands/signals.py`

#### Module Functions

- `_refresh(app, cmd: PC.RefreshGeometry -> CommandResult)`

### `commands.update`

Path: `commands/update.py`

#### Classes

- **UpdateElementCommand** (Command) (line 11)
  - Bir elemanın alanlarını değiştirir.
  - `__init__(self, element, before: dict[str, Any], after: dict[str, Any], setter: Callable[[Any, str, Any], None])`
  - `execute(self)`
  - `undo(self)`
  - `name(self -> str)`

### `commands.visibility`

Path: `commands/visibility.py`

#### Module Functions

- `_show_only(app, cmd: PC.ShowOnly -> CommandResult)`
- `_hide(app, cmd: PC.HideElements -> CommandResult)`
- `_show_all(app, cmd: PC.ShowEntireModel -> CommandResult)`
- `_f_show_only(args)`
- `_f_hide(args)`
- `_f_show_all(args)`

### `glfw_debug_overlay`

Path: `glfw_debug_overlay.py`

#### Classes

- **DebugButton** (line 39)
  - `__init__(self, label: str, ndc_rect: tuple[float, float, float, float], color: tuple[float, float, float], on_click: Callable[[], None])`
  - `contains(self, nx: float, ny: float -> bool)`
- **GlfwDebugOverlay** (line 53)
  - `__init__(self, width: int, height: int)`
  - `_init_gl(self -> None)`
  - `_trigger_engine(self -> None)`
  - `_trigger_ui(self -> None)`
  - `_trigger_test(self -> None)`
  - `log(self, msg: str -> None)`
  - `_to_ndc(self, x: float, y: float -> tuple[float, float])`
  - `resize(self, w: int, h: int -> None)`
  - `on_mouse_move(self, x: float, y: float -> None)`
  - `on_mouse_button(self, button: int, action: int, mods: int -> bool)`
  - `on_scroll(self, xoff: float, yoff: float -> None)`
  - `on_key(self, key: int, scancode: int, action: int, mods: int -> bool)`
  - `render(self, clear_bg: bool=True -> None)`
  - `_draw_rect(self, x0: float, y0: float, x1: float, y1: float, color: tuple[float, float, float] -> None)`
  - `_draw_border(self, x0: float, y0: float, x1: float, y1: float, color: tuple[float, float, float] -> None)`
  - `_draw(self, verts: list[float], mode: int, color: tuple[float, float, float] -> None)`
  - `cleanup(self -> None)`

### `input_bindings`

Path: `input_bindings.py`

#### Module Functions

- `build_bindings(command_queue -> dict)`

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

### `services.panel_registry`

Path: `services/panel_registry.py`

#### Classes

- **PanelSpec** (line 21)
- **PanelEntry** (line 117)
- **PanelRegistry** (line 129)
  - PANELS sözlüğündeki tanımları örnekler ve UI/Command katmanlarına sunar.
  - `__init__(self, app: 'CadApp | None'=None -> None)`
  - `load_from_specs(self, app: 'CadApp', specs: dict[int, PanelSpec] -> None)`
  - `register(self, entry: PanelEntry -> None)`
  - `get(self, name: str -> PanelEntry | None)`
  - `instance(self, name: str -> Any | None)`
  - `all(self -> list[PanelEntry])`
  - `visible(self -> list[PanelEntry])`
  - `is_visible(self, name: str -> bool)`
  - `categories(self -> dict[str, list[str]])`
  - `toolbar_specs(self -> list[PanelEntry])`
  - `toolbar_commands(self, put_command: Callable[[Any], None] -> dict[str, Callable[[], None]])`
  - `toolbar_states(self -> dict[str, Callable[[], bool]])`

### `services.project_service`

Path: `services/project_service.py`

#### Classes

- **ProjectState** (line 19)
- **ProjectService** (line 25)
  - Proje yaşam döngüsü: yeni/aç/kaydet/değiştir + birim dönüşümü.
  - `__init__(self, app: 'CadApp')`
  - `project(self -> Project)`
  - `file_path(self -> str | None)`
  - `model_text(self -> str)`
  - `replace(self, project: Project, *, path: str | None=None, model_text: str | None=None -> None)`
    - Projeyi değiştir; UI reset + engine senkronu + kamera odaklama.
  - `new(self -> None)`
  - `load(self, path: str -> None)`
  - `save(self, path: str -> None)`
  - `save_current(self -> bool)`
    - True = kaydedildi, False = yol yok (UI dialog açmalı).
  - `set_unit_system(self, unit_system: UnitSystem -> None)`
  - `_fit_viewports(self -> None)`
  - `_refresh_engine_after_unit_change(self -> None)`
  - `_notify_ui(self, unit_changed: bool=False -> None)`

### `services.toolbar_builder`

Path: `services/toolbar_builder.py`

#### Classes

- **UnifiedSpec** (line 12)
  - Toolbar'ın tek gördüğü spec türü — panel veya komut.

#### Module Functions

- `build_unified_specs(panel_registry: PanelRegistry, extra_commands: list[CommandSpec] | None=None -> list[UnifiedSpec])`
  - PANELS + varsayılan komut kataloğu → tek sıralı list.
- `group_by_category(specs: list[UnifiedSpec] -> dict[str, list[UnifiedSpec]])`

### `services.toolbar_specs`

Path: `services/toolbar_specs.py`

#### Classes

- **CommandSpec** (line 9)
  - Quick-bar / menüde görünecek anlık komut (panel değil).

#### Module Functions

- `default_commands( -> list[CommandSpec])`
  - Uygulamanın toolbar'da görmek istediği tüm dosya/düzen/görünüm komutları.

### `services.view_service`

Path: `services/view_service.py`

#### Classes

- **ViewService** (line 14)
  - Kamera, 2D plane, render modu, load görünürlüğü.
  - `__init__(self, app: 'CadApp')`
  - `_active_camera(self)`
  - `fit_view(self -> None)`
  - `zoom_extents(self -> None)`
  - `set_camera_preset(self, preset: str -> None)`
  - `toggle_2d(self -> None)`
  - `activate_plane(self, plane -> None)`
  - `get_loads_visible(self -> bool)`
  - `set_loads_visible(self, enabled: bool -> None)`

### `services.visibility_service`

Path: `services/visibility_service.py`

#### Classes

- **VisibilityService** (line 10)
  - show_only / hide / show_all — filtre state'i burada tutulur.
  - `__init__(self, app: 'CadApp')`
  - `show_only(self, uids: list[int] | None -> bool)`
  - `hide(self, uids: list[int] -> bool)`
  - `show_all(self -> None)`
  - `_model(self)`

### `services.wind_service`

Path: `services/wind_service.py`

#### Classes

- **WindService** (line 10)
  - WindManager'a ince sarmalayıcı — UIHost doğrudan erişmesin.
  - `__init__(self, app: 'CadApp')`
  - `attach(self, manager -> None)`
  - `state(self -> dict)`
  - `run(self -> None)`
  - `select_direction(self, w_dir -> None)`

## Internal Dependencies

- `commands.analysis` → `commands.analysis.mass_assembly`
- `commands.analysis` → `commands.analysis.mass_assembly`
- `commands.analysis` → `commands.analysis.mass_assembly`
- `commands.analysis` → `commands.analysis.material_takeoff`
- `commands.analysis` → `commands.analysis.material_takeoff`
- `commands.analysis` → `commands.analysis.solver`
- `commands.analysis` → `commands.analysis.solver`
- `commands.analysis` → `commands.analysis.stiffness_assembly`
- `commands.analysis` → `commands.analysis.stiffness_assembly`
- `commands.analysis` → `commands.analysis.stiffness_assembly`
- `commands.analysis` → `commands.analysis.stiffness_assembly`
- `commands.analysis` → `commands.analysis.structuralanalysis`
- `commands.analysis` → `commands.analysis.structuralanalysis`
- `commands.analysis.modal_analysis` → `commands.analysis.solver`
- `commands.analysis.structuralanalysis` → `commands.analysis.mass_assembly`
- `commands.analysis.structuralanalysis` → `commands.analysis.mass_assembly`
- `commands.analysis.structuralanalysis` → `commands.analysis.solver`
- `commands.analysis.structuralanalysis` → `commands.analysis.solver`
- `commands.analysis.structuralanalysis` → `commands.analysis.stiffness_assembly`
- `commands.analysis.structuralanalysis` → `commands.analysis.stiffness_assembly`

## Inheritance

- `commands.base.Command` extends `ABC`
- `commands.bulk_update.BulkUpdateCommand` extends `Command`
- `commands.create.CreateElementCommand` extends `Command`
- `commands.delete.DeleteElementsCommand` extends `Command`
- `commands.draw.AddDrawnElementCommand` extends `Command`
- `commands.replicate.ReplicateElementsCommand` extends `Command`
- `commands.update.UpdateElementCommand` extends `Command`

## Important Notes

- This document is generated using Python AST.
- Import relationships are statically inferred.
- Dynamic imports and runtime relationships may not appear.
- Class ownership and architectural responsibilities require human documentation.
- Refer to the source code for authoritative implementation details.

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.commands import project_commands as PC
from app.commands.registry import _discover_modules, _snake, build_registry
from app.commands.result import CommandResult


def _all_pc_command_classes() -> list[type]:
    return [
        cls
        for _, cls in inspect.getmembers(PC, inspect.isclass)
        if cls.__module__ == PC.__name__
    ]


def _make_mock_app() -> SimpleNamespace:
    mock_node = SimpleNamespace(unique_id=1, x=0.0, y=0.0, z=0.0, is_visible=True)
    mock_frame = SimpleNamespace(unique_id=2, is_visible=True)

    math_model = MagicMock()
    math_model.get_element_by_unique_id.side_effect = lambda uid: {
        1: mock_node,
        2: mock_frame,
    }.get(uid)
    math_model.get_selected.return_value = [mock_node]
    math_model.all_elements = {1: mock_node, 2: mock_frame}

    sel_mgr = MagicMock()
    sel_mgr.get_selected.return_value = [mock_node]
    sel_mgr.is_selected.return_value = True

    renderer = MagicMock()
    renderer.projection = "perspective"
    renderer.get_render_mode.return_value = "shaded"

    presentation = MagicMock()
    presentation.loads = SimpleNamespace(enabled=True)

    engine = MagicMock()
    engine.sel_mgr = sel_mgr
    engine.math_model = math_model
    engine.scene = SimpleNamespace(show_local_axes=False, grid=None)
    engine.renderer = renderer
    engine.presentation_renderer = presentation
    engine.draw_mgr = SimpleNamespace(is_active=False, start=MagicMock(), cancel=MagicMock())
    engine.plane_draw_mgr = SimpleNamespace(
        is_active=False,
        start_3pt=MagicMock(),
        start_2pt_z=MagicMock(),
        cancel=MagicMock(),
    )

    edit_ctrl = MagicMock()
    edit_ctrl.scene = math_model
    edit_ctrl.delete.return_value = SimpleNamespace(ok=True, message="1 silindi")
    edit_ctrl.replicate.return_value = SimpleNamespace(ok=True, message="1x çoğaltıldı")
    edit_ctrl.undo.return_value = SimpleNamespace(ok=True, message="Geri alındı")
    edit_ctrl.redo.return_value = SimpleNamespace(ok=True, message="Yinelendi")
    edit_ctrl.create.return_value = SimpleNamespace(ok=True, message="Oluşturuldu")
    edit_ctrl.update.return_value = SimpleNamespace(ok=True, message="Güncellendi")

    project = SimpleNamespace(
        math_model=math_model,
        scene=math_model,
        unit_system="KN_M",
        materials={},
        sections={},
        load_patterns={},
    )

    project_service = MagicMock()
    project_service.project = project
    project_service.file_path = None
    project_service.save_current.return_value = False

    panel_entry = SimpleNamespace(
        name="command_panel",
        title="Komut Satırı",
        instance=SimpleNamespace(visible=False, open=MagicMock(), close=MagicMock()),
    )
    panel_registry = MagicMock()
    panel_registry.get.side_effect = lambda name: panel_entry if name == "command_panel" else None
    panel_registry.all.return_value = [panel_entry]

    view_service = MagicMock()
    view_service.get_loads_visible.return_value = True

    visibility_service = MagicMock()
    visibility_service.show_only.return_value = True
    visibility_service.hide.return_value = True

    return SimpleNamespace(
        engine=engine,
        edit_controller=edit_ctrl,
        current_project=project,
        project_service=project_service,
        panel_registry=panel_registry,
        view_service=view_service,
        visibility_service=visibility_service,
        ui=MagicMock(),
        inspector=MagicMock(),
        command_queue=MagicMock(),
        request_quit=MagicMock(),
    )


def run_audit() -> dict[str, list[str]]:
    discovered = _discover_modules()
    reg = build_registry()
    pc_classes = _all_pc_command_classes()

    raw_conflicts = reg.conflicts() if callable(reg.conflicts) else reg.conflicts

    report: dict[str, list[str]] = {
        "discovered_modules": list(discovered),
        "registered_names": list(reg.list_names()),
        "registered_types": [t.__name__ for t in reg.list_types()],
        "conflicts": list(raw_conflicts),
        "missing_handlers": [],
        "cli_parse_ok": [],
        "cli_parse_fail": [],
        "dispatch_ok": [],
        "dispatch_broken": [],
    }

    for cls in pc_classes:
        if not reg.has_handler(cls):
            report["missing_handlers"].append(cls.__name__)

    cli_samples: list[tuple[str, list[str], bool]] = [
        ("new_project", [], True),
        ("undo", [], True),
        ("redo", [], True),
        ("delete_selected", [], True),
        ("fit_view", [], True),
        ("zoom_extents", [], True),
        ("toggle_2d", [], True),
        ("toggle_render_mode", [], True),
        ("clear_selection", [], True),
        ("show_all", [], True),
        ("panel", ["command_panel"], True),
        ("add_node", ["1.0", "2.5", "0.0"], True),
        ("add_node", ["hatali_sayi", "2.5"], False),
        ("replicate", ["3.0", "0.0", "0.0", "2"], True),
        ("replicate", ["3.0"], False),
        ("set_camera_preset", ["top"], True),
        ("set_render_mode", ["simple"], True),
        ("draw", ["line"], True),
        ("select", ["1", "2"], True),
        ("hide", ["1"], True),
        ("show_only", ["2"], True),
    ]

    for cmd_name, args, should_succeed in cli_samples:
        built = reg.build_by_name(cmd_name, args)
        ok = (built is not None) == should_succeed
        label = f"{cmd_name} {' '.join(args)}".strip()
        if ok:
            report["cli_parse_ok"].append(label)
        else:
            report["cli_parse_fail"].append(f"{label} (beklenen={should_succeed}, gelen={built})")

    dispatch_cases = [
        PC.NewProject(),
        PC.SaveProject(),
        PC.Undo(),
        PC.Redo(),
        PC.DeleteSelected(),
        PC.DeleteElements(uids=[1]),
        PC.ReplicateSelected(dx=3.0, dy=0.0, dz=0.0, count=2),
        PC.AddNode(x=1.0, y=2.0, z=3.0),
        PC.TogglePanel(name="command_panel"),
        PC.OpenPanel(name="command_panel"),
        PC.ClosePanel(name="command_panel"),
        PC.FitView(),
        PC.ZoomExtents(),
        PC.SetCameraPreset(preset="iso"),
        PC.Toggle2D(),
        PC.ToggleRenderMode(),
        PC.SetRenderMode(mode="simple"),
        PC.ToggleLoadsVisible(enabled=False),
        PC.ToggleLocalAxes(),
        PC.ClearSelection(),
        PC.SelectElements(uids=[1]),
        PC.ShowOnly(uids=[1]),
        PC.HideElements(uids=[1]),
        PC.ShowEntireModel(),
        PC.RefreshGeometry(),
        PC.StartDrawTool(mode="line"),
        PC.StartPlane3pt(),
        PC.StartPlane2ptZ(),
        PC.OpenInspector(),
        PC.QuitApp(),
    ]

    for cmd in dispatch_cases:
        app = _make_mock_app()
        cmd_label = type(cmd).__name__
        try:
            res: CommandResult = reg.dispatch(app, cmd)
            if res.handled:
                report["dispatch_ok"].append(f"{cmd_label} -> msg={res.message!r}")
            else:
                report["dispatch_broken"].append(f"{cmd_label} -> handled=False (msg={res.message!r})")
        except Exception as exc:
            report["dispatch_broken"].append(f"{cmd_label} -> EXCEPTION: {type(exc).__name__}: {exc}")

    return report


def test_audit_summary():
    r = run_audit()
    assert not r["conflicts"], f"Çakışmalar: {r['conflicts']}"
    assert not r["missing_handlers"], (
        f"\ndiscovered_modules={r['discovered_modules']}"
        f"\nregistered_types={r['registered_types']}"
        f"\nmissing_handlers={r['missing_handlers']}"
    )
    assert not r["cli_parse_fail"], f"CLI hataları: {r['cli_parse_fail']}"
    assert not r["dispatch_broken"], f"Dispatch hataları: {r['dispatch_broken']}"


if __name__ == "__main__":
    r = run_audit()
    for section, items in r.items():
        print(f"\n[{section.upper()}] ({len(items)})")
        for item in items:
            print(f"  - {item}")
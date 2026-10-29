# tests/test_s2k_panel.py
"""S2KPanel import/export akışı — sözleşme testleri.

Kapsam:
    - _execute_import: boş / dolu ctx, callback çağrısı, metadata
    - _run_handlers: tablo filtresi, sıralı router, fallback
    - _should_process: seçim mantığı
    - export: _parse_table_summary, _build_export_text (mock)
"""
from __future__ import annotations

import pandas as pd
import pytest

from domain.project import Project
from tools.s2k.loader import S2KParser
from tools.s2k.context import LoadContext
from ui.s2k_panel import S2KPanel


# ============================================================================
# FIXTURES
# ============================================================================
@pytest.fixture
def panel():
    """Callback toplayan izole panel."""
    imported: list[Project] = []
    p = S2KPanel(on_import_complete=imported.append)
    p._imported_for_test = imported   # testten erişim
    return p


@pytest.fixture
def empty_parser():
    """Geçerli ama boş parser — dosya okumaz."""
    return S2KParser()


@pytest.fixture
def minimal_ctx() -> LoadContext:
    """Tek node + tek frame üretecek minimum ctx."""
    from domain.definition import Section
    from data.enums import SectionType

    ctx = LoadContext()
    ctx.units_source_string = "N, mm, C"

    ctx.df_joints = pd.DataFrame([
        {"Joint": "1", "XorR": "0",    "Y": "0", "Z": "0"},
        {"Joint": "2", "XorR": "1000", "Y": "0", "Z": "0"},
    ])
    ctx.df_frame_conn = pd.DataFrame([
        {"Frame": "F1", "JointI": "1", "JointJ": "2"},
    ])
    ctx.df_frame_assign = pd.DataFrame([
        {"Frame": "F1", "AnalSect": "R1"},
    ])
    ctx.sections["R1"] = Section(
        name="R1",
        profile_type=SectionType.RECT,
        profile_params={"h": 300.0, "b": 200.0, "Area": 60000.0,
                        "I33": 4.5e8, "I22": 2.0e8, "J": 3.0e8},
    )
    return ctx


# ============================================================================
# 1. _execute_import — boş durum
# ============================================================================
def test_execute_import_empty_tables_calls_callback(panel, empty_parser):
    """Boş import_tables olsa bile callback çağrılır, boş Project döner."""
    panel.parser = empty_parser
    panel.import_tables = {}
    panel._execute_import()

    assert len(panel._imported_for_test) == 1
    proj = panel._imported_for_test[0]
    assert isinstance(proj, Project)
    assert len(proj.scene.frames) == 0
    assert len(proj.scene.nodes) == 0


def test_execute_import_without_parser_returns_early(panel):
    """parser yoksa callback çağrılmaz, log'a hata düşer."""
    panel.parser = None
    panel._execute_import()

    assert len(panel._imported_for_test) == 0
    assert any("[HATA]" in m for m in panel.log_messages)


def test_execute_import_without_callback_logs_error(empty_parser):
    """Callback bağlı değilse hata loglanır, crash yok."""
    panel = S2KPanel(on_import_complete=None)
    panel.parser = empty_parser
    panel.import_tables = {}
    panel._execute_import()

    assert any("Callback bağlı değil" in m for m in panel.log_messages)


def test_execute_import_callback_exception_is_caught(empty_parser):
    """Callback patlarsa panel yakalar, crash olmaz."""
    def boom(_):
        raise RuntimeError("boom")

    panel = S2KPanel(on_import_complete=boom)
    panel.parser = empty_parser
    panel.import_tables = {}
    panel._execute_import()

    assert any("[HATA]" in m for m in panel.log_messages)


# ============================================================================
# 2. _execute_import — dolu ctx (model inşası)
# ============================================================================
def test_execute_import_builds_frames_from_ctx(panel, empty_parser, minimal_ctx):
    """Handler ctx'ten gerçek model inşa edilir."""
    panel.parser = empty_parser
    panel.import_tables = {}

    # _run_handlers'ı atla, ctx doğrudan geçir
    from tools.s2k.loader import S2KLoader
    loader = S2KLoader()
    loader.parser = empty_parser
    new_proj, meta = loader.load_with_metadata(ctx=minimal_ctx)

    assert len(new_proj.scene.nodes) == 2
    assert len(new_proj.scene.frames) == 1
    assert meta.unit_system.value == "N, mm, C"


def test_loader_metadata_from_parser(empty_parser):
    """S2KMetadata doğru dolduruluyor."""
    from tools.s2k.loader import S2KLoader
    loader = S2KLoader()
    loader.parser = empty_parser

    ctx = LoadContext()
    ctx.units_source_string = "Ton. m. C"
    _, meta = loader.load_with_metadata(ctx=ctx)

    assert meta.curr_units_normalized == "Ton. m. C"
    assert meta.unit_system.value == "tonf, m, C"
    assert meta.program_name == ""   # boş parser


# ============================================================================
# 3. _run_handlers
# ============================================================================
def test_run_handlers_processes_selected_only(panel, empty_parser):
    """Sadece seçili tablolar işlenir."""
    panel.parser = empty_parser
    panel.import_tables = {
        "JOINT COORDINATES": pd.DataFrame([{"Joint": "1", "XorR": "0", "Y": "0", "Z": "0"}]),
        "MATERIAL PROPERTIES 01 - GENERAL": pd.DataFrame([{"Material": "S1"}]),
    }
    panel.selected_tables = {
        "JOINT COORDINATES": True,
        "MATERIAL PROPERTIES 01 - GENERAL": False,
    }

    ctx = panel._run_handlers()

    assert "1" in ctx.df_joints["Joint"].values
    assert len(ctx.materials) == 0   # material tablosu seçilmedi


def test_run_handlers_skips_empty_tables(panel, empty_parser):
    """Boş tablolar atlanır."""
    panel.parser = empty_parser
    panel.import_tables = {
        "JOINT COORDINATES": pd.DataFrame(),   # boş
    }
    panel.selected_tables = {"JOINT COORDINATES": True}

    ctx = panel._run_handlers()
    assert ctx.df_joints is None


def test_run_handlers_continues_on_handler_error(panel, empty_parser, caplog):
    """Bir handler patlarsa diğerleri devam eder."""
    panel.parser = empty_parser
    panel.import_tables = {
        "JOINT COORDINATES": pd.DataFrame([
            {"Joint": "1", "XorR": "invalid", "Y": "0", "Z": "0"},
        ]),
    }
    panel.selected_tables = {"JOINT COORDINATES": True}

    # Patlamamalı
    ctx = panel._run_handlers()
    assert ctx is not None


# ============================================================================
# 4. _should_process
# ============================================================================
def test_should_process_all_conditions(panel):
    panel.import_tables = {"T1": pd.DataFrame([{"a": 1}]),
                           "T2": pd.DataFrame()}
    panel.selected_tables = {"T1": True, "T2": True, "T3": True}

    assert panel._should_process("T1") is True
    assert panel._should_process("T2") is False   # boş
    assert panel._should_process("T3") is False   # tablo yok
    assert panel._should_process("nonexistent") is False


# ============================================================================
# 5. Export — _parse_table_summary
# ============================================================================
def test_parse_table_summary_empty():
    assert S2KPanel._parse_table_summary("") == []


def test_parse_table_summary_basic():
    text = (
        'TABLE: "JOINT COORDINATES"\n'
        'Joint=1 X=0 Y=0 Z=0\n'
        'Joint=2 X=1 Y=0 Z=0\n'
        'TABLE: "CONNECTIVITY - FRAME"\n'
        'Frame=F1 JointI=1 JointJ=2\n'
    )
    summary = S2KPanel._parse_table_summary(text)
    assert summary == [
        ("JOINT COORDINATES", 2),
        ("CONNECTIVITY - FRAME", 1),
    ]


def test_parse_table_summary_end_marker():
    text = (
        'TABLE: "A"\n'
        'line1\n'
        'END TABLE DATA\n'
        'TABLE: "B"\n'
        'line2\n'
    )
    summary = S2KPanel._parse_table_summary(text)
    assert summary == [("A", 1)]   # END'den sonrası yok


# ============================================================================
# 6. Export — _build_export_text
# ============================================================================
def test_build_export_text_without_project_logs_error(panel):
    panel.get_project = lambda: None
    ok = panel._build_export_text()
    assert ok is False
    assert any("Aktif proje yok" in m for m in panel.log_messages)


def test_build_export_text_with_empty_project(panel, monkeypatch):
    """Boş proje export edilir (exporter stub)."""
    from tools import s2k_exporter

    def fake_export(project, selected_elements=None):
        return 'TABLE: "JOINT COORDINATES"\nJoint=1 X=0 Y=0 Z=0\n'

    monkeypatch.setattr(s2k_exporter.S2KExporter, "export", staticmethod(fake_export))

    panel.get_project = lambda: Project()
    panel.get_selected_elements = lambda: []

    ok = panel._build_export_text()
    assert ok is True
    assert panel.export_text is not None
    assert panel.export_table_summary == [("JOINT COORDINATES", 1)]


def test_build_export_text_exporter_error(panel, monkeypatch):
    from tools import s2k_exporter

    def boom(*args, **kwargs):
        raise RuntimeError("exporter down")

    monkeypatch.setattr(s2k_exporter.S2KExporter, "export", staticmethod(boom))

    panel.get_project = lambda: Project()
    ok = panel._build_export_text()

    assert ok is False
    assert any("Export üretilemedi" in m for m in panel.log_messages)


# ============================================================================
# 7. Export — _write_export_file
# ============================================================================
def test_write_export_file_without_text_logs_error(panel):
    panel.export_text = None
    panel.export_path = "dummy.s2k"
    panel._write_export_file()
    assert any("Önce export metni" in m for m in panel.log_messages)


def test_write_export_file_without_path_logs_error(panel):
    panel.export_text = "content"
    panel.export_path = None
    panel._write_export_file()
    assert any("Kayıt yolu" in m for m in panel.log_messages)


def test_write_export_file_success(panel, tmp_path):
    out = tmp_path / "out.s2k"
    panel.export_text = "hello"
    panel.export_path = str(out)
    panel._write_export_file()

    assert out.read_text(encoding="utf-8") == "hello"
    assert any("Yazıldı" in m for m in panel.log_messages)


# ============================================================================
# 8. Log helpers
# ============================================================================
def test_log_prefixes(panel):
    panel._log_info("info")
    panel._log_warn("warn")
    panel._log_error("err")
    assert panel.log_messages == [
        "[BİLGİ] info",
        "[UYARI] warn",
        "[HATA] err",
    ]
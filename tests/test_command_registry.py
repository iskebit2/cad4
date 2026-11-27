# tests/test_command_registry.py
from __future__ import annotations

import dataclasses
import traceback

from app.commands.base import Command, _COMMAND_BY_TYPE, _CURRENT_APP, command_for
from app.commands.registry import get_registry



def _separator(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def _section(title: str) -> None:
    print()
    print("-" * 70)
    print(title)
    print("-" * 70)


def test_bind_app_called() -> None:
    _separator("1. _CURRENT_APP durumu")
    app = _CURRENT_APP[0]
    if app is None:
        print("HATA: bind_app() çağrılmamış. _CURRENT_APP[0] = None")
        print("Beklenen: main.py içinde bind_app(app) çağrılmalı.")
    else:
        print(f"OK: _CURRENT_APP[0] = {type(app).__name__}")


def test_command_by_type() -> None:
    _separator("2. _COMMAND_BY_TYPE kayıtları")
    if not _COMMAND_BY_TYPE:
        print("BOŞ: @command dekoratörü hiçbir payload yakalamamış.")
        print("Olası neden: polygon_commands.py import edilmemiş.")
        print("Kontrol: app/commands/__init__.py içinde polygon_commands import var mı?")
        return
    print(f"Toplam {len(_COMMAND_BY_TYPE)} payload kayıtlı:")
    for payload_type, cmd_type in _COMMAND_BY_TYPE.items():
        print(f"  {payload_type.__name__:35s} -> {cmd_type.__module__}.{cmd_type.__name__}")


def test_polygon_commands_imported() -> None:
    _separator("3. polygon_commands modülü import kontrolü")
    import sys
    mod_name = "app.commands.polygon_commands"
    if mod_name in sys.modules:
        print(f"OK: {mod_name} import edilmiş.")
        mod = sys.modules[mod_name]
        print(f"  Modül dosyası: {mod.__file__}")
        payloads = [
            name for name in dir(mod)
            if isinstance(getattr(mod, name), type)
            and dataclasses.is_dataclass(getattr(mod, name))
        ]
        print(f"  Dataclass payload'lar ({len(payloads)}):")
        for p in payloads:
            print(f"    - {p}")
    else:
        print(f"HATA: {mod_name} import edilmemiş.")
        print("Neden: app/commands/__init__.py veya impl.py bu modülü import etmiyor.")
        print("Kontrol: `from app.commands import polygon_commands` satırı nerede?")
        try:
            import app.commands.polygon_commands  # noqa: F401
            print("Manuel import başarılı.")
        except Exception:
            print("Manuel import da başarısız:")
            traceback.print_exc()


def test_registry_contents() -> None:
    _separator("4. CommandRegistry içeriği")
    try:
        registry = get_registry()
    except Exception:
        print("HATA: get_registry() başarısız:")
        traceback.print_exc()
        return

    names = registry.list_names()
    print(f"Registry'de {len(names)} komut kayıtlı:")
    for name in names:
        cmd_type = registry._types.get(name)
        meta = registry.get_meta_by_name(name)
        visible = " [UI]" if (meta and meta.visible_in_ui) else ""
        print(f"  {name:40s} {cmd_type.__name__ if cmd_type else '?'}{visible}")


def test_polygon_payloads_in_registry() -> None:
    _separator("5. polygon_commands payload'ları registry'de mi?")
    payload_types = [
        "SetPolygonType",
        "SetPolygonDistType",
        "SetPolygonColor",
        "PolygonToPlane",
        "ApplyPolygonAssoc",
        "AssignPolygonAreaLoad",
        "RemovePolygonAreaLoad",
        "SetTransferGridSettings",
        "StagePolygonAreaTransfer",
        "StagePolygonWindTransfer",
        "CommitFrameTransferBatch",
        "ResetWindZoneOverride",
    ]
    registry = get_registry()
    for payload_name in payload_types:
        payload_type = None
        for pt, ct in _COMMAND_BY_TYPE.items():
            if pt.__name__ == payload_name:
                payload_type = pt
                break
        if payload_type is None:
            print(f"  {payload_name:35s} -> @command dekoratörü YOK")
            continue
        cmd_type = _COMMAND_BY_TYPE[payload_type]
        snake = _snake(cmd_type.__name__)
        if snake.endswith("_command"):
            snake = snake[: -len("_command")]
        if registry.has(snake):
            print(f"  {payload_name:35s} -> OK ({snake})")
        else:
            print(f"  {payload_name:35s} -> KAYIT YOK (beklenen isim: {snake})")


def test_factory_runs() -> None:
    _separator("6. Factory her komut için çalışıyor mu?")
    registry = get_registry()
    for name in registry.list_names():
        cmd = registry.build(name, [])
        status = "OK" if cmd is not None else "None (factory args bekliyor veya desteklenmiyor)"
        print(f"  {name:40s} -> {status}")


def test_command_for_payload() -> None:
    _separator("7. command_for(payload_type) lookup")
    if not _COMMAND_BY_TYPE:
        print("_COMMAND_BY_TYPE boş; atlanıyor.")
        return
    for payload_type in list(_COMMAND_BY_TYPE.keys()):
        cmd_cls = command_for(payload_type)
        if cmd_cls is not None:
            print(f"  {payload_type.__name__:35s} -> OK ({cmd_cls.__name__})")
        else:
            print(f"  {payload_type.__name__:35s} -> BULUNAMADI")


def _snake(name: str) -> str:
    import re
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def main() -> None:
    test_bind_app_called()
    test_polygon_commands_imported()
    test_command_by_type()
    test_registry_contents()
    test_polygon_payloads_in_registry()
    test_factory_runs()
    test_command_for_payload()
    _separator("TEST BİTTİ")


if __name__ == "__main__":
    main()
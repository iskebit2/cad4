# app/commands/visibility.py
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from app.commands.base import Command, CommandResult

# ----------------------------------------------------------------------
# ShowOnly — sadece verilen elemanları göster
# ----------------------------------------------------------------------
@dataclass
class ShowOnly(Command):
    uids: list[int] | None = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        ok = self._app.visibility_service.show_only(self.uids)
        if not ok:
            return CommandResult(handled=False, message="Model hazır değil.")
        count = len(self.uids) if self.uids else 0
        if count:
            return CommandResult(
                handled=True,
                message=f"Sadece {count} eleman gösteriliyor.",
            )
        return CommandResult(handled=True, message="Filtre temizlendi (tümü görünür).")

    def undo(self) -> None:
        self._app.visibility_service.show_all()

    def __post_init__(self) -> None:
        self._app = None
        # Opsiyonel: seçimden otomatik uid toplama
        # if self.uids is None and self._app is not None:
        #     self.uids = [uid for uid in self._app.selection.ids()]


# ----------------------------------------------------------------------
# Hide — verilen elemanları gizle
# ----------------------------------------------------------------------
@dataclass
class Hide(Command):
    uids: list[int] | None = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if not self.uids:
            # Seçili elemanları gizle
            uids = self._selected_uids()
            if not uids:
                return CommandResult(
                    handled=False,
                    message="Gizlenecek eleman yok (seçim boş).",
                )
            self.uids = uids
        ok = self._app.visibility_service.hide(self.uids)
        if not ok:
            return CommandResult(handled=False, message="Model hazır değil.")
        return CommandResult(
            handled=True,
            message=f"{len(self.uids)} eleman gizlendi.",
        )

    def undo(self) -> None:
        if self.uids:
            self._app.visibility_service.unhide(self.uids)

    def _selected_uids(self) -> list[int]:
        sel = getattr(self._app, "selection", None)
        if sel is None:
            return []
        for attr in ("ids", "get_ids", "selected_ids"):
            fn = getattr(sel, attr, None)
            if callable(fn):
                try:
                    return [int(u) for u in fn()]
                except TypeError:
                    continue
            elif isinstance(fn, (list, set, tuple)):
                return [int(u) for u in fn]
        return []

    def __post_init__(self) -> None:
        self._app = None


# ----------------------------------------------------------------------
# ShowAll — tüm gizlemeleri ve filtreleri temizle
# ----------------------------------------------------------------------
@dataclass
class ShowAll(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app.visibility_service.show_all()
        return CommandResult(handled=True, message="Tüm elemanlar görünür.")

    def undo(self) -> None:
        # show_all geri alınamaz (durum bilgisi saklanmıyor)
        pass

    def __post_init__(self) -> None:
        self._app = None


# ----------------------------------------------------------------------
# ToggleLoadsVisible — mevcut (referans için)
# ----------------------------------------------------------------------
@dataclass
class ToggleLoadsVisible(Command):
    enabled: bool | None = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        state = self._app.visibility_service.toggle_loads_visible(self.enabled)
        return CommandResult(
            handled=True,
            message=f"Yük görünürlüğü: {'Açık' if state else 'Kapalı'}",
        )

    def undo(self) -> None:
        self._app.visibility_service.toggle_loads_visible(
            not self.enabled if self.enabled is not None else None
        )

    def __post_init__(self) -> None:
        self._app = None

# ======================================================================
# Taban: ShowKeyCommand
# ======================================================================
@dataclass
class ShowKeyCommand(Command):
    """engine.show[key] değerini toggle eden komutların tabanı."""

    enabled: bool | None = None

    # Alt sınıflar bunu override eder
    show_key: ClassVar[str] = ""
    label: ClassVar[str] = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        eng = self._app.engine
        if eng is None:
            return CommandResult(handled=False, message="Engine hazır değil.")

        show = getattr(eng, "show", None)
        if show is None or self.show_key not in show:
            return CommandResult(
                handled=False,
                message=f"'{self.show_key}' anahtarı engine.show içinde yok.",
            )

        old = bool(show[self.show_key])
        new = (not old) if self.enabled is None else bool(self.enabled)
        show[self.show_key] = new

        # Yan etkiler (renderer state)
        self._apply_side_effects(eng, new)

        name = self.label or self.show_key
        return CommandResult(
            handled=True,
            message=f"{name}: {'Açık' if new else 'Kapalı'}",
        )

    def undo(self) -> None:
        if self.enabled is None:
            # Toggle'ı geri al
            eng = self._app.engine
            if eng is not None and hasattr(eng, "show"):
                eng.show[self.show_key] = not bool(eng.show[self.show_key])
                self._apply_side_effects(eng, eng.show[self.show_key])
        else:
            eng = self._app.engine
            if eng is not None and hasattr(eng, "show"):
                eng.show[self.show_key] = not bool(self.enabled)
                self._apply_side_effects(eng, eng.show[self.show_key])

    def _apply_side_effects(self, eng, state: bool) -> None:
        """Alt sınıflar gerekirse renderer state'ini günceller."""
        pass

    def __post_init__(self) -> None:
        self._app = None


# ======================================================================
# Kısayol komutları — her anahtar için
# ======================================================================
@dataclass
class ToggleScene(ShowKeyCommand):
    show_key: ClassVar[str] = "scene"
    label: ClassVar[str] = "Sahne"


@dataclass
class ToggleGrid(ShowKeyCommand):
    show_key: ClassVar[str] = "grid"
    label: ClassVar[str] = "Grid"


@dataclass
class TogglePolygon(ShowKeyCommand):
    show_key: ClassVar[str] = "polygon"
    label: ClassVar[str] = "Polygon"


@dataclass
class ToggleLines(ShowKeyCommand):
    show_key: ClassVar[str] = "lines"
    label: ClassVar[str] = "Çizgiler"


@dataclass
class ToggleArea(ShowKeyCommand):
    show_key: ClassVar[str] = "area"
    label: ClassVar[str] = "Area"


@dataclass
class ToggleFrame(ShowKeyCommand):
    show_key: ClassVar[str] = "frame"
    label: ClassVar[str] = "Frame"


@dataclass
class ToggleLink(ShowKeyCommand):
    show_key: ClassVar[str] = "link"
    label: ClassVar[str] = "Link"


@dataclass
class ToggleNode(ShowKeyCommand):
    show_key: ClassVar[str] = "node"
    label: ClassVar[str] = "Node"


@dataclass
class ToggleRestraint(ShowKeyCommand):
    show_key: ClassVar[str] = "restraint"
    label: ClassVar[str] = "Mesnet"


@dataclass
class ToggleInteraction(ShowKeyCommand):
    show_key: ClassVar[str] = "interaction"
    label: ClassVar[str] = "Etkileşim"


@dataclass
class ToggleSnap(ShowKeyCommand):
    show_key: ClassVar[str] = "snap"
    label: ClassVar[str] = "Snap"


@dataclass
class ToggleToolPreview(ShowKeyCommand):
    show_key: ClassVar[str] = "tool_preview"
    label: ClassVar[str] = "Araç Önizleme"


@dataclass
class TogglePlanePreview(ShowKeyCommand):
    show_key: ClassVar[str] = "plane_preview"
    label: ClassVar[str] = "Düzlem Önizleme"


@dataclass
class TogglePresentationAny(ShowKeyCommand):
    show_key: ClassVar[str] = "presentation_any"
    label: ClassVar[str] = "Sunum"


@dataclass
class ToggleLoads(ShowKeyCommand):
    show_key: ClassVar[str] = "loads"
    label: ClassVar[str] = "Yükler"

    def _apply_side_effects(self, eng, state: bool) -> None:
        # LoadRenderer'ı da senkronize et
        pres = getattr(eng, "presentation_renderer", None)
        if pres is not None:
            lr = getattr(pres, "loads", None)
            if lr is not None:
                lr.enabled = state
                if state and getattr(eng, "math_model", None) is not None:
                    try:
                        lr.update(eng.math_model, camera_scale=1.0, scene_size=1.0)
                    except Exception:
                        pass


@dataclass
class ToggleZones(ShowKeyCommand):
    show_key: ClassVar[str] = "zones"
    label: ClassVar[str] = "Zone'lar"


@dataclass
class ToggleWindVector(ShowKeyCommand):
    show_key: ClassVar[str] = "wind_vector"
    label: ClassVar[str] = "Rüzgar Vektörü"


@dataclass
class ToggleLabels(ShowKeyCommand):
    show_key: ClassVar[str] = "labels"
    label: ClassVar[str] = "Etiketler"


@dataclass
class ToggleGridLabels(ShowKeyCommand):
    show_key: ClassVar[str] = "grid_labels"
    label: ClassVar[str] = "Grid Etiketleri"


@dataclass
class ToggleSelectedLabels(ShowKeyCommand):
    show_key: ClassVar[str] = "selected_labels"
    label: ClassVar[str] = "Seçili Etiketler"


@dataclass
class ToggleGlobalAxis(ShowKeyCommand):
    show_key: ClassVar[str] = "global_axis"
    label: ClassVar[str] = "Global Eksen"


@dataclass
class ToggleLocalAxes(ShowKeyCommand):
    show_key: ClassVar[str] = "local_axes"
    label: ClassVar[str] = "Yerel Eksenler"

    def _apply_side_effects(self, eng, state: bool) -> None:
        print("_apply_side_effects", state)
        if eng.scene is not None:
            eng.scene.show_local_axes = state


# ======================================================================
# Genel ToggleShow — key parametreli
# ======================================================================
@dataclass
class ToggleShow(Command):
    key: str = ""
    enabled: bool | None = None

    _VALID_KEYS: ClassVar[set[str]] = {
        "scene", "grid", "polygon", "lines", "area", "frame", "link",
        "node", "restraint", "interaction", "snap", "tool_preview",
        "plane_preview", "presentation_any", "loads", "zones",
        "wind_vector", "labels", "grid_labels", "selected_labels",
        "global_axis", "local_axes",
    }

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        eng = self._app.engine
        if eng is None:
            return CommandResult(handled=False, message="Engine hazır değil.")

        key = (self.key or "").strip()
        if not key:
            return CommandResult(
                handled=False,
                message=f"Anahtar belirtilmedi. Geçerli: {sorted(self._VALID_KEYS)}",
            )
        if key not in self._VALID_KEYS:
            return CommandResult(
                handled=False,
                message=f"Geçersiz anahtar: '{key}'. Geçerli: {sorted(self._VALID_KEYS)}",
            )

        show = getattr(eng, "show", None)
        if show is None:
            return CommandResult(handled=False, message="engine.show yok.")

        old = bool(show.get(key, False))
        new = (not old) if self.enabled is None else bool(self.enabled)
        show[key] = new

        # Loads için özel yan etki
        if key == "loads":
            pres = getattr(eng, "presentation_renderer", None)
            if pres is not None:
                lr = getattr(pres, "loads", None)
                if lr is not None:
                    lr.enabled = new
                    if new and getattr(eng, "math_model", None) is not None:
                        try:
                            lr.update(eng.math_model, camera_scale=1.0, scene_size=1.0)
                        except Exception:
                            pass

        return CommandResult(
            handled=True,
            message=f"{key}: {'Açık' if new else 'Kapalı'}",
        )

    def undo(self) -> None:
        eng = self._app.engine
        if eng is None or not hasattr(eng, "show"):
            return
        if self.key in eng.show:
            eng.show[self.key] = not bool(eng.show[self.key])

    def __post_init__(self) -> None:
        self._app = None


# ======================================================================
# ShowAll / ShowNone — toplu
# ======================================================================
@dataclass
class ShowAllKeys(Command):
    """Tüm show anahtarlarını açar."""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        eng = self._app.engine
        if eng is None or not hasattr(eng, "show"):
            return CommandResult(handled=False, message="Engine hazır değil.")
        for k in eng.show:
            eng.show[k] = True
        return CommandResult(handled=True, message="Tüm görünürlük açıldı.")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class HideAllKeys(Command):
    """Tüm show anahtarlarını kapatır (loads ve scene hariç tutulabilir)."""

    keep_core: bool = True   # scene, grid, interaction, snap açık kalsın

    _CORE = ("scene", "grid", "interaction", "snap")

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        eng = self._app.engine
        if eng is None or not hasattr(eng, "show"):
            return CommandResult(handled=False, message="Engine hazır değil.")
        for k in eng.show:
            if self.keep_core and k in self._CORE:
                eng.show[k] = True
            else:
                eng.show[k] = False
        return CommandResult(handled=True, message="Tüm görünürlük kapatıldı.")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None

_ALL_TYPES: list[type] = [
    Hide,
    ShowAll,
    ShowOnly,
    ToggleLoadsVisible,
    # Yeni toggle komutları
    ToggleScene, ToggleGrid, TogglePolygon, ToggleLines,
    ToggleArea, ToggleFrame, ToggleLink, ToggleNode,
    ToggleRestraint, ToggleInteraction, ToggleSnap,
    ToggleToolPreview, TogglePlanePreview, TogglePresentationAny,
    ToggleLoads, ToggleZones, ToggleWindVector,
    ToggleLabels, ToggleGridLabels, ToggleSelectedLabels,
    ToggleGlobalAxis, ToggleLocalAxes,
    ToggleShow, ShowAllKeys, HideAllKeys,
]
def register(registry) -> None:
    for cmd_type in _ALL_TYPES:
        registry.register(cmd_type)
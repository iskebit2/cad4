# app/settings/shortcut_store.py
from __future__ import annotations

import json
from pathlib import Path

from app.settings.app_paths import shortcuts_file


class ShortcutStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or shortcuts_file()
        self._overrides: dict[str, str] | None = None

    def load(self) -> dict[str, str]:
        if self._overrides is not None:
            return self._overrides
        if not self.path.exists():
            self._overrides = {}
            return self._overrides
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._overrides = {str(k): str(v) for k, v in raw.items() if isinstance(v, str)}
        return self._overrides

    def save(self, overrides: dict[str, str]) -> None:
        self._overrides = dict(overrides)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._overrides, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def resolve(self, cmd_id: str, default: str) -> str:
        return self.load().get(cmd_id, default)
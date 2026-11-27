# ui/panels/polygon/topbar.py
from __future__ import annotations

from imgui_bundle import imgui

from ui.base.inspector_panel import InspectorContext


_SMALL_BUTTON_SIZE = imgui.ImVec2(26, 22)
_ICON_BUTTON_SIZE = imgui.ImVec2(26, 22)


class TopBar:
    selection_commands: tuple[str, ...] = (
        "selection.delete",
        "selection.copy",
        "selection.duplicate",
        "selection.select_all",
    )
    panel_commands: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        domain: str,
        selection_commands: tuple[str, ...] | None = None,
        panel_commands: tuple[str, ...] | None = None,
    ) -> None:
        self.domain = domain
        if selection_commands is not None:
            self.selection_commands = selection_commands
        if panel_commands is not None:
            self.panel_commands = panel_commands

    def draw(self, ctx: InspectorContext) -> None:
        self._draw_selection_info(ctx)
        imgui.same_line()
        self._draw_selection_actions(ctx)
        imgui.same_line()
        self._draw_domain_actions(ctx)

    def _draw_selection_info(self, ctx: InspectorContext) -> None:
        primary = ctx.primary
        if primary is None:
            imgui.text_disabled("Seçim yok")
            return
        label = getattr(primary, "label", "") or f"{type(primary).__name__}"
        uid = getattr(primary, "unique_id", None)
        count = len(ctx.selection)
        suffix = f"  (+{count - 1})" if count > 1 else ""
        imgui.text_colored(
            imgui.ImVec4(0.55, 0.85, 1.0, 1.0),
            f"{label} (id={uid}){suffix}",
        )

    def _draw_selection_actions(self, ctx: InspectorContext) -> None:
        for command_id in self.selection_commands:
            self._draw_command_button(ctx, command_id, size=_ICON_BUTTON_SIZE)

    def _draw_domain_actions(self, ctx: InspectorContext) -> None:
        for command_id in self.panel_commands:
            self._draw_command_button(ctx, command_id, size=_SMALL_BUTTON_SIZE)

    def _draw_command_button(
        self,
        ctx: InspectorContext,
        command_id: str,
        *,
        size: imgui.ImVec2,
    ) -> None:
        command = self._resolve(ctx, command_id)
        if command is None:
            return
        if command.visible is not None and not command.visible(ctx):
            return
        enabled = command.enabled is None or command.enabled(ctx)
        if not enabled:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0)
            )
        label = command.icon or command.label
        clicked = imgui.button(f"{label}##{command_id}", size)
        if not enabled:
            imgui.pop_style_color()
        if imgui.is_item_hovered() and command.tooltip:
            imgui.set_tooltip(command.tooltip)
        if clicked and enabled:
            ctx.run(command_id)

    @staticmethod
    def _resolve(ctx: InspectorContext, command_id: str):
        cmds = ctx.commands()
        if cmds is None:
            return None
        return cmds.get(command_id)
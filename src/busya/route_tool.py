"""The tool the LLM orchestrator calls to pick the next stage.

Mirrors `handoff.py`: an in-process MCP server whose handler writes the choice
straight into a slot the orchestrator reads once the assistant is done.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, create_sdk_mcp_server, tool

from .state import Stage

SERVER_NAME = "busya_route"
TOOL_NAME = f"mcp__{SERVER_NAME}__select_next_stage"


@dataclass(slots=True)
class RouteSlot:
    """Collects the next stage the orchestrator picked."""

    target: Stage | None = None


def build_route_server(targets: tuple[Stage, ...], slot: RouteSlot) -> tuple[McpSdkServerConfig, str]:
    """Build an in-process MCP server exposing `select_next_stage` for one decision."""
    target_list = ", ".join(t.value for t in targets)
    description = (
        "Record the stage that should run next. Call this exactly once, as the very "
        f"last thing you do. Valid targets: {target_list}."
    )

    @tool("select_next_stage", description, {"target": str})
    async def select_next_stage(args: dict[str, Any]) -> dict[str, Any]:
        raw = str(args.get("target", "")).strip().lower()
        try:
            target = Stage(raw)
        except ValueError:
            return _error(f"Unknown target {raw!r}. Valid targets: {target_list}.")
        if target not in targets:
            return _error(f"{target.value} is not a valid next stage. Valid targets: {target_list}.")
        slot.target = target
        return {"content": [{"type": "text", "text": f"Next stage set to {target.value}."}]}

    return create_sdk_mcp_server(SERVER_NAME, tools=[select_next_stage]), TOOL_NAME


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}

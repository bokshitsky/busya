"""The tool a stage assistant calls to pass control itself.

The tool runs in-process (an SDK MCP server), so its handler can write the
decision straight into a slot the node reads once the assistant is done.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, create_sdk_mcp_server, tool

from .state import ALLOWED_TARGETS, HandoffRequest, Stage

SERVER_NAME = "busya"
TOOL_NAME = f"mcp__{SERVER_NAME}__handoff"


@dataclass(slots=True)
class HandoffSlot:
    """Collects the handoff a single stage run asked for."""

    request: HandoffRequest | None = None


def build_handoff_server(
    source: Stage, slot: HandoffSlot
) -> tuple[McpSdkServerConfig, str]:
    """Build an in-process MCP server exposing `handoff` for one stage run."""
    targets = ALLOWED_TARGETS[source]
    target_list = ", ".join(t.value for t in targets)
    description = (
        "Pass control to the next pipeline stage. Call this once, as the very last "
        "thing you do, after your final report is written. "
        f"Valid targets: {target_list}."
    )

    @tool("handoff", description, {"target": str, "reason": str})
    async def handoff(args: dict[str, Any]) -> dict[str, Any]:
        raw = str(args.get("target", "")).strip().lower()
        reason = str(args.get("reason", "")).strip()
        try:
            target = Stage(raw)
        except ValueError:
            return _error(f"Unknown target {raw!r}. Valid targets: {target_list}.")
        if target not in targets:
            return _error(
                f"{source.value} cannot hand off to {target.value}. "
                f"Valid targets: {target_list}."
            )
        slot.request = HandoffRequest(source=source, target=target, reason=reason)
        return {
            "content": [
                {"type": "text", "text": f"Handoff to {target.value} recorded."}
            ]
        }

    return create_sdk_mcp_server(SERVER_NAME, tools=[handoff]), TOOL_NAME


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def handoff_hint(source: Stage) -> str:
    """Prompt text telling the assistant it owns the routing decision."""
    targets = ALLOWED_TARGETS[source]
    lines = "\n".join(f"- {t.value}" for t in targets)
    return (
        "# Routing\n"
        "You decide where control goes next. After writing your final report, call "
        f"the `handoff` tool exactly once with one of these targets:\n{lines}\n"
        "Give a one-sentence reason. If you do not call it, the pipeline stops here."
    )

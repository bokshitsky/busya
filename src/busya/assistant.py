"""Running one Claude Agent SDK assistant to completion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    McpServerConfig,
    PermissionMode,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)


@dataclass(slots=True)
class AssistantSpec:
    """Everything one assistant run needs."""

    system_prompt: str
    prompt: str
    tools: list[str]
    mcp_servers: dict[str, McpServerConfig] = field(default_factory=dict)
    model: str | None = None
    max_turns: int = 40
    cwd: Path | None = None
    permission_mode: PermissionMode = "acceptEdits"


@dataclass(slots=True)
class AssistantResult:
    """What one assistant run produced."""

    text: str
    tool_calls: list[str] = field(default_factory=list)
    num_turns: int = 0
    cost_usd: float | None = None
    is_error: bool = False
    terminal_reason: str | None = None


async def run_assistant(spec: AssistantSpec) -> AssistantResult:
    """Run an assistant for a single stage and return its final report."""
    options = ClaudeAgentOptions(
        system_prompt=spec.system_prompt,
        tools=spec.tools,
        allowed_tools=spec.tools,
        mcp_servers=spec.mcp_servers,
        model=spec.model,
        max_turns=spec.max_turns,
        cwd=spec.cwd,
        permission_mode=spec.permission_mode,
        # Ignore ~/.claude and project settings so a run depends only on this config.
        setting_sources=[],
    )

    texts: list[str] = []
    tool_calls: list[str] = []
    result: ResultMessage | None = None

    async with ClaudeSDKClient(options=options) as client:
        await client.query(spec.prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        texts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_calls.append(block.name)
            elif isinstance(message, ResultMessage):
                result = message

    text = (result.result if result and result.result else "\n".join(texts)).strip()
    return AssistantResult(
        text=text,
        tool_calls=tool_calls,
        num_turns=result.num_turns if result else 0,
        cost_usd=result.total_cost_usd if result else None,
        is_error=bool(result and result.is_error),
        terminal_reason=result.terminal_reason if result else None,
    )

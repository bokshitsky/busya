"""The tool a reviewer calls to leave one structured comment.

Mirrors `handoff.py`: an in-process MCP server whose handler writes straight
into a slot the caller reads once the assistant is done.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, create_sdk_mcp_server, tool

from .state import ReviewComment

SERVER_NAME = "busya_review"
TOOL_NAME = f"mcp__{SERVER_NAME}__add_comment"


@dataclass(slots=True)
class ReviewCommentSlot:
    """Collects every comment left during one review run."""

    comments: list[ReviewComment] = field(default_factory=list)


def build_review_comment_server(slot: ReviewCommentSlot) -> tuple[McpSdkServerConfig, str]:
    """Build an in-process MCP server exposing `add_comment` for one review run."""
    description = (
        "Leave one review comment pinned to a file and line. Call it once per "
        "issue you find — do not bundle multiple issues into one call."
    )

    @tool("add_comment", description, {"file": str, "line": int, "comment": str})
    async def add_comment(args: dict[str, Any]) -> dict[str, Any]:
        file = str(args.get("file", "")).strip()
        comment = str(args.get("comment", "")).strip()
        try:
            line = int(args.get("line", 0))
        except (TypeError, ValueError):
            return _error("`line` must be an integer.")
        if not file or not comment:
            return _error("`file` and `comment` are required.")
        slot.comments.append(ReviewComment(file=file, line=line, comment=comment))
        return {"content": [{"type": "text", "text": f"Comment recorded for {file}:{line}."}]}

    return create_sdk_mcp_server(SERVER_NAME, tools=[add_comment]), TOOL_NAME


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}

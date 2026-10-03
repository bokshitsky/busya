"""The four stage nodes."""

from __future__ import annotations

import logging
from collections.abc import Awaitable
from typing import Any, Protocol

from claude_agent_sdk import McpServerConfig
from langgraph.graph import END
from langgraph.types import Command

from .assistant import AssistantSpec, run_assistant
from .config import PipelineConfig
from .handoff import SERVER_NAME, HandoffSlot, build_handoff_server, handoff_hint
from .prompts import SYSTEM_PROMPTS, review_instructions_block, reviewer_focus_block, stage_prompt
from .review_tool import SERVER_NAME as REVIEW_SERVER_NAME
from .review_tool import ReviewCommentSlot, build_review_comment_server
from .state import ARTIFACT_KEY, PipelineState, Stage, StageRecord, context_block

logger = logging.getLogger(__name__)

NodeReturn = PipelineState | Command[Any]


class StageNode(Protocol):
    """A LangGraph node. The parameter must be named `state` to satisfy LangGraph."""

    def __call__(self, state: PipelineState) -> Awaitable[NodeReturn]: ...


def build_stage_node(stage: Stage, config: PipelineConfig) -> StageNode:
    """Build the node that runs one stage's assistant.

    The assistant gets a `handoff` tool and can route itself; if it calls it,
    that decision wins and the node returns a `Command(goto=...)`. If it
    doesn't, the node just records its output and a conditional edge asks the
    orchestrator where to go instead.
    """

    async def node(state: PipelineState) -> NodeReturn:
        slot = HandoffSlot()
        tools = config.tools_for(stage)
        server, tool_name = build_handoff_server(stage, slot)
        mcp_servers: dict[str, McpServerConfig] = {SERVER_NAME: server}
        tools.append(tool_name)

        comment_slot: ReviewCommentSlot | None = None
        extra = ""
        if stage is Stage.CODING:
            extra = reviewer_focus_block(config.review_instructions)
        if stage is Stage.REVIEW:
            comment_slot = ReviewCommentSlot()
            comment_server, comment_tool = build_review_comment_server(comment_slot)
            mcp_servers[REVIEW_SERVER_NAME] = comment_server
            tools.append(comment_tool)
            extra = review_instructions_block(config.review_instructions)

        logger.info("stage %s: starting", stage.value)
        result = await run_assistant(
            AssistantSpec(
                system_prompt=SYSTEM_PROMPTS[stage],
                prompt=stage_prompt(
                    stage, context_block(state, exclude=stage), handoff_hint=handoff_hint(stage), extra=extra
                ),
                tools=tools,
                mcp_servers=mcp_servers,
                model=config.model,
                max_turns=config.max_turns[stage],
                label=stage.value,
                cwd=config.cwd,
                permission_mode=config.permission_mode,
            )
        )
        logger.info(
            "stage %s: done in %d turns (%s), handoff=%s",
            stage.value,
            result.num_turns,
            f"${result.cost_usd:.4f}" if result.cost_usd is not None else "cost n/a",
            slot.request.target.value if slot.request else "none",
        )

        record = StageRecord(
            stage=stage,
            output=result.text,
            handoff=slot.request,
            num_turns=result.num_turns,
            cost_usd=result.cost_usd,
            usage=result.usage,
            is_error=result.is_error,
        )
        update: PipelineState = {"history": [record], "handoff": slot.request}
        update[ARTIFACT_KEY[stage]] = result.text  # type: ignore[literal-required]
        if comment_slot is not None:
            update["review_comments"] = comment_slot.comments

        if slot.request is None:
            return update
        return Command(update=update, goto=_self_route(stage, state, slot, config))

    node.__name__ = f"{stage.value}_node"
    return node


def _self_route(stage: Stage, state: PipelineState, slot: HandoffSlot, config: PipelineConfig) -> str:
    """Turn the assistant's own handoff call into a graph destination."""
    if len(state.get("history", [])) + 1 >= config.max_stage_runs:
        logger.warning("stage-run cap reached after %s; stopping", stage.value)
        return END
    target = slot.request.target
    logger.info(
        "stage %s handed off to %s: %s",
        stage.value,
        target.value,
        slot.request.reason or "no reason given",
    )
    return END if target is Stage.DONE else target.value

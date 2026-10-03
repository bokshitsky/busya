"""Deciding which stage runs next."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from .assistant import AssistantSpec, run_assistant
from .config import PipelineConfig
from .route_tool import SERVER_NAME, RouteSlot, build_route_server
from .state import ALLOWED_TARGETS, ARTIFACT_KEY, PipelineState, Stage, visit_count

logger = logging.getLogger(__name__)

_APPROVED = "approved"
_CHANGES = "changes requested"


@runtime_checkable
class Orchestrator(Protocol):
    """Decides where control goes after a stage finishes."""

    async def next_stage(self, state: PipelineState, finished: Stage) -> Stage: ...


class RulesOrchestrator:
    """Walks the stages in order and loops coding/review on review feedback."""

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config

    async def next_stage(self, state: PipelineState, finished: Stage) -> Stage:
        if finished is Stage.REQUIREMENTS:
            return Stage.PLANNING
        if finished is Stage.PLANNING:
            return Stage.CODING
        if finished is Stage.CODING:
            return Stage.REVIEW

        verdict = read_verdict(state.get("review", ""))
        rounds = visit_count(state, Stage.REVIEW)
        if verdict == _APPROVED:
            return Stage.DONE
        if rounds >= self._config.max_review_rounds:
            logger.warning("review still wants changes after %d round(s); finishing anyway", rounds)
            return Stage.DONE
        return Stage.CODING


class LLMOrchestrator:
    """Asks a separate assistant to pick the next stage via a tool call."""

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        self._fallback = RulesOrchestrator(config)

    async def next_stage(self, state: PipelineState, finished: Stage) -> Stage:
        targets = ALLOWED_TARGETS[finished]
        if len(targets) == 1:
            return targets[0]

        choices = ", ".join(t.value for t in targets)
        slot = RouteSlot()
        server, tool_name = build_route_server(targets, slot)
        await run_assistant(
            AssistantSpec(
                system_prompt=(
                    "You route a four-stage software pipeline: requirements -> "
                    "planning -> coding -> review. You are given the stage that just "
                    "finished and its output. Decide whether its output is good "
                    "enough to move on, or whether an earlier stage must run again. "
                    "Record your choice by calling the `select_next_stage` tool."
                ),
                prompt=(
                    f"# Stage that finished\n{finished.value}\n\n"
                    f"# Its output\n{state.get(ARTIFACT_KEY[finished], '')}\n\n"
                    f"# Valid next stages\n{choices}\n\n"
                    "Call `select_next_stage` with exactly one of the valid next stages."
                ),
                tools=[tool_name],
                mcp_servers={SERVER_NAME: server},
                model=self._config.orchestrator_model or self._config.model,
                max_turns=2,
                label="orchestrator",
            )
        )

        if slot.target is None:
            logger.warning("orchestrator did not call select_next_stage; falling back to rules")
            return await self._fallback.next_stage(state, finished)
        logger.info("orchestrator chose %s after %s", slot.target.value, finished.value)
        return slot.target


def build_orchestrator(config: PipelineConfig) -> Orchestrator:
    return LLMOrchestrator(config) if config.llm_orchestrator else RulesOrchestrator(config)


def read_verdict(review: str) -> str:
    """Pull APPROVED / CHANGES REQUESTED out of a review report."""
    text = review.lower()
    changes_at = text.find(_CHANGES)
    approved_at = text.find(_APPROVED)
    if changes_at == -1 and approved_at == -1:
        return ""
    if changes_at == -1:
        return _APPROVED
    if approved_at == -1:
        return _CHANGES
    # Both appear (e.g. "APPROVED" in a findings list) — the earlier one is the verdict.
    return _APPROVED if approved_at < changes_at else _CHANGES

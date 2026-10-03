"""Wiring the four stages into a LangGraph pipeline."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Hashable

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .config import PipelineConfig, RoutingMode
from .nodes import build_stage_node
from .orchestrator import Orchestrator, build_orchestrator
from .state import ALLOWED_TARGETS, WORK_STAGES, PipelineState, Stage

logger = logging.getLogger(__name__)

Router = Callable[[PipelineState], Awaitable[str]]
Pipeline = CompiledStateGraph[PipelineState, None, PipelineState, PipelineState]


def build_graph(config: PipelineConfig | None = None) -> Pipeline:
    """Compile the pipeline.

    The two routing modes produce structurally different graphs:

    - `orchestrator`: every stage has a conditional edge, and the orchestrator
      decides which way it goes once the stage is finished.
    - `assistant`: stages have no outgoing edges — each one returns a `Command`
      carrying the target its own assistant chose via the handoff tool.
    """
    config = config or PipelineConfig()
    builder = StateGraph[PipelineState, None, PipelineState, PipelineState](
        PipelineState
    )

    self_routing = config.routing is RoutingMode.ASSISTANT
    for stage in WORK_STAGES:
        builder.add_node(
            stage.value,
            build_stage_node(stage, config),
            # Only meaningful for self-routing nodes, which carry no edges —
            # it tells LangGraph where their Commands can send control.
            destinations=_destinations(stage) if self_routing else None,
        )

    builder.add_edge(START, Stage.REQUIREMENTS.value)

    if not self_routing:
        orchestrator = build_orchestrator(config)
        for stage in WORK_STAGES:
            edges: dict[Hashable, str] = {
                key: value for key, value in _destinations(stage).items()
            }
            builder.add_conditional_edges(
                stage.value, _build_router(stage, config, orchestrator), edges
            )

    return builder.compile()


def _build_router(
    stage: Stage, config: PipelineConfig, orchestrator: Orchestrator
) -> Router:
    """Ask the orchestrator where to go after `stage`."""

    async def router(state: PipelineState) -> str:
        if len(state.get("history", [])) >= config.max_stage_runs:
            logger.warning("stage-run cap reached after %s; stopping", stage.value)
            return END
        target = await orchestrator.next_stage(state, stage)
        logger.info("orchestrator: %s -> %s", stage.value, target.value)
        return END if target is Stage.DONE else target.value

    router.__name__ = f"route_after_{stage.value}"
    return router


def _destinations(stage: Stage) -> dict[str, str]:
    """Where `stage` is allowed to send control, as a LangGraph edge mapping."""
    mapping = {
        target.value: target.value
        for target in ALLOWED_TARGETS[stage]
        if target is not Stage.DONE
    }
    mapping[END] = END
    return mapping

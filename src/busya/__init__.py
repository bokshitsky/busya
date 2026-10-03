"""busya — a four-stage coding agent: requirements, planning, coding, review.

Each stage runs its own Claude Agent SDK assistant and sees the other stages'
artifacts. LangGraph moves control between them, either by orchestrator decision
or by the stage assistant calling the `handoff` tool itself.
"""

from .assistant import AssistantResult, AssistantSpec, run_assistant
from .cli import main
from .config import PipelineConfig, RoutingMode
from .graph import build_graph
from .handoff import HandoffSlot, build_handoff_server
from .orchestrator import (
    LLMOrchestrator,
    Orchestrator,
    RulesOrchestrator,
    build_orchestrator,
)
from .runner import run_pipeline, summarize
from .state import HandoffRequest, PipelineState, Stage, StageRecord

__all__ = [
    "AssistantResult",
    "AssistantSpec",
    "HandoffRequest",
    "HandoffSlot",
    "LLMOrchestrator",
    "Orchestrator",
    "PipelineConfig",
    "PipelineState",
    "RoutingMode",
    "RulesOrchestrator",
    "Stage",
    "StageRecord",
    "build_graph",
    "build_handoff_server",
    "build_orchestrator",
    "main",
    "run_assistant",
    "run_pipeline",
    "summarize",
]

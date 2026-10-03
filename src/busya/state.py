"""State that travels between pipeline stages."""

from __future__ import annotations

import operator
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, TypedDict


class Stage(StrEnum):
    """A pipeline step. Values double as LangGraph node names."""

    REQUIREMENTS = "requirements"
    PLANNING = "planning"
    CODING = "coding"
    REVIEW = "review"
    DONE = "done"


WORK_STAGES: tuple[Stage, ...] = (
    Stage.REQUIREMENTS,
    Stage.PLANNING,
    Stage.CODING,
    Stage.REVIEW,
)

#: Where each stage is allowed to send control next.
ALLOWED_TARGETS: dict[Stage, tuple[Stage, ...]] = {
    Stage.REQUIREMENTS: (Stage.PLANNING,),
    Stage.PLANNING: (Stage.REQUIREMENTS, Stage.CODING),
    Stage.CODING: (Stage.PLANNING, Stage.REVIEW),
    Stage.REVIEW: (Stage.CODING, Stage.DONE),
}

#: Which state key holds each stage's artifact.
ARTIFACT_KEY: dict[Stage, str] = {
    Stage.REQUIREMENTS: "requirements",
    Stage.PLANNING: "plan",
    Stage.CODING: "code_report",
    Stage.REVIEW: "review",
}


@dataclass(frozen=True, slots=True)
class HandoffRequest:
    """A stage assistant's own decision about where control should go."""

    source: Stage
    target: Stage
    reason: str


@dataclass(frozen=True, slots=True)
class StageRecord:
    """What one stage run produced."""

    stage: Stage
    output: str
    handoff: HandoffRequest | None = None
    num_turns: int = 0
    cost_usd: float | None = None
    is_error: bool = False


class PipelineState(TypedDict, total=False):
    """Graph state. Every stage reads the artifacts of the others from here."""

    task: str
    requirements: str
    plan: str
    code_report: str
    review: str
    #: Set by the handoff tool when a stage routes itself; cleared on read.
    handoff: HandoffRequest | None
    history: Annotated[list[StageRecord], operator.add]


def visit_count(state: PipelineState, stage: Stage) -> int:
    """How many times `stage` has already run."""
    return sum(1 for record in state.get("history", []) if record.stage is stage)


def context_block(state: PipelineState, *, exclude: Stage) -> str:
    """Render the other stages' artifacts as prompt context."""
    parts = [f"# Task\n{state.get('task', '').strip()}"]
    titles = {
        Stage.REQUIREMENTS: "Requirements (from the requirements stage)",
        Stage.PLANNING: "Plan (from the planning stage)",
        Stage.CODING: "Implementation report (from the coding stage)",
        Stage.REVIEW: "Review feedback (from the review stage)",
    }
    for stage in WORK_STAGES:
        if stage is exclude:
            continue
        artifact = state.get(ARTIFACT_KEY[stage], "")
        if artifact:
            parts.append(f"# {titles[stage]}\n{str(artifact).strip()}")
    return "\n\n".join(parts)

"""Pipeline configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from claude_agent_sdk import PermissionMode

from .state import Stage


class RoutingMode(StrEnum):
    """How control moves between nodes."""

    #: The graph asks the orchestrator after each stage finishes.
    ORCHESTRATOR = "orchestrator"
    #: Each stage's assistant calls the handoff tool itself.
    ASSISTANT = "assistant"


_READ_ONLY = ["Read", "Glob", "Grep"]

#: Tools available to each stage, before the handoff tool is added.
STAGE_TOOLS: dict[Stage, list[str]] = {
    Stage.REQUIREMENTS: list(_READ_ONLY),
    Stage.PLANNING: list(_READ_ONLY),
    Stage.CODING: [*_READ_ONLY, "Write", "Edit", "Bash", "TodoWrite"],
    Stage.REVIEW: [*_READ_ONLY, "Bash"],
}


@dataclass(slots=True)
class PipelineConfig:
    """Knobs for one pipeline run."""

    routing: RoutingMode = RoutingMode.ORCHESTRATOR
    #: Model for stage assistants; None uses the CLI default.
    model: str | None = None
    #: Model for the LLM orchestrator, when one is used.
    orchestrator_model: str | None = None
    #: Let an assistant decide the next stage instead of applying rules.
    llm_orchestrator: bool = False
    #: Working directory the assistants operate in.
    cwd: Path | None = None
    max_turns: dict[Stage, int] = field(
        default_factory=lambda: {
            Stage.REQUIREMENTS: 25,
            Stage.PLANNING: 25,
            Stage.CODING: 60,
            Stage.REVIEW: 30,
        }
    )
    permission_mode: PermissionMode = "acceptEdits"
    #: Cap on coding/review loops before the run is forced to finish.
    max_review_rounds: int = 2
    #: Hard cap on total stage runs, so a bad handoff cannot loop forever.
    max_stage_runs: int = 12

    def tools_for(self, stage: Stage) -> list[str]:
        return list(STAGE_TOOLS[stage])

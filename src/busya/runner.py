"""Running the pipeline end to end."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from .config import PipelineConfig
from .graph import build_graph
from .state import PipelineState


async def run_pipeline(
    task: str, config: PipelineConfig | None = None
) -> PipelineState:
    """Run all four stages on `task` and return the final state."""
    config = config or PipelineConfig()
    if config.cwd is None:
        config.cwd = Path.cwd()
    graph = build_graph(config)
    initial: PipelineState = {"task": task, "history": []}
    # recursion_limit bounds graph steps; stage runs are capped separately.
    final = await graph.ainvoke(
        initial, config={"recursion_limit": config.max_stage_runs * 2 + 4}
    )
    return cast(PipelineState, final)


def summarize(state: PipelineState) -> str:
    """One line per stage run, plus the total cost."""
    lines = []
    total = 0.0
    for index, record in enumerate(state.get("history", []), start=1):
        cost = f"${record.cost_usd:.4f}" if record.cost_usd is not None else "n/a"
        total += record.cost_usd or 0.0
        handoff = f" -> {record.handoff.target.value}" if record.handoff else ""
        flag = " [error]" if record.is_error else ""
        lines.append(
            f"{index}. {record.stage.value}{handoff}: "
            f"{record.num_turns} turns, {cost}{flag}"
        )
    lines.append(f"total: ${total:.4f}")
    return "\n".join(lines)

"""Running the pipeline end to end."""

from __future__ import annotations

from typing import Any, cast

from .config import PipelineConfig
from .graph import build_graph
from .state import PipelineState


async def run_pipeline(task: str, config: PipelineConfig) -> PipelineState:
    """Run all four stages on `task` and return the final state."""
    graph = build_graph(config)
    initial: PipelineState = {"task": task, "history": []}
    # recursion_limit bounds graph steps; stage runs are capped separately.
    final = await graph.ainvoke(initial, config={"recursion_limit": config.max_stage_runs * 2 + 4})
    return cast(PipelineState, final)


#: Usage dict keys that count as consumed tokens.
_TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def _tokens(usage: dict[str, Any] | None) -> int:
    """Total tokens (input + output + cache) a usage dict accounts for."""
    if not usage:
        return 0
    return sum(int(usage.get(key) or 0) for key in _TOKEN_KEYS)


def summarize(state: PipelineState) -> str:
    """One line per stage run, plus the total cost and tokens."""
    lines = []
    total_cost = 0.0
    total_tokens = 0
    for index, record in enumerate(state.get("history", []), start=1):
        cost = f"${record.cost_usd:.4f}" if record.cost_usd is not None else "n/a"
        tokens = _tokens(record.usage)
        total_cost += record.cost_usd or 0.0
        total_tokens += tokens
        handoff = f" -> {record.handoff.target.value}" if record.handoff else ""
        flag = " [error]" if record.is_error else ""
        lines.append(f"{index}. {record.stage.value}{handoff}: {record.num_turns} turns, {cost}, {tokens} tokens{flag}")
    lines.append(f"total: ${total_cost:.4f}, {total_tokens} tokens")
    return "\n".join(lines)

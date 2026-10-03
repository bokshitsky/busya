"""Command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import PipelineConfig
from .runner import run_pipeline, summarize
from .state import ARTIFACT_KEY, WORK_STAGES


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="busya", description="Four-stage coding agent on LangGraph."
    )
    parser.add_argument("task", nargs="?", help="what to build; omit to read stdin")
    parser.add_argument(
        "--routing",
        choices=["orchestrator", "assistant"],
        default="orchestrator",
        help="who picks the next stage (default: orchestrator)",
    )
    parser.add_argument(
        "--llm-orchestrator",
        action="store_true",
        help="let an assistant make the orchestrator's decisions",
    )
    parser.add_argument("--model", help="model for the stage assistants")
    parser.add_argument("--orchestrator-model", help="model for the LLM orchestrator")
    parser.add_argument(
        "--cwd", type=Path, help="directory the assistants work in (default: .)"
    )
    parser.add_argument(
        "--max-review-rounds",
        type=int,
        default=2,
        help="coding/review loops before finishing anyway (default: 2)",
    )
    parser.add_argument(
        "--max-stage-runs",
        type=int,
        default=12,
        help="hard cap on total stage runs (default: 12)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="print every stage artifact, not just the summary",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    task = args.task or sys.stdin.read()
    if not task.strip():
        print("busya: no task given", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config = PipelineConfig(
        routing=args.routing,
        llm_orchestrator=args.llm_orchestrator,
        model=args.model,
        orchestrator_model=args.orchestrator_model,
        cwd=args.cwd,
        max_review_rounds=args.max_review_rounds,
        max_stage_runs=args.max_stage_runs,
    )

    state = asyncio.run(run_pipeline(task, config))

    if args.show:
        for stage in WORK_STAGES:
            artifact = state.get(ARTIFACT_KEY[stage], "")
            if artifact:
                print(f"\n{'=' * 70}\n{stage.value.upper()}\n{'=' * 70}\n{artifact}")
        print()

    print(summarize(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

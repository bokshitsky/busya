"""Command line entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer

from .config import PipelineConfig, RoutingMode
from .runner import run_pipeline, summarize
from .state import ARTIFACT_KEY, WORK_STAGES

app = typer.Typer(
    add_completion=False,
    help="Four-stage coding agent on LangGraph: requirements, planning, coding, review.",
)


@app.command()
def run(
    task: Annotated[str | None, typer.Argument(help="What to build. Omit to read it from stdin.")] = None,
    routing: Annotated[RoutingMode, typer.Option(help="Who picks the next stage.")] = RoutingMode.ORCHESTRATOR,
    llm_orchestrator: Annotated[bool, typer.Option(help="Let an assistant make the orchestrator's decisions.")] = False,
    model: Annotated[str | None, typer.Option(help="Model for the stage assistants.")] = None,
    orchestrator_model: Annotated[str | None, typer.Option(help="Model for the LLM orchestrator.")] = None,
    cwd: Annotated[
        Path | None,
        typer.Option(
            help="Directory the assistants work in.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
    max_review_rounds: Annotated[
        int,
        typer.Option(min=1, help="Coding/review loops before finishing anyway."),
    ] = 2,
    max_stage_runs: Annotated[int, typer.Option(min=1, help="Hard cap on total stage runs.")] = 12,
    show: Annotated[bool, typer.Option(help="Print every stage artifact, not just the summary.")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging.")] = False,
) -> None:
    """Run the pipeline on a task."""
    text = task if task is not None else sys.stdin.read()
    if not text.strip():
        typer.echo("busya: no task given", err=True)
        raise typer.Exit(code=2)

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config = PipelineConfig(
        routing=routing,
        llm_orchestrator=llm_orchestrator,
        model=model,
        orchestrator_model=orchestrator_model,
        cwd=cwd,
        max_review_rounds=max_review_rounds,
        max_stage_runs=max_stage_runs,
    )

    state = asyncio.run(run_pipeline(text, config))

    if show:
        for stage in WORK_STAGES:
            artifact = state.get(ARTIFACT_KEY[stage], "")
            if artifact:
                typer.echo(f"\n{'=' * 70}\n{stage.value.upper()}\n{'=' * 70}\n{artifact}")
        typer.echo()

    typer.echo(summarize(state))


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()

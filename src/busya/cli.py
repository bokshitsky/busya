"""Command line entry point."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer

from .config import PipelineConfig
from .review_only import run_review_only
from .runner import run_pipeline, summarize
from .state import ARTIFACT_KEY, WORK_STAGES

app = typer.Typer(
    add_completion=False,
    help="Four-stage coding agent on LangGraph: requirements, planning, coding, review.",
)


@app.command("run")
def run(
    task: Annotated[str | None, typer.Argument(help="What to build. Omit to read it from stdin.")] = None,
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
    review_instruction: Annotated[
        list[Path] | None,
        typer.Option(
            "--review-instruction",
            help="File or folder telling the review stage what to focus on. Repeatable.",
            exists=True,
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
        llm_orchestrator=llm_orchestrator,
        model=model,
        orchestrator_model=orchestrator_model,
        cwd=cwd if cwd is not None else Path.cwd(),
        review_instructions=review_instruction or [],
        max_review_rounds=max_review_rounds,
        max_stage_runs=max_stage_runs,
    )

    state = asyncio.run(run_pipeline(text, config))

    if show:
        for stage in WORK_STAGES:
            artifact = state.get(ARTIFACT_KEY[stage], "")
            if artifact:
                typer.echo(f"\n{'=' * 70}\n{stage.value.upper()}\n{'=' * 70}\n{artifact}")
        for comment in state.get("review_comments", []):
            typer.echo(f"{comment.file}:{comment.line}: {comment.comment}")
        typer.echo()

    typer.echo(summarize(state))


@app.command("review")
def review(
    compare_base: Annotated[str, typer.Option(help="Git ref to compare from.")] = "master",
    compare_update: Annotated[str, typer.Option(help="Git ref to compare to.")] = "HEAD",
    review_instruction: Annotated[
        list[Path] | None,
        typer.Option(
            "--review-instruction",
            help="File or folder telling the reviewer what to focus on. Repeatable.",
            exists=True,
        ),
    ] = None,
    cwd: Annotated[
        Path | None,
        typer.Option(help="Repository to review.", exists=True, file_okay=False, dir_okay=True),
    ] = None,
    model: Annotated[str | None, typer.Option(help="Model for the reviewer.")] = None,
    max_turns: Annotated[int, typer.Option(min=1, help="Cap on reviewer turns.")] = 30,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging.")] = False,
) -> None:
    """Review the diff between two git refs; print findings as JSON. No pipeline, just review."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    result = asyncio.run(
        run_review_only(
            cwd=cwd if cwd is not None else Path.cwd(),
            compare_base=compare_base,
            compare_update=compare_update,
            review_instructions=review_instruction or [],
            model=model,
            max_turns=max_turns,
        )
    )

    payload = {
        "summary": result.summary,
        "comments": [{"file": c.file, "line": c.line, "comment": c.comment} for c in result.comments],
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()

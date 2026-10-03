"""Standalone review of a diff between two git refs — no pipeline, no handoff."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .assistant import AssistantSpec, run_assistant
from .config import STAGE_TOOLS
from .prompts import REVIEW_ONLY_SYSTEM_PROMPT, review_instructions_block, review_only_prompt
from .review_tool import SERVER_NAME, ReviewCommentSlot, build_review_comment_server
from .state import ReviewComment, Stage

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ReviewOnlyResult:
    """What a standalone review run produced."""

    summary: str
    comments: list[ReviewComment]


async def run_review_only(
    *,
    cwd: Path,
    compare_base: str,
    compare_update: str,
    review_instructions: str,
    model: str | None,
    max_turns: int,
) -> ReviewOnlyResult:
    """Diff `compare_base` against `compare_update` in `cwd` and review it.

    `review_instructions` is raw text (e.g. from `review_instructions.load_review_instructions`)
    — this function doesn't care where it came from.
    """
    diff = _git_diff(cwd, compare_base, compare_update)
    prompt = review_only_prompt(compare_base, compare_update, diff, review_instructions_block(review_instructions))

    tools = [*STAGE_TOOLS[Stage.REVIEW]]
    slot = ReviewCommentSlot()
    server, tool_name = build_review_comment_server(slot)
    tools.append(tool_name)

    result = await run_assistant(
        AssistantSpec(
            system_prompt=REVIEW_ONLY_SYSTEM_PROMPT,
            prompt=prompt,
            tools=tools,
            mcp_servers={SERVER_NAME: server},
            model=model,
            max_turns=max_turns,
            label="review",
            cwd=cwd,
        )
    )
    return ReviewOnlyResult(summary=result.text, comments=slot.comments)


def _git_diff(cwd: Path, base: str, update: str) -> str:
    proc = subprocess.run(
        ["git", "diff", f"{base}...{update}"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git diff {base}...{update} failed: {proc.stderr.strip()}")
    return proc.stdout

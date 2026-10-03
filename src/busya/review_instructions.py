"""Loading reviewer instructions from files or whole folders."""

from __future__ import annotations

from pathlib import Path


def load_review_instructions(paths: list[Path]) -> str:
    """Read every path, expanding directories into their files, and join their raw text.

    The result is unframed — callers decide how to present it to whichever
    stage receives it (see `prompts.review_instructions_block` and
    `prompts.reviewer_focus_block`).
    """
    sections = []
    for path in paths:
        for file in _files(path):
            try:
                text = file.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                continue
            if text:
                sections.append(f"## {file}\n{text}")
    return "\n\n".join(sections)


def _files(path: Path) -> list[Path]:
    """`path` itself if it's a file, or every non-hidden file under it if it's a directory."""
    if path.is_dir():
        return sorted(
            p
            for p in path.rglob("*")
            if p.is_file() and not any(part.startswith(".") for part in p.relative_to(path).parts)
        )
    return [path]

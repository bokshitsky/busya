# AGENTS.md

Guidance for AI agents working in this repo. Pairs with `README.md` (which is
in Russian and user-facing); this file is the contributor/agent view.

## What this is

`busya` is a four-stage coding agent — **requirements → planning → coding →
review** — built on [LangGraph](https://langchain-ai.github.io/langgraph/).
Each stage is a separate [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk)
assistant with its own system prompt and tool set. There are two CLI commands:
`run` (the full pipeline) and `review` (a standalone reviewer over a git diff,
no pipeline).

## Commands

```sh
uv sync                                              # install
uv run ruff format src && uv run ruff check src && uv run mypy   # the full check
uv run busya run "task"                              # run the pipeline
uv run busya review --compare-base master --compare-update HEAD  # review a diff
```

There is no test suite. Treat `ruff format`, `ruff check`, and `mypy` (strict)
all passing as the bar for "done". Run them after every change.

Running the agent for real costs money and hits the Claude API — do it only
when a change genuinely needs end-to-end confirmation, and prefer the
`review` command with a small diff for a cheap smoke test.

## Layout

| file | what's in it |
|---|---|
| `state.py` | `Stage` enum, `PipelineState`, `ALLOWED_TARGETS`, dataclasses (`HandoffRequest`, `ReviewComment`, `StageRecord`), context assembly |
| `config.py` | `PipelineConfig`, `STAGE_TOOLS` |
| `prompts.py` | per-stage system-prompt constants assembled into `SYSTEM_PROMPTS`, plus prompt builders |
| `assistant.py` | `run_assistant` — drives one `ClaudeSDKClient` run to completion |
| `handoff.py` | in-process MCP tool `handoff` (a stage routing itself) |
| `review_tool.py` | in-process MCP tool `add_comment` (structured review findings) |
| `route_tool.py` | in-process MCP tool `select_next_stage` (the LLM orchestrator's choice) |
| `review_instructions.py` | resolve `--review-instruction` files/folders into prompt text |
| `nodes.py` | the LangGraph stage nodes |
| `orchestrator.py` | `RulesOrchestrator`, `LLMOrchestrator`, verdict parsing |
| `graph.py` | wires nodes + edges into the compiled graph |
| `review_only.py` | the `review` command: git diff + one reviewer run, no graph |
| `runner.py` | runs the pipeline and summarizes cost/tokens |
| `cli.py` | the `typer` app (`run`, `review`) |

## How routing works

Each stage assistant gets a `handoff` tool and can route itself: if it calls
it, the node returns a `Command(goto=...)` that wins outright. If it doesn't,
a conditional edge asks an orchestrator. `RulesOrchestrator` walks the stages
in order and loops coding↔review on the verdict; `LLMOrchestrator`
(`--llm-orchestrator`) asks a tool-equipped assistant and falls back to the
rules if it doesn't answer. `ALLOWED_TARGETS` in `state.py` is the source of
truth for legal transitions.

## Conventions

- Target Python 3.14. `from __future__ import annotations` at the top of every
  module.
- `mypy` runs in **strict** mode; keep everything fully typed. `ruff` line
  length is 120; lint rules are in `pyproject.toml`.
- Dataclasses use `slots=True` (and `frozen=True` for value types). Document
  non-obvious fields with a `#:` comment.
- **In-process MCP tool pattern** — `handoff.py`, `review_tool.py`, and
  `route_tool.py` are the template to copy for a new tool: a `*Slot`
  dataclass the handler writes into, and a `build_*_server(...) -> (server,
  tool_name)` function. The caller reads the slot after `run_assistant`
  returns.
- Keep prompt text in `prompts.py` as named constants, assembled into dicts
  afterwards — don't inline prompt bodies into dict literals.
- Resolve external inputs (like review instructions) to plain strings at the
  CLI boundary in `cli.py`, so the graph and runners stay source-agnostic.
- Commit in small, focused steps with a short imperative subject and a body
  explaining the why; only commit when the user asks.
- Comments and identifiers are in English; user-facing `README.md` is Russian.

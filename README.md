# busya

Кодинг-агент из четырёх этапов: **требования → планирование → написание кода → ревью**.

Каждый этап — отдельный ассистент на [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk)
со своим системным промптом и своим набором инструментов. Переходы между этапами
держит [LangGraph](https://langchain-ai.github.io/langgraph/).

## Установка

```sh
uv sync
```

Нужен доступ к Claude (переменная `ANTHROPIC_API_KEY` или уже выполненный логин
в Claude Code — SDK использует вложенный CLI и подхватывает те же креды).

## Запуск

```sh
# оркестратор решает, когда передать управление дальше
uv run busya "Добавь ручку /health в сервис"

# ассистент сам передаёт управление через тул handoff
uv run busya --routing assistant "Добавь ручку /health в сервис"

# работать в другой директории и печатать все артефакты
uv run busya --cwd ../myproject --show "Перепиши парсер конфига"

# задачу можно подать на stdin
cat task.md | uv run busya
```

Полезные флаги: `--model`, `--llm-orchestrator`, `--max-review-rounds`,
`--max-stage-runs`, `-v`. Весь список — `uv run busya --help`.
CLI на [typer](https://typer.tiangolo.com/), булевы флаги имеют парные
`--no-*` формы.

## Два способа перехода между этапами

**1. Решает оркестратор** (`--routing orchestrator`, по умолчанию).

У каждой ноды есть условное ребро. Когда этап закончил работу, оркестратор
смотрит на состояние и выбирает следующую ноду. Доступны две реализации:

- `RulesOrchestrator` — идёт по порядку этапов, а после ревью читает вердикт:
  `APPROVED` → конец, `CHANGES REQUESTED` → снова код (до `--max-review-rounds` раз).
- `LLMOrchestrator` (`--llm-orchestrator`) — отдельный ассистент без инструментов
  получает вывод этапа и отвечает одним названием следующего этапа. Если ответ
  непонятен, падает обратно на правила.

**2. Решает сам ассистент** (`--routing assistant`).

Ноде добавляется in-process MCP-сервер с тулом `handoff(target, reason)`.
Ассистент вызывает его последним действием, обработчик пишет решение в слот,
нода возвращает `Command(goto=...)`. Тул проверяет, что цель разрешена для этого
этапа; если ассистент вообще не вызвал `handoff`, пайплайн останавливается.

Куда можно передавать управление (`state.ALLOWED_TARGETS`):

| этап | разрешённые цели |
|---|---|
| requirements | planning |
| planning | requirements, coding |
| coding | planning, review |
| review | coding, done |

## Что видит каждый ассистент

В промпт этапа складываются артефакты всех остальных этапов: исходная задача,
требования, план, отчёт о реализации, замечания ревью. То есть кодер видит
требования и план, а на второй итерации — ещё и замечания ревьюера.

Инструменты по этапам (`config.STAGE_TOOLS`):

| этап | инструменты |
|---|---|
| requirements | Read, Glob, Grep |
| planning | Read, Glob, Grep |
| coding | Read, Glob, Grep, Write, Edit, Bash, TodoWrite |
| review | Read, Glob, Grep, Bash |

## Структура

| файл | что внутри |
|---|---|
| `state.py` | `Stage`, состояние графа, разрешённые переходы, сборка контекста |
| `prompts.py` | системные промпты этапов |
| `assistant.py` | запуск одного ассистента через `ClaudeSDKClient` |
| `handoff.py` | in-process MCP-сервер с тулом `handoff` |
| `nodes.py` | ноды этапов |
| `orchestrator.py` | `RulesOrchestrator`, `LLMOrchestrator` |
| `graph.py` | сборка графа под выбранный режим переходов |
| `runner.py` | прогон пайплайна и сводка по стоимости |
| `cli.py` | typer-приложение |

## Ограничители

- `--max-review-rounds` — сколько раз крутить цикл код↔ревью, прежде чем закончить.
- `--max-stage-runs` — жёсткий потолок на число запусков этапов, чтобы плохой
  handoff не зациклил граф.
- `max_turns` на этап — в `PipelineConfig.max_turns`.
- `setting_sources=[]` — ассистенты не читают `~/.claude` и настройки проекта,
  прогон зависит только от конфига.

## Разработка

```sh
uv run ruff format src && uv run ruff check src && uv run mypy
```

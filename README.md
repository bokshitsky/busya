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

У CLI две команды: `run` — весь четырёхэтапный пайплайн, `review` —
только ревью, без требований/плана/кода (например, для CI).

```sh
uv run busya run "Добавь ручку /health в сервис"

# работать в другой директории и печатать все артефакты
uv run busya run --cwd ../myproject --show "Перепиши парсер конфига"

# задачу можно подать на stdin
cat task.md | uv run busya run
```

Полезные флаги `run`: `--model`, `--llm-orchestrator`, `--max-review-rounds`,
`--max-stage-runs`, `--review-instruction`, `-v`. Весь список —
`uv run busya run --help`. CLI на [typer](https://typer.tiangolo.com/),
булевы флаги имеют парные `--no-*` формы.

## На что обращать внимание при ревью

`--review-instruction` (можно повторять) добавляет в промпт ревью-этапа блок
`# Review instructions` с текстом из указанных файлов. Можно передать и папку
целиком — тогда берутся все файлы под ней рекурсивно (скрытые файлы и папки
пропускаются). Флаг работает и у `run`, и у `review`:

```sh
uv run busya run --review-instruction docs/security-checklist.md "..."
uv run busya review --review-instruction docs/review-focus/
```

## Структурированные комментарии ревью

Ревью-этапу (в обоих режимах) доступен тул `add_comment(file, line, comment)` —
он вызывает его один раз на каждую найденную проблему, вдобавок к текстовому
отчёту. В `run` эти комментарии попадают в `state.review_comments` и печатаются
построчно вместе с `--show`; в `review` — это и есть содержимое `comments` в
JSON-выводе.

## Ревью без пайплайна (`review`)

```sh
uv run busya review --compare-base master --compare-update HEAD --cwd ../myproject
```

Делает `git diff <compare-base>...<compare-update>` в указанном репозитории
(`--cwd`, по умолчанию текущая директория), прогоняет через него один
ассистент-ревьюер (с `Read`, `Glob`, `Grep`, `Bash` и тулом `add_comment`) и
печатает в stdout JSON:

```json
{
  "summary": "общий вывод ревьюера, в несколько предложений",
  "comments": [
    {"file": "src/foo.py", "line": 42, "comment": "что здесь не так и как исправить"}
  ]
}
```

`--compare-base` по умолчанию `master`, `--compare-update` — `HEAD`. Поддерживает
те же `--review-instruction`, `--model`, `-v`, плюс `--max-turns` (по умолчанию 30).

## Переход между этапами

У каждой ноды есть одновременно и тул для самостоятельного перехода, и
условное ребро на оркестратор — они не исключают друг друга:

**1. Решает сам ассистент.**

Ноде добавляется in-process MCP-сервер с тулом `handoff(target, reason)`.
Если ассистент вызывает его последним действием, обработчик пишет решение в
слот, нода возвращает `Command(goto=...)` — это решение приоритетно и обходит
условное ребро.

**2. Иначе решает оркестратор.**

Если ассистент не вызвал `handoff`, нода просто записывает свой вывод, и
условное ребро спрашивает оркестратора, куда идти дальше. Доступны две
реализации:

- `RulesOrchestrator` — идёт по порядку этапов, а после ревью читает вердикт:
  `APPROVED` → конец, `CHANGES REQUESTED` → снова код (до `--max-review-rounds` раз).
- `LLMOrchestrator` (`--llm-orchestrator`) — отдельный ассистент без инструментов
  получает вывод этапа и отвечает одним названием следующего этапа. Если ответ
  непонятен, падает обратно на правила.

Тул `handoff` проверяет, что выбранная ассистентом цель разрешена для этого этапа.

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
| review | Read, Glob, Grep, Bash, add_comment |

## Структура

| файл | что внутри |
|---|---|
| `state.py` | `Stage`, состояние графа, разрешённые переходы, сборка контекста |
| `prompts.py` | системные промпты этапов |
| `assistant.py` | запуск одного ассистента через `ClaudeSDKClient` |
| `handoff.py` | in-process MCP-сервер с тулом `handoff` |
| `review_tool.py` | in-process MCP-сервер с тулом `add_comment` |
| `review_instructions.py` | чтение `--review-instruction` (файлы и папки) в текст промпта |
| `review_only.py` | режим `review`: git diff + один прогон ревьюера, без графа |
| `nodes.py` | ноды этапов |
| `orchestrator.py` | `RulesOrchestrator`, `LLMOrchestrator` |
| `graph.py` | сборка графа: handoff-тул и оркестратор на каждой ноде |
| `runner.py` | прогон пайплайна и сводка по стоимости |
| `cli.py` | typer-приложение: команды `run` и `review` |

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

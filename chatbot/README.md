# Menu-driven chatbot (LangGraph + Qwen via Ollama)

A terminal chatbot built with [LangGraph](https://langchain-ai.github.io/langgraph/) that
runs a small [Qwen](https://ollama.com/library/qwen2.5) model locally through
[Ollama](https://ollama.com). Every bot turn includes a short numbered menu of
suggested replies; you can type the number to pick one, or just type free text.

## Setup

1. Install [Ollama](https://ollama.com/download) and pull a small Qwen model:

   ```bash
   ollama pull qwen2.5:1.5b
   ```

2. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Run

```bash
python cli.py
```

Options:

```bash
python cli.py --model qwen2.5:3b --base-url http://localhost:11434
```

Type `exit` or `quit` to end the conversation.

## How it works

- `graph.py` defines a three-node LangGraph graph:
  - `assistant` either serves a **predefined** menu (see `PREDEFINED_MENUS`, keyed by
    `stage`) with zero LLM calls, or falls through to the Qwen model (via `ChatOllama` with
    `format="json"`) with a system prompt asking it to return
    `{"reply": ..., "options": [...], "allow_free_text": ...}`. Model output is validated
    against the `AssistantTurn` Pydantic schema (deduping/trimming options, falling back to
    raw text if parsing fails).
  - `human` pauses the graph with `interrupt()`, handing control back to the CLI. When
    resumed, numeric input is mapped back to the matching option; each option (`ChatOption`)
    carries an `id`, `label`, `value` (defaults to `label`), `source` (`"model"` or
    `"predefined"`), and an optional `action` — if set, selecting that option routes the
    graph straight to the named node (e.g. `"handoff"`) instead of replaying the choice as a
    normal chat message.
  - `handoff` is a demo of an action-routed node: picking "Talk to a human" in the welcome
    menu jumps here directly, without ever calling the LLM.
- `cli.py` drives the graph turn by turn using an `InMemorySaver` checkpointer, starting in
  the `"welcome"` stage, printing the bot's reply and menu, then reading terminal input and
  resuming the graph with `Command(resume=...)`.
- Graph state (`ChatState.options`) stores plain dicts (`ChatOption.model_dump()`), not
  `ChatOption` instances, so it stays fully JSON-serializable for any LangGraph checkpointer
  (in-memory, SQLite, Postgres) without needing a custom type registered for msgpack.

Swap in a different model by changing `--model`, or point `--base-url` at a remote Ollama
instance instead of running one locally.

## Tests

Tests use a `FakeLLM` stand-in (see `tests/test_graph.py`), so they don't require a running
Ollama server or model:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Covers: the predefined welcome menu (no LLM call), `action`-based routing to `handoff`,
falling through to the LLM for non-action options, option deduping/capping, the malformed-JSON
fallback path, numeric-to-value resolution, free-text passthrough, and `exit`.

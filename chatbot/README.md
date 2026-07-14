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

- `graph.py` defines a two-node LangGraph graph:
  - `assistant` calls the Qwen model (via `ChatOllama` with `format="json"`) with a system
    prompt asking it to return `{"reply": ..., "options": [...]}` — a conversational reply
    plus 2-4 short suggested next messages.
  - `human` pauses the graph with `interrupt()`, handing control back to the CLI. When the
    CLI resumes the graph with the user's input, numeric input is mapped back to the
    matching option text; anything else is passed through as free text.
- `cli.py` drives the graph turn by turn using an `InMemorySaver` checkpointer, printing the
  bot's reply and menu, then reading terminal input and resuming the graph with
  `Command(resume=...)`.

Swap in a different model by changing `--model`, or point `--base-url` at a remote Ollama
instance instead of running one locally.

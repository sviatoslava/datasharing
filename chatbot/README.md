# Menu-driven chatbot (LangGraph + Qwen via Ollama)

A chatbot (CLI and web UI) built with [LangGraph](https://langchain-ai.github.io/langgraph/)
that runs a small [Qwen](https://ollama.com/library/qwen2.5) model locally through
[Ollama](https://ollama.com). Every bot turn includes a short menu of suggested replies you
can click/type the number for, or you can just type free text.

Includes a **product Q&A mode** ("Ask about products & services") that answers questions
about retail banking products (cards, deposits, loans, mortgages, mobile banking) using a
small local knowledge base, retrieval-augmented into the model's prompt.

> **⚠️ Important — read before using the product Q&A mode.** This started as a request to
> build a Halyk Bank product chatbot sourced from halykbank.kz. The environment this was
> built in could not reach that site (blocked by network policy) or any other live source,
> so **`knowledge/*.md` is placeholder content I wrote by hand**, modeled on typical retail
> banking products in general — it is **not real data scraped or sourced from Halyk Bank**,
> and the bot is **not affiliated with or endorsed by Halyk Bank**. Every knowledge file and
> the bot's own system prompt say so explicitly, and the bot is instructed to never claim its
> answers are Halyk Bank's actual current rates, fees, or terms. Before using this for
> anything beyond a demo: replace `knowledge/*.md` with real, sourced content (see
> "Using real content" below), and keep the disclaimers — displaying fabricated financial
> product details as if they were a real bank's could mislead users into bad financial
> decisions.

## Setup

1. Install [Ollama](https://ollama.com/download) and pull a small Qwen model:

   ```bash
   ollama pull qwen2.5:1.5b
   ```

2. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Run — CLI

```bash
python cli.py
```

Options:

```bash
python cli.py --model qwen2.5:3b --base-url http://localhost:11434
```

Type `exit` or `quit` to end the conversation.

## Run — web UI

A small FastAPI + vanilla-JS chat page with clickable option buttons, backed by the same
graph as the CLI:

```bash
python webapp.py --model qwen2.5:1.5b
```

Then open http://127.0.0.1:8000/ in a browser. Options: `--base-url`, `--host`, `--port`.

Try it without a running Ollama server using a canned local stand-in (cycles through a few
scripted reply/menu pairs instead of calling a real model — useful for trying the UI/UX or
for environments where Ollama isn't reachable):

```bash
python webapp.py --demo
```

`GET /` serves the page; `POST /api/start` begins a session (returns a `thread_id`);
`POST /api/message {thread_id, text}` resumes the conversation — `text` can be an option's
`id` (from a button click) or free-typed text.

## How it works

- `graph.py` defines a four-node LangGraph graph:
  - `assistant` either serves a **predefined** menu (see `PREDEFINED_MENUS`, keyed by
    `stage`) with zero LLM calls, or falls through to the Qwen model (via `ChatOllama` with
    `format="json"`) with a system prompt asking it to return
    `{"reply": ..., "options": [...], "allow_free_text": ...}`. Model output is validated
    against the `AssistantTurn` Pydantic schema (deduping/trimming options, falling back to
    raw text if parsing fails).
  - `product_assistant` is the same pattern, but first retrieves the top matching chunks
    from the local `knowledge/` files (via `knowledge.retrieve`, a dependency-free TF-IDF
    scorer with stopword filtering, light plural stemming, and a title-match boost — no
    embedding model or vector DB needed for a handful of short documents) and injects them
    into a system prompt (`PRODUCT_SYSTEM_PROMPT`) that instructs the model to answer *only*
    from that reference material and to repeat the demo/placeholder disclaimer. If nothing
    scores above a confidence floor, `retrieve()` returns `[]` and the prompt says so
    explicitly, rather than grounding the model in an arbitrary/unrelated chunk.
    After the model replies, its **options are overridden by curated ones** from
    `knowledge/options.json` when the matched topic (or `"fallback"`, for no match) has an
    entry there — more reliable than trusting a small model to invent a good menu every
    turn. Topics without a curated entry keep the model's own options, so adding a new
    `knowledge/*.md` file works immediately even before its `options.json` entry is filled
    in.
  - `human` pauses the graph with `interrupt()`, handing control back to the caller. When
    resumed, numeric input or an option's `id` is mapped back to the matching option; each
    option (`ChatOption`) carries an `id`, `label`, `value` (defaults to `label`), `source`
    (`"model"` or `"predefined"`), and an optional `action` — if set, selecting that option
    routes the graph straight to the named node (`"product_assistant"`, `"handoff"`, ...)
    instead of replaying the choice as a normal chat message. If unset, follow-up turns stay
    in whichever LLM-backed node is currently active (`ChatState.active_node`), so a product
    Q&A conversation doesn't bounce back to the generic assistant between turns.
  - `handoff` is a demo of an action-routed node: picking "Talk to a human" in the welcome
    menu jumps here directly, without ever calling the LLM.
- `knowledge.py` + `knowledge/*.md`: the product knowledge base and its retrieval function
  (see the disclaimer above — this is placeholder content, not sourced from Halyk Bank).
- `cli.py` / `webapp.py` drive the graph turn by turn using an `InMemorySaver` checkpointer,
  starting in the `"welcome"` stage.
- Graph state (`ChatState.options`) stores plain dicts (`ChatOption.model_dump()`), not
  `ChatOption` instances, so it stays fully JSON-serializable for any LangGraph checkpointer
  (in-memory, SQLite, Postgres) without needing a custom type registered for msgpack.

Swap in a different model by changing `--model`, or point `--base-url` at a remote Ollama
instance instead of running one locally.

## Using real content

To replace the placeholder knowledge base with real, sourced product information:

1. Get the real content yourself (copy/export from the official site, an internal doc, a
   PDF brochure, etc. — with rights/permission to use it) and drop it into `knowledge/` as
   one `.md` file per topic, following the existing files' structure.
2. Remove the `> DEMO/PLACEHOLDER CONTENT...` disclaimer lines once the content is real, but
   keep *some* disclaimer if the bot still isn't an official, bank-authorized channel — it
   shouldn't be presented as one without the bank's involvement.
3. `knowledge.retrieve()` and `product_assistant` need no code changes — they just index
   whatever `.md` files are in `knowledge/`.
4. Optionally add a matching entry to `knowledge/options.json` (key = the new file's stem,
   e.g. `savings_bonds.md` → `"savings_bonds"`) to give that topic curated follow-up options
   instead of leaving them to the model. Each entry is `{"label": "...", "value": "...",
   "action": "..."}` — only `label` is required; `value` defaults to `label`, `action` is
   only needed to route to another node (e.g. `"handoff"`) instead of continuing the topic.
   No entry needed — the model's own generated options are used as a fallback.

## Common conversation scenarios

See **[`SCENARIOS.md`](./SCENARIOS.md)** for example transcripts of the most common ways
someone would actually use this bot (product inquiries per category, straight-to-the-point
free text, out-of-scope questions, human handoff, exit) — each backed by an executable test,
plus two documented known limitations that aren't fixed yet.

## Tests

Tests use a `FakeLLM` stand-in (see `tests/test_graph.py`), so they don't require a running
Ollama server or model:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

- `test_graph.py` — individual mechanisms in isolation: the predefined welcome menu (no LLM
  call), `action`-based routing to `handoff` and to `product_assistant`, falling through to
  the LLM for non-action options, option deduping/capping, the malformed-JSON fallback path,
  numeric-to-value and id-to-value resolution, free-text passthrough, `exit`, and that a
  product question retrieves and injects the matching knowledge chunk into the prompt.
- `test_knowledge.py` — retrieval quality: ranks the right topic per query, disambiguates
  similar topics, returns `[]` (not a stray chunk) when nothing confidently matches.
- `test_scenarios.py` — full multi-turn scenarios matching `SCENARIOS.md`, run end-to-end
  against the real graph.

Both `cli.py` and `webapp.py` need a real Ollama server + pulled model to talk to an actual
Qwen model (`webapp.py --demo` and the pytest suite don't — they use stand-ins). Note
`webapp.py --demo`'s canned responses aren't bank-related, so that mode is only useful for
exercising the UI mechanics — try the product Q&A content for real against an actual Ollama
model.

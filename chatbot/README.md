# Menu-driven chatbot (LangGraph + Qwen via Ollama)

A chatbot (CLI and web UI) built with [LangGraph](https://langchain-ai.github.io/langgraph/)
that runs a small [Qwen](https://ollama.com/library/qwen2.5) model locally through
[Ollama](https://ollama.com). Every bot turn includes a short menu of suggested replies you
can click/type the number for, or you can just type free text.

Includes a **product Q&A mode** ("Ask about products & services") that answers questions
about retail banking products (cards, deposits, loans, mortgages, mobile banking) using a
small local knowledge base, retrieval-augmented into the model's prompt.

> **⚠️ Important — read before using the product Q&A mode.** This started as a request to
> build a bank product chatbot sourced from a specific bank's site. The environment this was
> built in could not reach any live source (blocked by network policy), so
> **`knowledge/*.md` is placeholder content I wrote by hand**, modeled on typical retail
> banking products in general — it is **not real data scraped or sourced from any specific
> bank**, and the bot is **not affiliated with or endorsed by any bank**. Every knowledge
> file and the bot's own system prompt say so explicitly, and the bot is instructed to never
> claim its answers are a real bank's actual current rates, fees, or terms. Before using
> this for anything beyond a demo: replace `knowledge/*.md` with real, sourced content (see
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
python cli.py --embedding-model nomic-embed-text   # semantic retrieval — see "Semantic retrieval" below
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
    from the local `knowledge/` files (via `knowledge.retrieve`/`retrieve_scored`, a
    dependency-free TF-IDF scorer with stopword filtering, light plural stemming, and a
    title-match boost — no embedding model or vector DB needed for a handful of short
    documents) and injects them into a system prompt (`PRODUCT_SYSTEM_PROMPT`) that instructs
    the model to answer *only* from that reference material and to repeat the demo/placeholder
    disclaimer. The retrieval query is built from the last `_RETRIEVAL_CONTEXT_TURNS` (2) human
    messages, not just the latest one, so a short follow-up ("and the rewards program?") stays
    anchored to the topic raised a turn earlier instead of retrieving on its own with no
    context — predefined menu-click labels ("Ask about products & services") are excluded from
    this window since they're navigation, not content, and would otherwise pollute it with
    generic words. If nothing scores above a confidence floor, retrieval returns `[]` and the
    prompt says so explicitly, rather than grounding the model in an arbitrary/unrelated
    chunk. If the top two matches are too close to call (`knowledge.is_ambiguous`, ratio-based
    — see "Clarification questions" below), it asks which topic the user means instead of
    guessing or blending both into one answer. An optional `embedder` (see "Semantic
    retrieval" below) swaps this whole scoring step for embedding cosine similarity instead.
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
  (see the disclaimer above — this is placeholder content, not sourced from any real bank).
- `cli.py` / `webapp.py` drive the graph turn by turn using an `InMemorySaver` checkpointer,
  starting in the `"welcome"` stage.
- Graph state (`ChatState.options`) stores plain dicts (`ChatOption.model_dump()`), not
  `ChatOption` instances, so it stays fully JSON-serializable for any LangGraph checkpointer
  (in-memory, SQLite, Postgres) without needing a custom type registered for msgpack.

Swap in a different model by changing `--model`, or point `--base-url` at a remote Ollama
instance instead of running one locally.

## Clarification questions

When a question plausibly matches more than one product topic and the match is too close to
call, the bot asks which one you mean instead of guessing or blending both into one answer:

```
User: what's the interest rate?
Bot:  I can help with more than one of these — which are you asking about?
      [Deposits] [Mortgages]
User: (clicks) Mortgages
Bot:  [answer grounded specifically in the Mortgages knowledge file]
```

This is fully deterministic — no LLM call is spent on the clarification turn itself:

1. `knowledge.retrieve_scored()` returns each candidate topic's score, not just the ranked
   list.
2. `knowledge.is_ambiguous()` checks whether the top two are within `_AMBIGUITY_RATIO`
   (1.4x) of each other. Calibrated against real queries in the corpus — e.g. "how do I open
   a savings account?" scores Deposits and Mobile App both above the confidence floor (they
   share the generic word "account"), but at a clear-enough 1.43x ratio it answers directly
   rather than interrupting with an unnecessary clarification prompt.
3. If ambiguous, `product_assistant` returns a clarification turn with one option per
   candidate topic. Each option carries a `topic_key` (a `ChatOption` field distinct from
   `action`) rather than relying on the topic name alone to re-retrieve correctly next turn.
4. Picking an option sets `ChatState.forced_topic`, which the next `product_assistant` call
   uses to load that exact chunk directly via `knowledge.get_chunk()` — bypassing retrieval
   scoring entirely for that turn, since text-based re-ranking on a short label like
   "Mortgages" isn't reliable enough to guarantee landing on the intended topic when a second
   candidate is also written about it. The original question stays in the conversation
   history throughout, so the eventual grounded answer still addresses exactly what was
   asked, not just "tell me about mortgages" generically.

This only fires for genuinely close ties — see `test_no_false_positive_ambiguity_on_the_real_corpus`
in `tests/test_knowledge.py` for the specific queries it was checked against.

## Semantic retrieval

> **⚠️ Unverified.** This sandbox has no network access to Ollama, so `retrieve_semantic()`
> is unit-tested against a fake embedder (proving the cosine-similarity math, caching, and
> ranking are correct — see `tests/test_knowledge.py`) but has **not** been
> integration-tested against a real embedding model. Tune `knowledge._MIN_SEMANTIC_SCORE`
> against your own model and knowledge base before relying on this in production.

TF-IDF only matches shared words — it can't tell that "monthly cost" and "fee" mean the same
thing. Passing `--embedding-model nomic-embed-text` (or any Ollama embedding model) switches
`product_assistant` to `knowledge.retrieve_semantic()`, which ranks knowledge chunks by
embedding cosine similarity instead:

```bash
python cli.py --embedding-model nomic-embed-text
python webapp.py --embedding-model nomic-embed-text
```

Chunk embeddings are cached per process (`knowledge._embed_cached`) so the static knowledge
base is only embedded once, not re-embedded on every user turn.

**The clarification-questions flow (above) is disabled entirely in semantic mode.**
`is_ambiguous()`'s 1.4x ratio was calibrated against TF-IDF's score distribution specifically;
cosine similarity clusters very differently (unrelated documents from the same embedding
model often still score 0.3-0.5+), so applying that threshold unchanged would likely either
never fire or fire constantly depending on the model — worse than not having the feature.
Combining semantic retrieval with a properly recalibrated clarification flow is a natural
next step once the confidence floor has been tuned against a real model.

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

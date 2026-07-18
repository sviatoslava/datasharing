"""LangGraph conversation graph for a menu-driven chatbot backed by a small Qwen model via Ollama."""
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command
from pydantic import BaseModel, Field, ValidationError, field_validator

from knowledge import Chunk, get_chunk, is_ambiguous, load_recommended_options, retrieve_scored, retrieve_semantic

DEFAULT_MODEL = "qwen2.5:1.5b"
WELCOME_STAGE = "welcome"

SYSTEM_PROMPT = """You are a friendly, concise conversational assistant.

After every reply, propose 2 to 4 short options the user might pick as their next message,
like quick-reply buttons. Options must be short (under 8 words) and mutually distinct.
Set allow_free_text to false only if the user must pick one of the options (e.g. confirming
yes/no); otherwise true. If the user's turn genuinely needs a free-text answer instead (e.g.
asking for a name, a number, or open-ended detail), return an empty options list.

Respond with ONLY a single JSON object, no other text, in exactly this shape:
{"reply": "<your conversational reply>", "options": ["option 1", "option 2"], "allow_free_text": true}
"""

PRODUCT_SYSTEM_PROMPT = """You are an unofficial, unaffiliated DEMO assistant that discusses \
general retail banking products.

IMPORTANT: the reference material below is placeholder/sample content written for a coding \
demo — it is NOT real, current data from any specific bank. Never state or imply these are \
a real bank's actual current rates, fees, or terms. Always remind the user to confirm real \
details with their own bank or a bank representative before making any financial decision. \
You cannot access real accounts, move money, or perform any actual banking transaction.

Answer using ONLY the reference material below. If the answer isn't covered there, say you \
don't have that information rather than guessing.

After every reply, propose 2 to 4 short options for what the user might ask next, like \
quick-reply buttons. Set allow_free_text to false only if the user must pick one of the \
options; otherwise true.

Respond with ONLY a single JSON object, no other text, in exactly this shape:
{{"reply": "<your reply>", "options": ["option 1", "option 2"], "allow_free_text": true}}

Reference material:
{context}
"""


class ChatOption(BaseModel):
    """A single suggested next-message, shown to the user as a numbered/clickable choice."""

    id: str
    label: str = Field(max_length=40)
    value: str | None = None
    source: Literal["model", "predefined"] = "model"
    action: str | None = None  # graph node name to route to; None = replay as user text
    # Forces product_assistant to ground on this exact knowledge topic next turn, bypassing
    # retrieve() — used by clarification options, where text-based re-retrieval on a short
    # label like "Mortgages" isn't reliable enough to guarantee landing on the right topic.
    topic_key: str | None = None

    def resolved_value(self) -> str:
        return self.value or self.label


class AssistantTurn(BaseModel):
    """The narrow schema the LLM is asked to fill in each turn."""

    reply: str
    options: list[str] = Field(default_factory=list)
    allow_free_text: bool = True

    @field_validator("options")
    @classmethod
    def _dedupe_and_trim(cls, options: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for option in options:
            option = option.strip()[:40]
            if option and option.lower() not in seen:
                seen.add(option.lower())
                cleaned.append(option)
        return cleaned[:4]


class StageMenu(BaseModel):
    reply: str
    options: list[ChatOption] = Field(default_factory=list)
    # Node a free-text reply (one that doesn't match any option) should fall through to.
    # Defaults to "assistant" (generic chat), but the welcome menu overrides this to
    # "product_assistant" since that's this bot's primary purpose — a user who ignores the
    # buttons and just types a product question straight away should still get a
    # retrieval-grounded answer, not a generic chit-chat reply.
    default_active_node: str = "assistant"


PREDEFINED_MENUS: dict[str, StageMenu] = {
    WELCOME_STAGE: StageMenu(
        reply=(
            "Hi! I'm an unofficial demo assistant that can discuss general retail banking "
            "products (cards, deposits, loans, mortgages). Heads up: this uses placeholder "
            "demo content, not live data from any real bank — always confirm real details "
            "with your own bank. What would you like to do?"
        ),
        default_active_node="product_assistant",
        options=[
            ChatOption(
                id="products",
                label="Ask about products & services",
                source="predefined",
                action="product_assistant",
            ),
            ChatOption(id="chat", label="Something else", source="predefined", action="assistant"),
            ChatOption(id="human", label="Talk to a human", source="predefined", action="handoff"),
        ],
    ),
}


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    # ChatOption dicts (via .model_dump()), not ChatOption instances — keeps state made only of
    # plain JSON-serializable values, which every LangGraph checkpointer (memory/sqlite/postgres)
    # can persist without needing a custom type registered for msgpack.
    options: list[dict]
    allow_free_text: bool
    stage: str | None
    active_node: str  # which LLM-backed node produced the current turn; human()'s routing
    # default when the picked option has no explicit `action`, so a conversation stays in
    # whichever flow (assistant / product_assistant / ...) it's currently in.
    forced_topic: str | None  # set by human() when a clarification option is picked; consumed
    # (reset to None) by product_assistant on the very next turn — see ChatOption.topic_key.


# How many of the most recent human turns to fold into the retrieval query, so a short
# follow-up ("and the rewards program?") stays anchored to the topic raised a turn or two
# earlier instead of retrieving on its own with no context and (previously) finding nothing.
_RETRIEVAL_CONTEXT_TURNS = 2

# Predefined menu labels (e.g. "Ask about products & services") are navigation, not content —
# folding them into the retrieval query pollutes it with generic words ("products", "services")
# that incidentally clear the confidence floor across several topics, which previously turned
# a genuinely out-of-scope follow-up into a false "ambiguous" clarification. Excluded from the
# context window; a real follow-up (a curated option, or a clarification topic pick) still
# contributes since its text is substantive.
_NAVIGATION_PHRASES = {opt.label for menu in PREDEFINED_MENUS.values() for opt in menu.options}


def _retrieval_query(messages: list) -> str:
    human_texts = [
        m.content for m in messages if m.type == "human" and m.content not in _NAVIGATION_PHRASES
    ]
    return " ".join(human_texts[-_RETRIEVAL_CONTEXT_TURNS:])


def build_graph(model: str = DEFAULT_MODEL, base_url: str | None = None, llm=None, embedder=None):
    """embedder: optional — anything exposing `.embed_query(text) -> list[float]` (e.g.
    langchain_ollama.OllamaEmbeddings). When set, product_assistant grounds on
    knowledge.retrieve_semantic() (cosine similarity) instead of the default TF-IDF
    retrieve_scored(). NOTE: the ambiguous-match clarification flow (knowledge.is_ambiguous)
    is calibrated for TF-IDF score distributions only and is skipped entirely in semantic
    mode — see knowledge.py's "Optional semantic retrieval" section for why, and tune
    knowledge._MIN_SEMANTIC_SCORE for your embedding model before relying on this in
    production; it hasn't been integration-tested against a real model."""
    llm = llm or ChatOllama(model=model, base_url=base_url, format="json", temperature=0.4)

    def _generate_turn(system_prompt: str, state: ChatState, active_node: str) -> ChatState:
        messages = [SystemMessage(content=system_prompt), *state["messages"]]
        response = llm.invoke(messages)
        try:
            turn = AssistantTurn.model_validate_json(response.content)
        except (ValidationError, ValueError):
            turn = AssistantTurn(reply=response.content.strip() or "Sorry, I didn't catch that.")

        options = [
            ChatOption(id=f"opt_{i}", label=label, source="model")
            for i, label in enumerate(turn.options, start=1)
        ]
        return {
            "messages": [AIMessage(content=turn.reply)],
            "options": [o.model_dump() for o in options],
            "allow_free_text": turn.allow_free_text or not options,
            "stage": None,
            "active_node": active_node,
        }

    def assistant(state: ChatState) -> ChatState:
        stage = state.get("stage")
        if stage and stage in PREDEFINED_MENUS:
            menu = PREDEFINED_MENUS[stage]
            return {
                "messages": [AIMessage(content=menu.reply)],
                "options": [o.model_dump() for o in menu.options],
                "allow_free_text": True,
                "stage": None,
                "active_node": menu.default_active_node,
            }

        return _generate_turn(SYSTEM_PROMPT, state, active_node="assistant")

    def _clarify_turn(chunks: list[Chunk]) -> ChatState:
        # Deterministic — no LLM call needed for an ambiguous match. Each option locks in one
        # candidate topic (via topic_key) rather than hoping the topic name alone re-retrieves
        # unambiguously; the original question stays in the message history either way, so the
        # eventual grounded answer still addresses what was actually asked.
        options = [
            ChatOption(
                id=f"clarify_{i}",
                label=chunk.title,
                value=chunk.title,
                source="predefined",
                topic_key=chunk.topic_key,
            ).model_dump()
            for i, chunk in enumerate(chunks, start=1)
        ]
        return {
            "messages": [
                AIMessage(content="I can help with more than one of these — which are you asking about?")
            ],
            "options": options,
            "allow_free_text": True,
            "stage": None,
            "active_node": "product_assistant",
            "forced_topic": None,
        }

    def product_assistant(state: ChatState) -> ChatState:
        retrieval_query = _retrieval_query(state["messages"])

        forced_topic = state.get("forced_topic")
        if forced_topic:
            forced_chunk = get_chunk(forced_topic)
            if forced_chunk:
                chunks = [forced_chunk]
            elif embedder is not None:
                chunks = [c for c, _ in retrieve_semantic(retrieval_query, embedder)]
            else:
                chunks = [c for c, _ in retrieve_scored(retrieval_query)]
        elif embedder is not None:
            # Semantic mode skips the clarification flow entirely — is_ambiguous()'s ratio was
            # calibrated for TF-IDF score distributions, not cosine similarity, and applying it
            # unchanged risks either never firing or firing constantly depending on the model.
            chunks = [c for c, _ in retrieve_semantic(retrieval_query, embedder)]
        else:
            scored = retrieve_scored(retrieval_query)
            if is_ambiguous(scored):
                return _clarify_turn([c for c, _ in scored])
            chunks = [c for c, _ in scored]

        if chunks:
            context = "\n\n".join(f"### {c.title}\n{c.text}" for c in chunks)
            topic_key = chunks[0].topic_key
        else:
            context = (
                "(No matching reference material found for this question — say so rather "
                "than guessing, and suggest the product categories you *can* help with.)"
            )
            topic_key = "fallback"

        system_prompt = PRODUCT_SYSTEM_PROMPT.format(context=context)
        turn = _generate_turn(system_prompt, state, active_node="product_assistant")
        turn["forced_topic"] = None  # consumed — only applies to the turn it was set for

        # Curated options (knowledge/options.json) take priority over model-generated ones
        # when available for this topic — more reliable than trusting a small model to invent
        # a good, correctly-scoped menu every turn. Falls back to the model's own options
        # (already in `turn`) when the topic has no curated entry.
        recommended = load_recommended_options(topic_key)
        if recommended:
            turn["options"] = [
                ChatOption(
                    id=f"opt_{i}",
                    label=o["label"],
                    value=o.get("value"),
                    source="predefined",
                    action=o.get("action"),
                ).model_dump()
                for i, o in enumerate(recommended, start=1)
            ]
            turn["allow_free_text"] = True

        return turn

    def human(state: ChatState) -> Command:
        options = state["options"]
        user_input = interrupt(
            {
                "reply": state["messages"][-1].content,
                "options": options,
                "allow_free_text": state.get("allow_free_text", True),
            }
        )
        text = user_input.strip()

        if text.lower() in {"exit", "quit"}:
            return Command(goto=END)

        selected: dict | None = None
        if text.isdigit() and 1 <= int(text) <= len(options):
            selected = options[int(text) - 1]
        else:
            selected = next((o for o in options if o["id"] == text), None)

        resolved_text = (selected["value"] or selected["label"]) if selected else text
        goto = (
            selected["action"]
            if selected and selected["action"]
            else state.get("active_node", "assistant")
        )

        update = {"messages": [HumanMessage(content=resolved_text)]}
        if selected and selected.get("topic_key"):
            update["forced_topic"] = selected["topic_key"]

        return Command(goto=goto, update=update)

    def handoff(state: ChatState) -> ChatState:
        return {
            "messages": [
                AIMessage(
                    content="Connecting you to a human agent. "
                    "(Demo endpoint — no live agent is actually attached.)"
                )
            ],
            "options": [],
            "allow_free_text": False,
        }

    graph = StateGraph(ChatState)
    graph.add_node("assistant", assistant)
    graph.add_node("product_assistant", product_assistant)
    graph.add_node("human", human)
    graph.add_node("handoff", handoff)
    graph.add_edge(START, "assistant")
    graph.add_edge("assistant", "human")
    graph.add_edge("product_assistant", "human")
    graph.add_edge("handoff", END)

    return graph

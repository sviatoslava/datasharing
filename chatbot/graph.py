"""LangGraph conversation graph for a menu-driven chatbot backed by a small Qwen model via Ollama."""
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command
from pydantic import BaseModel, Field, ValidationError, field_validator

from knowledge import load_recommended_options, retrieve

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


def build_graph(model: str = DEFAULT_MODEL, base_url: str | None = None, llm=None):
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

    def product_assistant(state: ChatState) -> ChatState:
        last_user_text = next(
            (m.content for m in reversed(state["messages"]) if m.type == "human"), ""
        )
        chunks = retrieve(last_user_text)
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

        return Command(goto=goto, update={"messages": [HumanMessage(content=resolved_text)]})

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

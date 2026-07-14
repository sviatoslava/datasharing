"""LangGraph conversation graph for a menu-driven chatbot backed by a small Qwen model via Ollama."""
import json
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command

DEFAULT_MODEL = "qwen2.5:1.5b"

SYSTEM_PROMPT = """You are a friendly, concise conversational assistant.

After every reply, propose 2 to 4 short options the user might pick as their next message,
like quick-reply buttons. Options must be short (under 8 words) and mutually distinct.
If the user's turn genuinely needs a free-text answer instead (e.g. asking for a name, a
number, or open-ended detail), return an empty options list.

Respond with ONLY a single JSON object, no other text, in exactly this shape:
{"reply": "<your conversational reply>", "options": ["option 1", "option 2"]}
"""


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    options: list[str]


def _parse_model_output(content: str) -> tuple[str, list[str]]:
    try:
        data = json.loads(content)
        reply = str(data.get("reply", "")).strip()
        options = [str(o).strip() for o in data.get("options", []) if str(o).strip()]
        if reply:
            return reply, options
    except (json.JSONDecodeError, AttributeError):
        pass
    return content.strip(), []


def build_graph(model: str = DEFAULT_MODEL, base_url: str | None = None):
    llm = ChatOllama(model=model, base_url=base_url, format="json", temperature=0.4)

    def assistant(state: ChatState) -> ChatState:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        response = llm.invoke(messages)
        reply, options = _parse_model_output(response.content)
        return {"messages": [AIMessage(content=reply)], "options": options}

    def human(state: ChatState) -> Command:
        user_input = interrupt({"reply": state["messages"][-1].content, "options": state["options"]})
        text = user_input.strip()

        if text.lower() in {"exit", "quit"}:
            return Command(goto=END)

        options = state["options"]
        if text.isdigit() and 1 <= int(text) <= len(options):
            text = options[int(text) - 1]

        return Command(goto="assistant", update={"messages": [HumanMessage(content=text)]})

    graph = StateGraph(ChatState)
    graph.add_node("assistant", assistant)
    graph.add_node("human", human)
    graph.add_edge(START, "assistant")
    graph.add_edge("assistant", "human")

    return graph

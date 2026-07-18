"""Terminal chat loop for the LangGraph + Qwen (Ollama) menu-driven chatbot.

Usage:
    python cli.py [--model qwen2.5:1.5b] [--base-url http://localhost:11434]
    python cli.py --embedding-model nomic-embed-text   # semantic retrieval instead of TF-IDF

Type a message freely, or type the number of one of the offered options.
Type "exit" or "quit" to end the conversation.
"""
import argparse

from langchain_core.messages import AIMessage
from langchain_ollama import OllamaEmbeddings
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph import build_graph, DEFAULT_MODEL, WELCOME_STAGE


def render_turn(payload: dict) -> None:
    print(f"\nBot: {payload['reply']}")
    for i, option in enumerate(payload.get("options") or [], start=1):
        print(f"  [{i}] {option['label']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model tag to use")
    parser.add_argument("--base-url", default=None, help="Ollama server URL (defaults to http://localhost:11434)")
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Ollama embedding model (e.g. nomic-embed-text) for semantic retrieval instead "
        "of the default TF-IDF matcher. UNVERIFIED against a real model — see build_graph()'s "
        "docstring in graph.py and knowledge.py's 'Optional semantic retrieval' section before "
        "relying on this; the ambiguous-match clarification flow is disabled in this mode.",
    )
    args = parser.parse_args()

    embedder = (
        OllamaEmbeddings(model=args.embedding_model, base_url=args.base_url)
        if args.embedding_model
        else None
    )
    graph = build_graph(model=args.model, base_url=args.base_url, embedder=embedder).compile(
        checkpointer=InMemorySaver()
    )
    config = {"configurable": {"thread_id": "cli-session"}}

    print(f"Chatbot ready (model: {args.model}). Type 'exit' to quit.")
    initial_state = {
        "messages": [],
        "options": [],
        "allow_free_text": True,
        "stage": WELCOME_STAGE,
        "active_node": "assistant",
        "forced_topic": None,
    }
    result = graph.invoke(initial_state, config=config)

    quitting = False
    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        render_turn(payload)

        user_input = input("\nYou: ").strip()
        if not user_input:
            continue

        quitting = user_input.lower() in {"exit", "quit"}
        result = graph.invoke(Command(resume=user_input), config=config)

        if quitting:
            break

    if not quitting:
        final_messages = result.get("messages") or []
        if final_messages and isinstance(final_messages[-1], AIMessage):
            print(f"\nBot: {final_messages[-1].content}")

    print("\nGoodbye!")


if __name__ == "__main__":
    main()

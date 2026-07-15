"""FastAPI web UI for the LangGraph + Qwen menu-driven chatbot.

Usage:
    python webapp.py [--model qwen2.5:1.5b] [--base-url http://localhost:11434] [--port 8000]
    python webapp.py --demo   # canned local stand-in, no Ollama server required

Serves a single-page chat UI at "/" with clickable option buttons, backed by
the same LangGraph graph used by cli.py.
"""
import argparse
import itertools
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from graph import DEFAULT_MODEL, WELCOME_STAGE, build_graph

STATIC_DIR = Path(__file__).parent / "static"

DEMO_RESPONSES = [
    {
        "reply": "Nice! What genre are you in the mood for?",
        "options": ["Sci-fi", "Mystery", "Comedy", "Something else"],
        "allow_free_text": True,
    },
    {
        "reply": "Got it. Want a short recommendation or a full list?",
        "options": ["Short recommendation", "Full list"],
        "allow_free_text": False,
    },
    {
        "reply": "Here you go, enjoy! Anything else?",
        "options": ["Ask again", "No thanks"],
        "allow_free_text": True,
    },
]


class DemoLLM:
    """Canned stand-in for ChatOllama so the UI can be tried without a running Ollama server."""

    def __init__(self):
        self._cycle = itertools.cycle(DEMO_RESPONSES)

    def invoke(self, messages):
        return SimpleNamespace(content=json.dumps(next(self._cycle)))


class MessageIn(BaseModel):
    thread_id: str
    text: str


def _turn_response(thread_id: str, result: dict) -> dict:
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        return {"thread_id": thread_id, "done": False, **payload}
    messages = result.get("messages") or []
    reply = messages[-1].content if messages else ""
    return {"thread_id": thread_id, "done": True, "reply": reply, "options": [], "allow_free_text": True}


def create_app(model: str = DEFAULT_MODEL, base_url: str | None = None, llm=None) -> FastAPI:
    app = FastAPI()
    graph = build_graph(model=model, base_url=base_url, llm=llm).compile(checkpointer=InMemorySaver())

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.post("/api/start")
    def start():
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {
            "messages": [],
            "options": [],
            "allow_free_text": True,
            "stage": WELCOME_STAGE,
            "active_node": "assistant",
        }
        result = graph.invoke(initial_state, config=config)
        return _turn_response(thread_id, result)

    @app.post("/api/message")
    def message(body: MessageIn):
        config = {"configurable": {"thread_id": body.thread_id}}
        result = graph.invoke(Command(resume=body.text), config=config)
        return _turn_response(body.thread_id, result)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model tag to use")
    parser.add_argument("--base-url", default=None, help="Ollama server URL (defaults to http://localhost:11434)")
    parser.add_argument("--demo", action="store_true", help="Use a canned local stand-in instead of Ollama")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    llm = DemoLLM() if args.demo else None
    app = create_app(model=args.model, base_url=args.base_url, llm=llm)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

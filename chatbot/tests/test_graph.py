"""Tests for the LangGraph chat graph, using a fake LLM so no Ollama server is required."""
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph import WELCOME_STAGE, build_graph


class FakeLLM:
    """Stand-in for ChatOllama: returns queued raw response strings in order."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def invoke(self, messages):
        content = self._responses.pop(0)
        return SimpleNamespace(content=content)


def make_app(responses: list[str] | None = None):
    graph = build_graph(llm=FakeLLM(responses or [])).compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "test"}}
    initial_state = {"messages": [], "options": [], "allow_free_text": True, "stage": WELCOME_STAGE}
    return graph, config, initial_state


def test_welcome_stage_is_predefined_and_skips_the_llm():
    graph, config, initial_state = make_app(responses=[])  # no LLM calls expected

    result = graph.invoke(initial_state, config=config)

    assert "__interrupt__" in result
    payload = result["__interrupt__"][0].value
    assert payload["reply"].startswith("Hi!")
    labels = [o["label"] for o in payload["options"]]
    assert labels == ["Just chat", "Talk to a human"]
    assert payload["options"][0]["source"] == "predefined"
    assert payload["options"][1]["action"] == "handoff"


def test_predefined_option_with_action_routes_to_handoff_and_ends():
    graph, config, initial_state = make_app(responses=[])
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="2"), config=config)  # "Talk to a human"

    assert "__interrupt__" not in result
    assert isinstance(result["messages"][-1], AIMessage)
    assert "human agent" in result["messages"][-1].content
    # the user's choice should still be logged in the transcript
    assert any(m.content == "Talk to a human" for m in result["messages"])


def test_predefined_option_without_action_falls_through_to_llm():
    graph, config, initial_state = make_app(
        responses=['{"reply": "Sure, what\'s up?", "options": ["Weather", "Jokes"], "allow_free_text": true}']
    )
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="1"), config=config)  # "Just chat"

    assert "__interrupt__" in result
    payload = result["__interrupt__"][0].value
    assert payload["reply"] == "Sure, what's up?"
    labels = [o["label"] for o in payload["options"]]
    assert labels == ["Weather", "Jokes"]
    assert all(o["source"] == "model" for o in payload["options"])


def test_model_options_are_deduped_and_capped_at_four():
    responses = [
        '{"reply": "Pick a genre", '
        '"options": ["Sci-fi", "Sci-fi", "Mystery", "Romance", "Comedy"], '
        '"allow_free_text": false}'
    ]
    graph, config, initial_state = make_app(responses=responses)
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="1"), config=config)

    payload = result["__interrupt__"][0].value
    labels = [o["label"] for o in payload["options"]]
    assert labels == ["Sci-fi", "Mystery", "Romance", "Comedy"]
    assert payload["allow_free_text"] is False


def test_malformed_llm_output_falls_back_to_raw_text_with_no_options():
    graph, config, initial_state = make_app(responses=["not valid json{{{"])
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="1"), config=config)

    payload = result["__interrupt__"][0].value
    assert payload["reply"] == "not valid json{{{"
    assert payload["options"] == []
    assert payload["allow_free_text"] is True  # forced true since there are no options


def test_numeric_selection_resolves_to_option_value_not_the_digit():
    graph, config, initial_state = make_app(
        responses=['{"reply": "ok", "options": [], "allow_free_text": true}']
    )
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="1"), config=config)  # picks "Just chat"

    human_messages = [m.content for m in result["messages"] if m.type == "human"]
    assert "Just chat" in human_messages
    assert "1" not in human_messages


def test_free_text_input_passes_through_unchanged():
    graph, config, initial_state = make_app(
        responses=['{"reply": "Got it", "options": [], "allow_free_text": true}']
    )
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="tell me a story"), config=config)

    human_messages = [m.content for m in result["messages"] if m.type == "human"]
    assert "tell me a story" in human_messages


def test_exit_ends_conversation_without_extra_message():
    graph, config, initial_state = make_app(responses=[])
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="exit"), config=config)

    assert "__interrupt__" not in result

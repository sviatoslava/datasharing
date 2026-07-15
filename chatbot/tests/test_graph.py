"""Tests for the LangGraph chat graph, using a fake LLM so no Ollama server is required."""
from types import SimpleNamespace

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph import WELCOME_STAGE, build_graph


class FakeLLM:
    """Stand-in for ChatOllama: returns queued raw response strings in order, and records
    every `messages` list it was invoked with so tests can inspect the prompt actually sent."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(messages)
        content = self._responses.pop(0)
        return SimpleNamespace(content=content)


def make_app(responses: list[str] | None = None, llm=None):
    llm = llm or FakeLLM(responses or [])
    graph = build_graph(llm=llm).compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "test"}}
    initial_state = {
        "messages": [],
        "options": [],
        "allow_free_text": True,
        "stage": WELCOME_STAGE,
        "active_node": "assistant",
    }
    return graph, config, initial_state, llm


def test_welcome_stage_is_predefined_and_skips_the_llm():
    graph, config, initial_state, _ = make_app(responses=[])  # no LLM calls expected

    result = graph.invoke(initial_state, config=config)

    assert "__interrupt__" in result
    payload = result["__interrupt__"][0].value
    assert payload["reply"].startswith("Hi!")
    ids = [o["id"] for o in payload["options"]]
    assert ids == ["products", "chat", "human"]
    assert all(o["source"] == "predefined" for o in payload["options"])
    assert next(o for o in payload["options"] if o["id"] == "products")["action"] == "product_assistant"
    assert next(o for o in payload["options"] if o["id"] == "human")["action"] == "handoff"
    assert next(o for o in payload["options"] if o["id"] == "chat")["action"] == "assistant"


def test_predefined_option_with_action_routes_to_handoff_and_ends():
    graph, config, initial_state, _ = make_app(responses=[])
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="human"), config=config)  # "Talk to a human"

    assert "__interrupt__" not in result
    assert isinstance(result["messages"][-1], AIMessage)
    assert "human agent" in result["messages"][-1].content
    # the user's choice should still be logged in the transcript
    assert any(m.content == "Talk to a human" for m in result["messages"])


def test_predefined_option_without_action_falls_through_to_llm():
    graph, config, initial_state, _ = make_app(
        responses=['{"reply": "Sure, what\'s up?", "options": ["Weather", "Jokes"], "allow_free_text": true}']
    )
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="chat"), config=config)  # "Something else"

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
    graph, config, initial_state, _ = make_app(responses=responses)
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="chat"), config=config)

    payload = result["__interrupt__"][0].value
    labels = [o["label"] for o in payload["options"]]
    assert labels == ["Sci-fi", "Mystery", "Romance", "Comedy"]
    assert payload["allow_free_text"] is False


def test_malformed_llm_output_falls_back_to_raw_text_with_no_options():
    graph, config, initial_state, _ = make_app(responses=["not valid json{{{"])
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="chat"), config=config)

    payload = result["__interrupt__"][0].value
    assert payload["reply"] == "not valid json{{{"
    assert payload["options"] == []
    assert payload["allow_free_text"] is True  # forced true since there are no options


def test_numeric_selection_resolves_to_option_value_not_the_digit():
    graph, config, initial_state, _ = make_app(
        responses=['{"reply": "ok", "options": [], "allow_free_text": true}']
    )
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="2"), config=config)  # picks "Something else" (index 2)

    human_messages = [m.content for m in result["messages"] if m.type == "human"]
    assert "Something else" in human_messages
    assert "2" not in human_messages


def test_free_text_input_passes_through_unchanged():
    graph, config, initial_state, _ = make_app(
        responses=['{"reply": "Got it", "options": [], "allow_free_text": true}']
    )
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="tell me a story"), config=config)

    human_messages = [m.content for m in result["messages"] if m.type == "human"]
    assert "tell me a story" in human_messages


def test_free_text_from_welcome_routes_to_product_assistant_not_generic_chat():
    # A user who ignores the welcome buttons and just types a product question straight
    # away should still land in the grounded product_assistant flow, not generic chit-chat.
    llm = FakeLLM(['{"reply": "Rates vary by term.", "options": [], "allow_free_text": true}'])
    graph, config, initial_state, _ = make_app(llm=llm)
    graph.invoke(initial_state, config=config)

    graph.invoke(Command(resume="What are your mortgage rates?"), config=config)

    system_content = llm.calls[-1][0].content
    assert "Reference material:" in system_content
    assert "Mortgages" in system_content


def test_exit_ends_conversation_without_extra_message():
    graph, config, initial_state, _ = make_app(responses=[])
    graph.invoke(initial_state, config=config)

    result = graph.invoke(Command(resume="exit"), config=config)

    assert "__interrupt__" not in result


def test_product_assistant_injects_retrieved_context_and_persists_the_flow():
    llm = FakeLLM(
        [
            '{"reply": "Sure, ask away!", "options": [], "allow_free_text": true}',
            '{"reply": "Rates vary by term.", "options": ["Ask about fees"], "allow_free_text": true}',
            '{"reply": "Fees vary too.", "options": [], "allow_free_text": true}',
        ]
    )
    graph, config, initial_state, _ = make_app(llm=llm)
    graph.invoke(initial_state, config=config)

    graph.invoke(Command(resume="products"), config=config)  # enters product_assistant
    result = graph.invoke(Command(resume="Tell me about mortgage rates"), config=config)

    # the system prompt sent on that call should include retrieved mortgage content
    system_content = llm.calls[-1][0].content
    assert "Mortgage" in system_content or "mortgage" in system_content.lower()
    assert "DEMO" in system_content  # disclaimer must always be present

    payload = result["__interrupt__"][0].value
    assert payload["reply"] == "Rates vary by term."

    # a numeric follow-up (no action) should stay in product_assistant, not bounce to "assistant"
    graph.invoke(Command(resume="1"), config=config)
    assert len(llm.calls) == 3


def test_product_assistant_tells_the_model_when_nothing_matches_instead_of_guessing():
    llm = FakeLLM(
        [
            '{"reply": "Sure, ask away!", "options": [], "allow_free_text": true}',
            '{"reply": "I don\'t have that information.", "options": [], "allow_free_text": true}',
        ]
    )
    graph, config, initial_state, _ = make_app(llm=llm)
    graph.invoke(initial_state, config=config)
    graph.invoke(Command(resume="products"), config=config)

    graph.invoke(Command(resume="What's the bank's current CEO?"), config=config)

    system_content = llm.calls[-1][0].content
    assert "Reference material:" in system_content
    # no chunk matched — the prompt should say so explicitly rather than injecting a stray one
    assert "No matching reference material" in system_content
    assert "###" not in system_content


def test_curated_options_override_model_generated_ones_for_a_known_topic():
    llm = FakeLLM(
        [
            '{"reply": "Sure, ask away!", "options": [], "allow_free_text": true}',
            '{"reply": "Typically 10-20%.", "options": ["should be discarded"], "allow_free_text": false}',
        ]
    )
    graph, config, initial_state, _ = make_app(llm=llm)
    graph.invoke(initial_state, config=config)
    graph.invoke(Command(resume="products"), config=config)

    result = graph.invoke(Command(resume="How much down payment do I need for a mortgage?"), config=config)

    payload = result["__interrupt__"][0].value
    labels = [o["label"] for o in payload["options"]]
    assert labels == ["Down payment amount", "Government programs", "Refinancing"]
    assert all(o["source"] == "predefined" for o in payload["options"])
    # curated menus always allow free text too, regardless of what the model said
    assert payload["allow_free_text"] is True


def test_fallback_curated_options_used_when_no_topic_matches():
    llm = FakeLLM(
        [
            '{"reply": "Sure, ask away!", "options": [], "allow_free_text": true}',
            '{"reply": "I do not have that information.", "options": [], "allow_free_text": true}',
        ]
    )
    graph, config, initial_state, _ = make_app(llm=llm)
    graph.invoke(initial_state, config=config)
    graph.invoke(Command(resume="products"), config=config)

    result = graph.invoke(Command(resume="What's the bank's current CEO?"), config=config)

    payload = result["__interrupt__"][0].value
    handoff_opt = next(o for o in payload["options"] if o["label"] == "Talk to a human")
    assert handoff_opt["action"] == "handoff"

    # and picking it actually reaches the handoff node, not just decoration
    result = graph.invoke(Command(resume=handoff_opt["id"]), config=config)
    assert "__interrupt__" not in result
    assert "human agent" in result["messages"][-1].content


def test_topic_without_a_curated_entry_falls_back_to_model_generated_options():
    import graph as graph_module

    original = graph_module.load_recommended_options
    graph_module.load_recommended_options = lambda topic_key: None
    try:
        llm = FakeLLM(
            [
                '{"reply": "Sure, ask away!", "options": [], "allow_free_text": true}',
                '{"reply": "Typically 10-20%.", "options": ["model option A", "model option B"], '
                '"allow_free_text": true}',
            ]
        )
        graph, config, initial_state, _ = make_app(llm=llm)
        graph.invoke(initial_state, config=config)
        graph.invoke(Command(resume="products"), config=config)

        result = graph.invoke(Command(resume="How much down payment for a mortgage?"), config=config)

        payload = result["__interrupt__"][0].value
        labels = [o["label"] for o in payload["options"]]
        assert labels == ["model option A", "model option B"]
        assert all(o["source"] == "model" for o in payload["options"])
    finally:
        graph_module.load_recommended_options = original


def test_ambiguous_match_asks_for_clarification_instead_of_guessing():
    import graph as graph_module
    from knowledge import Chunk

    # Deliberately close scores rather than relying on a fragile real-corpus example — the
    # ambiguity threshold itself is unit-tested directly in test_knowledge.py. Starts straight
    # from the welcome screen (free text, no "products" click) so the mock only ever needs to
    # cover this one product_assistant call.
    fake_scored = [
        (Chunk(title="Deposits", text="deposits reference content"), 0.10),
        (Chunk(title="Mortgages", text="mortgages reference content"), 0.09),
    ]
    original = graph_module.retrieve_scored
    graph_module.retrieve_scored = lambda query, chunks=None, k=3: fake_scored
    try:
        llm = FakeLLM([])  # clarification is deterministic — should make no LLM call at all
        graph, config, initial_state, _ = make_app(llm=llm)
        graph.invoke(initial_state, config=config)

        result = graph.invoke(Command(resume="what's the rate?"), config=config)

        assert llm.calls == []
        payload = result["__interrupt__"][0].value
        labels = [o["label"] for o in payload["options"]]
        assert labels == ["Deposits", "Mortgages"]
        assert all(o["source"] == "predefined" for o in payload["options"])
        assert all(o["topic_key"] for o in payload["options"])
    finally:
        graph_module.retrieve_scored = original


def test_picking_a_clarification_option_forces_that_exact_topic():
    import graph as graph_module
    from knowledge import Chunk

    fake_scored = [
        (Chunk(title="Deposits", text="deposits reference content"), 0.10),
        (Chunk(title="Mortgages", text="mortgages reference content"), 0.09),
    ]
    original = graph_module.retrieve_scored
    graph_module.retrieve_scored = lambda query, chunks=None, k=3: fake_scored
    try:
        llm = FakeLLM(['{"reply": "Mortgage rates vary.", "options": [], "allow_free_text": true}'])
        graph, config, initial_state, _ = make_app(llm=llm)
        graph.invoke(initial_state, config=config)
        result = graph.invoke(Command(resume="what's the rate?"), config=config)
        payload = result["__interrupt__"][0].value
        mortgages_id = next(o["id"] for o in payload["options"] if o["label"] == "Mortgages")

        graph.invoke(Command(resume=mortgages_id), config=config)

        # forced_topic looks the chosen topic up directly (get_chunk), bypassing retrieve_scored
        # entirely, so it's grounded in the real Mortgages content — not the other candidate.
        system_content = llm.calls[-1][0].content
        assert "Mortgages (Home Loans)" in system_content
        assert "down payment" in system_content
        assert "Deposits & Savings" not in system_content
    finally:
        graph_module.retrieve_scored = original

"""End-to-end scenario tests matching SCENARIOS.md — full realistic multi-turn transcripts
run against the real graph, using FakeLLM to stand in for the model. Unlike test_graph.py
(which checks individual mechanisms in isolation), these walk a whole conversation the way a
real user would, and double as the executable proof behind the example transcripts in
SCENARIOS.md."""
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph import WELCOME_STAGE, build_graph
from tests.test_graph import FakeLLM


def _start(llm):
    graph = build_graph(llm=llm).compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "scenario"}}
    initial_state = {
        "messages": [],
        "options": [],
        "allow_free_text": True,
        "stage": WELCOME_STAGE,
        "active_node": "assistant",
    }
    graph.invoke(initial_state, config=config)
    return graph, config


def test_deposit_inquiry():
    llm = FakeLLM(
        [
            '{"reply": "Sure, what would you like to know?", "options": [], "allow_free_text": true}',
            '{"reply": "A savings account has no fixed term; a term deposit locks funds in '
            'for a higher rate.", "options": ["Interest rates", "How to open one"], '
            '"allow_free_text": true}',
        ]
    )
    graph, config = _start(llm)

    graph.invoke(Command(resume="products"), config=config)
    result = graph.invoke(
        Command(resume="What's the difference between a savings account and a term deposit?"),
        config=config,
    )

    system_content = llm.calls[-1][0].content
    assert "Deposits" in system_content
    payload = result["__interrupt__"][0].value
    assert "term deposit" in payload["reply"].lower()


def test_mortgage_inquiry_via_free_text():
    # no click on "Ask about products & services" — types the question straight away
    llm = FakeLLM(
        ['{"reply": "Typically 10-20% of the property value.", "options": [], "allow_free_text": true}']
    )
    graph, config = _start(llm)

    result = graph.invoke(Command(resume="How much down payment do I need for a mortgage?"), config=config)

    system_content = llm.calls[-1][0].content
    assert "Mortgages" in system_content
    payload = result["__interrupt__"][0].value
    assert "10-20%" in payload["reply"]


def test_card_inquiry_multi_turn():
    llm = FakeLLM(
        [
            '{"reply": "Sure, what would you like to know?", "options": [], "allow_free_text": true}',
            '{"reply": "Cards often include cashback on everyday purchases.", '
            '"options": ["How do I apply?", "Card security"], "allow_free_text": true}',
            '{"reply": "An income and credit check is standard.", "options": [], "allow_free_text": true}',
        ]
    )
    graph, config = _start(llm)

    graph.invoke(Command(resume="products"), config=config)
    graph.invoke(Command(resume="Tell me about credit card rewards"), config=config)
    assert "Cards" in llm.calls[-1][0].content

    # follow-up via clicking a generated option (id "opt_1" = "How do I apply?")
    result = graph.invoke(Command(resume="opt_1"), config=config)

    # stayed in the grounded product flow, didn't bounce back to generic chat
    assert "Reference material:" in llm.calls[-1][0].content
    human_messages = [m.content for m in result["messages"] if m.type == "human"]
    assert "How do I apply?" in human_messages
    assert len(llm.calls) == 3


def test_loan_inquiry():
    llm = FakeLLM(
        [
            '{"reply": "Sure, what would you like to know?", "options": [], "allow_free_text": true}',
            '{"reply": "You will need proof of income and a credit history check.", '
            '"options": [], "allow_free_text": true}',
        ]
    )
    graph, config = _start(llm)

    graph.invoke(Command(resume="products"), config=config)
    graph.invoke(Command(resume="What do I need to apply for a personal loan?"), config=config)

    assert "Loans" in llm.calls[-1][0].content


def test_out_of_scope_question():
    llm = FakeLLM(
        [
            '{"reply": "Sure, what would you like to know?", "options": [], "allow_free_text": true}',
            '{"reply": "I do not have that information.", "options": [], "allow_free_text": true}',
        ]
    )
    graph, config = _start(llm)

    graph.invoke(Command(resume="products"), config=config)
    result = graph.invoke(Command(resume="What's Halyk Bank's current CEO?"), config=config)

    system_content = llm.calls[-1][0].content
    assert "No matching reference material" in system_content
    payload = result["__interrupt__"][0].value
    assert "do not have that information" in payload["reply"].lower()


def test_immediate_human_handoff():
    llm = FakeLLM([])  # handoff never calls the LLM
    graph, config = _start(llm)

    result = graph.invoke(Command(resume="human"), config=config)

    assert "__interrupt__" not in result
    assert "human agent" in result["messages"][-1].content
    assert llm.calls == []


def test_exit_mid_product_conversation():
    llm = FakeLLM(['{"reply": "Sure, what would you like to know?", "options": [], "allow_free_text": true}'])
    graph, config = _start(llm)

    graph.invoke(Command(resume="products"), config=config)
    result = graph.invoke(Command(resume="exit"), config=config)

    assert "__interrupt__" not in result

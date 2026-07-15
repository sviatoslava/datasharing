# Common conversation scenarios

Example transcripts for the most common ways someone would actually use this bot, generated
by thinking through realistic user behavior and then **verifying each one against the real
code** (not just plausible-sounding fiction) — either via the executable scenario tests in
`tests/test_scenarios.py`, or via a direct trace against `graph.py`/`knowledge.py` where noted.
Two scenarios below surfaced real bugs, which are now fixed; two more surfaced real
*limitations* that are still open — see "Known limitations" at the end. Scenario 9
(ambiguous questions) started as a limitation itself, until a proper fix was built for it.

All examples use the placeholder knowledge base (see the disclaimer in `README.md`) —
content is representative, not real data from any specific bank.

---

### 1. Product inquiry — deposits & savings

```
Bot:  Hi! I'm an unofficial demo assistant that can discuss general retail banking
      products (cards, deposits, loans, mortgages). Heads up: this uses placeholder
      demo content, not live data from any real bank — always confirm real details
      with your own bank. What would you like to do?
      [Ask about products & services] [Something else] [Talk to a human]

User: (clicks) Ask about products & services

Bot:  Sure, what would you like to know?

User: What's the difference between a savings account and a term deposit?

Bot:  [grounded in the Deposits chunk — no fixed term / unlimited-ish withdrawals vs.
      locked-in term for a higher rate, early-withdrawal tradeoffs, etc.]
      [Interest rates] [How to open one] [Something else]
```
Covered by `test_scenarios.py::test_deposit_inquiry`.

---

### 2. Product inquiry — mortgage

```
User: (from welcome) How much down payment do I need for a mortgage?
Bot:  [grounded in the Mortgages chunk — typical 10-20% range, loan-to-value effect on
      rate, term lengths, disclaimer that real figures depend on the actual program]
```
Note this works **without** clicking "Ask about products & services" first — see
scenario 5.
Covered by `test_scenarios.py::test_mortgage_inquiry_via_free_text`.

---

### 3. Product inquiry — credit card, multi-turn same topic

```
Bot:  (welcome) ...
User: (clicks) Ask about products & services
Bot:  Sure, what would you like to know?
User: Tell me about credit card rewards
Bot:  [grounded in Cards — cashback/rewards points, bonus categories]
      [Annual & monthly fees] [How do I apply?] [Card security features]
User: (clicks) How do I apply?
Bot:  [continues, still in product_assistant flow — active_node persisted]
```
The three options shown are **curated** (`knowledge/options.json`'s `"cards"` entry), not
model-generated — `product_assistant` overrides whatever options the model proposed with the
curated list for the matched topic when one exists, falling back to the model's own options
only for topics with no `options.json` entry. See `knowledge/options.json` to edit these.
Covered by `test_scenarios.py::test_card_inquiry_multi_turn` and
`test_graph.py::test_curated_options_override_model_generated_ones_for_a_known_topic`.

---

### 4. Product inquiry — personal loan eligibility

```
User: (from welcome, clicks products) What do I need to apply for a personal loan?
Bot:  [grounded in Loans — income/credit check, proof of income, self-employed notes]
```
Covered by `test_scenarios.py::test_loan_inquiry`.

---

### 5. Straight-to-the-point — no menu click at all

A user who ignores the buttons entirely and just types their real question on the first
turn. Arguably the *most* common real behavior, and initially the code got this wrong.

```
Bot:  (welcome menu shown)
User: What are your mortgage rates?          <- typed directly, ignoring the buttons
Bot:  [correctly grounded in Mortgages]
```
**This was a real bug**, found while building this scenario: the welcome stage
hardcoded the post-welcome fallback flow to the generic (non-grounded) `assistant` node
regardless of what the user actually did next, so typing a product question directly
produced an ungrounded chit-chat answer instead of a retrieval-grounded one. Fixed by
giving `StageMenu` a `default_active_node` (welcome now defaults to
`"product_assistant"`, since that's this bot's whole purpose; only clicking "Something
else" explicitly switches to generic chat). Regression-tested by
`test_graph.py::test_free_text_from_welcome_routes_to_product_assistant_not_generic_chat`.

---

### 6. Out-of-scope question

```
User: (in product mode) What's the bank's current CEO?
Bot:  I don't have that information — I can help with cards, deposits, loans,
      mortgages, or mobile banking questions instead.
```
**This was also a real bug**, found the same way: the original retrieval scorer had no
stopword filtering, so an incidental shared word (e.g. "between") could out-rank genuine
topic words entirely, and there was no confidence floor — every query returned *some*
chunk, including for questions with no real match, risking the model latching onto
unrelated reference text. Fixed with a stopword list, proper TF-IDF (term frequency,
not just presence), a title-match boost, a minimum-score confidence floor, and — when
nothing clears that floor — an explicit "no matching reference material" note injected
into the prompt instead of silently substituting an arbitrary chunk. Covered by
`test_scenarios.py::test_out_of_scope_question` and `test_knowledge.py`.

---

### 7. Immediate human handoff

```
Bot:  (welcome menu)
User: (clicks) Talk to a human
Bot:  Connecting you to a human agent. (Demo endpoint — no live agent is actually
      attached.)
      [conversation ends]
```
Covered by `test_graph.py::test_predefined_option_with_action_routes_to_handoff_and_ends`.

---

### 8. Exit mid-conversation

```
User: (anywhere in the flow) exit
Bot:  [conversation ends immediately, no extra message]
```
Covered by `test_graph.py::test_exit_ends_conversation_without_extra_message`.

---

### 9. Ambiguous question — bot asks for clarification

```
User: (in product mode) what's the interest rate?
Bot:  I can help with more than one of these — which are you asking about?
      [Deposits] [Mortgages]
User: (clicks) Mortgages
Bot:  [grounded specifically in Mortgages — not a blended guess, and not the Deposits
      content that also matched]
```
Deterministic, no LLM call for the clarification turn itself: `knowledge.retrieve_scored()`
exposes each candidate's score, and `knowledge.is_ambiguous()` checks whether the top two
are within 1.4x of each other. Picking an option sets `ChatState.forced_topic`, which
bypasses retrieval scoring entirely on the next turn (`knowledge.get_chunk()` loads that
exact topic directly) rather than trusting a short label like "Mortgages" to reliably
re-retrieve to a single chunk on its own — it doesn't (verified: appending the topic name to
the original ambiguous query still left both candidates above the confidence floor). See
"Clarification questions" in `README.md` for the full mechanism and how the 1.4x threshold
was calibrated against false positives (e.g. "how do I open a savings account?" also
technically matches two topics but is answered directly, not treated as ambiguous).
Covered by `test_graph.py::test_ambiguous_match_asks_for_clarification_instead_of_guessing`
and `test_graph.py::test_picking_a_clarification_option_forces_that_exact_topic`.

---

## Known limitations (not yet fixed — flagging rather than silently shipping)

### A. Short follow-ups can lose the topic

Retrieval only looks at the user's latest message, not the conversation so far. A natural
follow-up like:

```
User: Tell me about credit card fees
Bot:  [grounded in Cards]
User: and the rewards program?
Bot:  [retrieve("and the rewards program?") -> [] — no confident match, even though a
      human would obviously read this as still being about cards]
```

Verified directly: `retrieve("and fees?")` and `retrieve("how do I apply?")` both return
`[]` in isolation, even right after a clearly on-topic first turn. A fix would mean
building the retrieval query from recent conversation context (e.g. the last user message
plus the current `active_node`'s topic, or the last couple of turns) rather than the
latest message alone.

### B. No way to reach a human mid-conversation

"Talk to a human" only exists as a predefined option on the welcome menu (`action:
"handoff"`). Once inside `product_assistant`, model-generated options never carry an
`action` (`ChatOption(..., source="model")` always has `action=None`), so a user typing
"I want to talk to a real person" mid-conversation just gets treated as another product
question — there's no code path back to the `handoff` node. A fix would need either (a)
the product system prompt instructed to emit an option literally labeled "Talk to a
human" when it detects that intent, with code mapping that specific label to
`action="handoff"` post-hoc, or (b) a lightweight intent check on every free-text turn
before it reaches the LLM.

Want me to implement a fix for either of these?

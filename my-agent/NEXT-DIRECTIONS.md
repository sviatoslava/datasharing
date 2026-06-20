# NEXT-DIRECTIONS.md — Agentic AI Tutor

## v1 — After first week of lessons

### Spaced repetition
**What:** Re-quiz concepts the student scored < 70% on, injected into future lessons automatically.
**Why:** Single-pass learning doesn't stick — revisiting strengthens retention.
**How:** Add a `failed_topics` array to lesson-log.json. On each run, if lesson N > 7, pick one failed topic and append a 2-question bonus review section to the email.

### Two-way quiz grading
**What:** Sviatoslava replies to the email with her quiz answers; the agent grades them.
**Why:** Self-grading (scrolling to see answers) has low accountability. Real grading closes the loop.
**How:** Set up a Gmail label + filter for replies to the tutor. Add a second deployment triggered on reply (event-driven). Parse reply text, grade against stored answers, update lesson-log.json with score, adjust next lesson difficulty accordingly.
**Credential needed:** Gmail OAuth (read access) — not just App Password.

## v2 — After two weeks

### Learning style profile
**What:** After 7 sessions, analyze quiz scores + time-of-open patterns to infer learning style (conceptual vs hands-on, fast vs slow) and adjust lesson format automatically.
**How:** Add a `learning_profile.json` that the agent updates after each run. Feed profile summary into system prompt context each session.

### Slack delivery option
**What:** Mirror the daily lesson to a personal Slack channel in addition to email.
**How:** Add Slack MCP server as connector; post formatted lesson as a Slack message with interactive quiz buttons (Block Kit).
**Credential needed:** Slack Bot Token with `chat:write` scope.

### Progress dashboard
**What:** A weekly HTML report showing: lessons completed, quiz scores over time, topics mastered, topics to revisit.
**How:** Generate `weekly-report.html` every Sunday. Email it as a separate digest.

## fallback — If CMA is unavailable

Run as a local Claude Code workflow:
```bash
source my-agent/.env
claude -p "$(cat my-agent/first_prompt.txt)"
```
Add to crontab for scheduling:
```
0 16 * * * cd /home/user/datasharing && source my-agent/.env && claude -p "$(cat my-agent/first_prompt.txt)" >> my-agent/local-run.log 2>&1
```
When CMA becomes available, "Launch Your Agent" is the upgrade path — IDs will be fresh, same agent.json config.

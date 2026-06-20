# LAUNCH.md — Agentic AI Tutor
## Resumable step-by-step launch sequence

All steps read/write IDs to IDS.env. If a step is already done, skip to the next one.

---

### Prerequisites
```bash
cd my-agent
source .env                        # loads ANTHROPIC_API_KEY, GMAIL_APP_PASSWORD, etc.
# Verify key is set:
echo ${ANTHROPIC_API_KEY:+OK}      # should print "OK"
```

---

### Step 1 — Pick the model
```bash
MODEL_SLUG=$(curl -s https://api.anthropic.com/v1/models \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" | \
  python3 -c "
import json, sys
models = json.load(sys.stdin)['data']
opus = [m for m in models if 'opus' in m['id'].lower()]
print(sorted(opus, key=lambda m: m['created_at'], reverse=True)[0]['id'])
")
echo "MODEL_SLUG=$MODEL_SLUG" >> IDS.env
echo "✅ Model: $MODEL_SLUG"
```

---

### Step 2 — Create environment
```bash
ENV_RESP=$(curl -s -X POST https://api.anthropic.com/v1/environments \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d @environment.json)
ENVIRONMENT_ID=$(python3 -c "import json,sys; print(json.loads('$ENV_RESP')['id'])")
echo "ENVIRONMENT_ID=$ENVIRONMENT_ID" >> IDS.env
echo "✅ 📦 environment $ENVIRONMENT_ID"
```

---

### Step 3 — Create agent
```bash
source IDS.env
AGENT_PAYLOAD=$(python3 -c "
import json
a = json.load(open('agent.json'))
a['model'] = '$MODEL_SLUG'
a['environment_id'] = '$ENVIRONMENT_ID'
# Inject Gmail credentials into system prompt env vars
print(json.dumps(a))
")
AGENT_RESP=$(curl -s -X POST https://api.anthropic.com/v1/agents \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d "$AGENT_PAYLOAD")
AGENT_ID=$(python3 -c "import json,sys; d=json.loads('$AGENT_RESP'); print(d['id'])")
AGENT_VERSION=$(python3 -c "import json,sys; d=json.loads('$AGENT_RESP'); print(d['version'])")
echo "AGENT_ID=$AGENT_ID" >> IDS.env
echo "AGENT_VERSION=$AGENT_VERSION" >> IDS.env
echo "✅ 🤖 agent $AGENT_ID (v$AGENT_VERSION, $MODEL_SLUG)"
```

---

### Step 4 — Create session
```bash
source IDS.env
SESSION_RESP=$(curl -s -X POST https://api.anthropic.com/v1/sessions \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\"}")
SESSION_ID=$(python3 -c "import json,sys; print(json.loads('$SESSION_RESP')['id'])")
echo "SESSION_ID=$SESSION_ID" >> IDS.env
echo "✅ ▶️ session $SESSION_ID created"
```

---

### Step 5 — Kick off with outcome
```bash
source IDS.env
# Inject Gmail app password as a secret event before kickoff
curl -s -X POST "https://api.anthropic.com/v1/sessions/${SESSION_ID}/events" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d "{\"type\": \"secret\", \"name\": \"GMAIL_APP_PASSWORD\", \"value\": \"$GMAIL_APP_PASSWORD\"}"

curl -s -X POST "https://api.anthropic.com/v1/sessions/${SESSION_ID}/events" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d @kickoff.json

echo "✅ ▶️ run started $SESSION_ID"
echo ""
echo "Watch it run:"
echo "  https://platform.anthropic.com/workspaces"
```

---

### Step 6 — Create daily deployment
```bash
source IDS.env
DEPLOY_PAYLOAD=$(python3 -c "
import json
d = json.load(open('deployment.json'))
d['agent_id'] = '$AGENT_ID'
print(json.dumps(d))
")
DEPLOY_RESP=$(curl -s -X POST https://api.anthropic.com/v1/deployments \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d "$DEPLOY_PAYLOAD")
DEPLOYMENT_ID=$(python3 -c "import json,sys; print(json.loads('$DEPLOY_RESP')['id'])")
NEXT_RUN=$(python3 -c "import json,sys; print(json.loads('$DEPLOY_RESP').get('upcoming_runs_at','unknown'))")
echo "DEPLOYMENT_ID=$DEPLOYMENT_ID" >> IDS.env
echo "✅ 🗓️ deployment $DEPLOYMENT_ID"
echo "   Next run: $NEXT_RUN"
echo "   Schedule: daily at 16:00 UTC (7pm Kyiv)"
```

---

### Troubleshooting
| Error | Fix |
|-------|-----|
| 401 | Check API key matches your Console workspace |
| 400 on agent-create | Check model slug is exact; tools array uses `agent_toolset_20260401` |
| jq failures | Use `python3 -c "import json,sys; ..."` instead of jq |
| Email not arriving | Check Gmail App Password, verify 2FA is on in Google account |
| Hung session | Re-poll from IDS.env session ID |

---

### Fallback: run as local Claude Code workflow
If CMA is unreachable, run the agent locally:
```bash
source .env
claude -p "$(cat first_prompt.txt)"
```
See NEXT-DIRECTIONS.md #fallback for making this permanent.

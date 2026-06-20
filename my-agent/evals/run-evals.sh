#!/bin/bash
# Run eval cases against a pinned agent version
# Usage: ./run-evals.sh <AGENT_ID> <VERSION>
# Results written to evals/results-v<VERSION>.json

set -e
source ../.env

AGENT_ID=${1:?Usage: run-evals.sh AGENT_ID VERSION}
VERSION=${2:?Usage: run-evals.sh AGENT_ID VERSION}
RESULTS_FILE="results-v${VERSION}.json"
BASE_URL="https://api.anthropic.com/v1"
HEADERS=(-H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json")

echo "[]" > "$RESULTS_FILE"

for case_dir in case-*/; do
  CASE_ID=$(basename "$case_dir")
  INPUT=$(cat "$case_dir/input.md")

  echo "Running $CASE_ID against agent $AGENT_ID v$VERSION..."

  SESSION=$(curl -s "${BASE_URL}/sessions" "${HEADERS[@]}" \
    -d "{\"agent_id\": \"$AGENT_ID\"}" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

  curl -s "${BASE_URL}/sessions/${SESSION}/events" "${HEADERS[@]}" \
    -d "{\"type\": \"user\", \"content\": \"$INPUT\"}" > /dev/null

  python3 -c "
import json, sys
results = json.load(open('$RESULTS_FILE'))
results.append({'case': '$CASE_ID', 'session_id': '$SESSION', 'agent_version': $VERSION, 'status': 'running'})
json.dump(results, open('$RESULTS_FILE', 'w'), indent=2)
"
  echo "  Started: session $SESSION"
done

echo "All eval cases launched. Check $RESULTS_FILE for session IDs."
echo "Grade verdicts at: https://platform.anthropic.com/workspaces"

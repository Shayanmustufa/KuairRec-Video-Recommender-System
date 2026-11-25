#!/usr/bin/env sh
# Day 10/12 exit criteria: feedback and logs survive an API restart and a full
# stack restart, and logs are queryable. Run from backend-frontend/ with the
# stack already up. Ports follow .env (defaults 8080 / 3000).
set -eu
API="http://localhost:${API_PORT:-8080}"
WEB="http://localhost:${WEB_PORT:-3000}"
RID="restart-check-$(date +%s)"

wait_ready() {
  for _ in $(seq 1 60); do
    if curl -fs "$API/readyz" >/dev/null 2>&1 && curl -fs -o /dev/null "$WEB/" 2>/dev/null; then return 0; fi
    sleep 2
  done
  echo "stack did not become ready" >&2; exit 1
}

count() { curl -fsS "$API/api/v1/feedback?user_id=restart-probe&limit=500" | python -c "import json,sys;print(len(json.load(sys.stdin)['events']))"; }

wait_ready
echo "== 1. record feedback through the web proxy (request id $RID)"
curl -fsS -X POST "$WEB/api/v1/feedback" -H 'Content-Type: application/json' -H "X-Request-ID: $RID" \
  -d '{"user_id":"restart-probe","item_id":"5434","action":"click","rank":1}'
echo
BEFORE=$(count); echo "feedback rows for restart-probe: $BEFORE"

echo "== 2. restart only the API container"
docker compose restart backend >/dev/null; wait_ready
AFTER_API=$(count); echo "after API restart: $AFTER_API"

echo "== 3. full stack down/up (volume kept, containers recreated)"
docker compose down >/dev/null; docker compose up -d >/dev/null; wait_ready
AFTER_STACK=$(count); echo "after full restart: $AFTER_STACK"

echo "== 4. logs are queryable by request id"
curl -fsS "$API/api/v1/logs/requests?request_id=$RID"; echo
curl -fsS "$API/api/v1/feedback?user_id=restart-probe&limit=1"; echo

[ "$BEFORE" -ge 1 ] && [ "$AFTER_API" = "$BEFORE" ] && [ "$AFTER_STACK" = "$BEFORE" ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }

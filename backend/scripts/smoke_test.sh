#!/usr/bin/env bash
# Manual/CI smoke test of the full request path against a running stack.
# Usage: BASE_URL=http://localhost:8000 ./scripts/smoke_test.sh
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "Waiting for /ready ..."
for i in $(seq 1 30); do
  if curl -sf "$BASE_URL/ready" > /dev/null; then break; fi
  sleep 1
done

echo "POST /api/complaints ..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/complaints" \
  -H "Content-Type: application/json" \
  -d '{"text":"Burst water main flooding Street 12 since fajr","location":"Sector G-9"}')
echo "$RESPONSE"
ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "GET /api/complaints/$ID ..."
curl -sf "$BASE_URL/api/complaints/$ID" > /dev/null && echo "OK"

echo "GET /api/stats (expect MISS then HIT) ..."
curl -sD - "$BASE_URL/api/stats" -o /dev/null | grep -i x-cache
curl -sD - "$BASE_URL/api/stats" -o /dev/null | grep -i x-cache

echo "Smoke test passed."

#!/usr/bin/env bash
# Captures the scale-out evidence §3.3 asks for: `kubectl get hpa -w` output
# plus a timestamped replicas-against-load series you can chart.
#
# Run this in one terminal, the k6 load test in another:
#   Terminal 1: ./scripts/capture-hpa.sh
#   Terminal 2: k6 run scripts/load-test.js
set -euo pipefail

NS="${NS:-civicpulse}"
OUT="${OUT:-docs/evidence}"
DURATION="${DURATION:-420}"     # match the k6 stages: 30+30+10+180+30+120 = 400s
mkdir -p "$OUT"

echo "Recording HPA behaviour for ${DURATION}s into $OUT/"
echo "Starting replicas: $(kubectl -n "$NS" get deploy backend -o jsonpath='{.spec.replicas}')"

# The raw watch output the rubric names explicitly.
timeout "$DURATION" kubectl -n "$NS" get hpa backend -w | tee "$OUT/hpa-watch.txt" &
watch_pid=$!

# A parseable series for the chart: seconds since start, desired replicas,
# ready replicas, current CPU utilisation.
{
  echo "elapsed_s,desired_replicas,ready_replicas,cpu_utilisation_pct"
  start=$(date +%s)
  while [ $(($(date +%s) - start)) -lt "$DURATION" ]; do
    hpa=$(kubectl -n "$NS" get hpa backend -o json)
    desired=$(echo "$hpa" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"].get("desiredReplicas",0))')
    cpu=$(echo "$hpa" | python3 -c 'import sys,json;d=json.load(sys.stdin);m=d["status"].get("currentMetrics") or [{}];print((m[0].get("resource",{}).get("current",{}) or {}).get("averageUtilization","") or "")')
    ready=$(kubectl -n "$NS" get deploy backend -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)
    echo "$(($(date +%s) - start)),$desired,${ready:-0},$cpu"
    sleep 5
  done
} | tee "$OUT/hpa-series.csv"

wait $watch_pid 2>/dev/null || true

echo
echo "Wrote $OUT/hpa-watch.txt and $OUT/hpa-series.csv"
echo "Chart it, then answer engineering note #5 from the CSV: the lag is the gap"
echo "between the row where cpu_utilisation_pct crosses 60 and the row where"
echo "ready_replicas first exceeds its starting value. Expect roughly 45-90s,"
echo "made up of: metrics-server scrape interval (~15s) + HPA sync period (~15s)"
echo "+ image pull and container start + the startupProbe passing."

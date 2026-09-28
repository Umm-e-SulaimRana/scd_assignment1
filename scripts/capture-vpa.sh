#!/usr/bin/env bash
# The VPA loop from §3.3, steps 1 and 3: record what we guessed, then record
# what the VPA measured.
#
#   ./scripts/capture-vpa.sh | tee docs/evidence/vpa-recommendation.txt
set -euo pipefail
NS="${NS:-civicpulse}"

echo "VPA recommender output -- $(date -u +%FT%TZ)"
echo
echo "1. What we guessed when writing k8s/base/backend.yaml:"
kubectl -n "$NS" get deploy backend \
  -o jsonpath='   requests: cpu={.spec.template.spec.containers[0].resources.requests.cpu} memory={.spec.template.spec.containers[0].resources.requests.memory}{"\n"}   limits:   cpu={.spec.template.spec.containers[0].resources.limits.cpu} memory={.spec.template.spec.containers[0].resources.limits.memory}{"\n"}'

echo
echo "2. What the VPA measured after the load test:"
kubectl -n "$NS" describe vpa backend-vpa | sed -n '/Recommendation/,$p'

echo
echo "3. Next: update requests in k8s/base/backend.yaml to the Target values,"
echo "   re-run the load test, and write down what changed about HPA behaviour."
echo "   Raising the request lowers computed utilisation for the same real load,"
echo "   so the HPA crosses 60% later and scales out less aggressively -- which"
echo "   is the same coupling that makes updateMode: Auto unsafe here."

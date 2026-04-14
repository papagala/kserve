#!/bin/bash
set -euo pipefail

HOST="retry-test-graph.ig-retry-test.example.com"
GATEWAY="http://localhost:8090"

echo "=== Starting port-forward ==="
lsof -ti:8090 | xargs kill -9 2>/dev/null || true
sleep 1
kubectl port-forward svc/istio-ingressgateway -n istio-system 8090:80 &>/dev/null &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null" EXIT
sleep 3

# Ensure the knative service is scaled up
echo "=== Warmup request ==="
curl -s -o /dev/null -w "Warmup: HTTP %{http_code}\n" -X POST \
  -H "Host: $HOST" -H "Content-Type: application/json" \
  -d '{"instances":["warmup"]}' "$GATEWAY" --max-time 60

echo ""
echo "=== Sending 20 requests ==="
SUCCESS=0
FAIL=0
for i in $(seq 1 20); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Host: $HOST" -H "Content-Type: application/json" \
    -d '{"instances":["test"]}' "$GATEWAY" --max-time 30)
  if [ "$CODE" = "200" ]; then
    SUCCESS=$((SUCCESS + 1))
    echo -n "."
  else
    FAIL=$((FAIL + 1))
    echo -n "X"
  fi
done
echo ""
echo "=== Results: $SUCCESS/20 succeeded, $FAIL/20 failed ==="

echo ""
echo "=== Router retry logs ==="
stern retry-test-graph -n ig-retry-test -c user-container --no-follow --since 2m -o raw 2>&1 | grep -i "Retrying\|retriable\|exhausted\|All retries" | tail -20
echo "=== Done ==="

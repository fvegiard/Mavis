#!/usr/bin/env bash
# Delegate demo — shows mavis-delegate's full workflow
# Requires: mavis-call, mavis-rag, mavis-openhands installed and running
#           OpenHands Agent Canvas stack up (mavis-openhands up)

set -e
echo "=== mavis-delegate workflow demo ==="
echo

echo "--- 1. Show the decision matrix ---"
mavis-delegate --matrix
echo

echo "--- 2. Classify 5 sample tasks (dry-run, no dispatch) ---"
for t in \
  "fix the failing test in mavis-hook.py" \
  "research best 2026 agent frameworks" \
  "restart nginx on prod server" \
  "verify this code is correct" \
  "find where X is defined"; do
  AGENT=$(mavis-delegate --dry-run "$t" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('agent','?'))")
  printf "  %-50s → %s\n" "$t" "$AGENT"
done
echo

echo "--- 3. End-to-end: delegate a real code task to OpenHands ---"
WS=/tmp/delegate-demo
rm -rf $WS
mkdir -p $WS
mavis-delegate \
  "Use file_editor to create $WS/fib.py containing a fibonacci function that computes fib(10) and prints the result. Then run python3 $WS/fib.py. Reply with just the output." \
  --workspace $WS \
  --expected fib.py \
  --timeout 120

echo
echo "--- 4. Verify the artifact ---"
if [ -f "$WS/fib.py" ]; then
  echo "  [OK] $WS/fib.py exists ($(wc -c < $WS/fib.py) bytes)"
  echo "  --- content ---"
  cat "$WS/fib.py"
  echo "  --- running ---"
  python3 "$WS/fib.py"
else
  echo "  [FAIL] $WS/fib.py was NOT created"
  exit 1
fi
echo

echo "=== demo complete ==="

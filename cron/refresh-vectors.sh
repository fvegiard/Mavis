#!/bin/bash
# refresh-vectors.sh — Daily idempotent re-embedding of Supabase content.
#
# Re-runs both:
#  - mavis-vectorize     (re-embeds any NULL mavis_knowledge.embedding)
#  - mavis-vectorize-extra (migrates new rows from tasks/alerts/state/cron tables)
#
# Safe to run any number of times — both scripts skip already-embedded rows.
#
# Add to cron with:
#   crontab -e
#   0 4 * * * /workspace/jarvis/cron/refresh-vectors.sh >> /var/log/mavis-rag-refresh.log 2>&1
#
# Or call from Mavis cron system:
#   mavis cron create --agent-name mavis --cron-name daily-vector-refresh \
#     --schedule "0 4 * * *" --prompt "run /workspace/jarvis/cron/refresh-vectors.sh"

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"

# Load OpenRouter key from env or fall back to a local file
if [ -z "$OPENROUTER_API_KEY" ]; then
    for f in /root/.mavis/secrets/openrouter /etc/mavis/openrouter ~/.mavis/openrouter; do
        if [ -f "$f" ]; then
            export OPENROUTER_API_KEY=$(cat "$f")
            break
        fi
    done
fi

if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "🔴 $(date -Iseconds) refresh-vectors: no OPENROUTER_API_KEY, aborting" >&2
    exit 1
fi

echo "=== $(date -Iseconds) refresh-vectors starting ==="

# 1. Re-embed any NULL rows in mavis_knowledge
echo "--- mavis-vectorize ---"
python3 "$SCRIPT_DIR/mavis-vectorize.py" 2>&1

# 2. Migrate new rows from other tables
echo "--- mavis-vectorize-extra ---"
python3 "$SCRIPT_DIR/mavis-vectorize-extra.py" 2>&1

# 3. Refresh the RAG cache
echo "--- mavis-rag --refresh-cache ---"
python3 "$SCRIPT_DIR/mavis-rag.py" --refresh-cache "warmup" 2>&1

echo "=== $(date -Iseconds) refresh-vectors done ==="

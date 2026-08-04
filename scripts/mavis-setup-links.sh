#!/usr/bin/env bash
# mavis-setup-links.sh — Re-create all mavis-* symlinks in /usr/local/bin
# Run after sandbox restart (symlinks don't persist outside the workspace)

set -euo pipefail
SCRIPTS_DIR="${1:-/workspace/jarvis/scripts}"

if [ ! -d "$SCRIPTS_DIR" ]; then
    echo "[ERROR] Scripts dir not found: $SCRIPTS_DIR" >&2
    exit 1
fi

LINKED=0
SKIPPED=0
for src in "$SCRIPTS_DIR"/mavis-*; do
    [ -f "$src" ] || continue
    name=$(basename "$src" .py)  # mavis-call from mavis-call (no .py)
    name=$(basename "$src")       # mavis-X from mavis-X.py
    name="${name%.py}"            # strip .py
    link="/usr/local/bin/$name"
    ln -sf "$src" "$link"
    LINKED=$((LINKED + 1))
done

echo "✅ Linked $LINKED mavis-* tools in /usr/local/bin"
echo
echo "Available commands:"
ls /usr/local/bin/mavis-* | sed 's|/usr/local/bin/||' | column

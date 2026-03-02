#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/Users/lijiaolong/.openclaw/workspace/daynews"
PAGE="${REPO_DIR}/docs/每日财经早报$(date +%Y.%m.%d).html"

# Render full page (Chinese-first structure)
/usr/bin/python3 "${REPO_DIR}/scripts/render_brief.py"

if [ ! -f "$PAGE" ]; then
  echo "missing page: $PAGE" >&2
  exit 2
fi

cd "$REPO_DIR"

# Commit only if changed
if git diff --quiet -- "$PAGE"; then
  echo "no change"
  exit 0
fi

NOW_BJT=$(date "+%Y-%m-%d %H:%M:%S")

git add "$PAGE"
git commit -m "Auto render: $NOW_BJT" >/dev/null

git push >/dev/null

echo "pushed $NOW_BJT"

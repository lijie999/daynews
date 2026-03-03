#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/Users/lijiaolong/.openclaw/workspace/daynews"

# Delegate to the smarter updater (venv + translation cache + index maintenance)
exec /bin/bash "/Users/lijiaolong/.openclaw/workspace/scripts/daynews-update.sh"

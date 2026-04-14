#!/usr/bin/env bash
# devsync.sh  —  rsync local sources to the dev server, then run Python remotely.
#
# Usage:
#   ./devsync.sh                         # runs: python -m chatdku.core.agent
#   ./devsync.sh path/to/file.py         # runs: python path/to/file.py
#   ./devsync.sh chatdku.core.agent      # runs: python -m chatdku.core.agent
# Arguments with `/` or a `.py` suffix are treated as file paths; everything
# else is treated as a module name and run with `python -m`.
set -euo pipefail

BOLD="\033[1m"
DIM="\033[2m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

info()    { echo -e "${CYAN}${BOLD}→${RESET} $*"; }
success() { echo -e "${GREEN}${BOLD}✓${RESET} $*"; }
step()    { echo -e "${YELLOW}${BOLD}»${RESET} ${DIM}$*${RESET}"; }
warn()    { echo -e "${RED}${BOLD}!${RESET} $*"; }

_GH_USER="$(gh api user -q .login 2>/dev/null || true)"
_SSH_USER="${_GH_USER:-$(whoami)}"
SERVER="${CHATDKU_SERVER:-${_SSH_USER}@10.200.14.82}"
REMOTE_DIR="${CHATDKU_REMOTE_DIR:-~/ChatDKU-DevSync}"
LOCAL_DIR="$(git rev-parse --show-toplevel)"

# Accept a leading `-m` / `--module` flag for familiarity; we always decide
# file-vs-module from the argument shape below.
if [[ "${1:-}" == "-m" || "${1:-}" == "--module" ]]; then
    shift
fi

TARGET="${1:-}"
if [[ -n "$TARGET" ]]; then
    if [[ "$TARGET" != *"/"* && "$TARGET" != *.py ]]; then
        # Looks like a module (e.g. chatdku.core.agent) — run with -m
        REMOTE_RUN_CMD="uv run python -m $(printf %q "$TARGET")"
        RUN_DESC="python -m $TARGET"
    else
        # Treat as a file path
        if [[ "$TARGET" = /* ]]; then
            TARGET="${TARGET#"$LOCAL_DIR"/}"
        fi
        if [[ ! -f "$LOCAL_DIR/$TARGET" ]]; then
            warn "target '$TARGET' not found under $LOCAL_DIR — syncing anyway"
        fi
        REMOTE_RUN_CMD="uv run python $(printf %q "$TARGET")"
        RUN_DESC="python $TARGET"
    fi
else
    REMOTE_RUN_CMD="uv run python -m chatdku.core.agent"
    RUN_DESC="agent"
fi

step "preparing remote directory $REMOTE_DIR on $SERVER"
ssh "${SERVER}" "mkdir -p ${REMOTE_DIR}"

step "linking ~/.env → ${REMOTE_DIR}/.env"
ssh "${SERVER}" '
  if [ -f ~/.env ]; then
    ln -sf ~/.env '"${REMOTE_DIR}"'/.env
  else
    echo "WARN: ~/.env not found on server — skipping link"
  fi
'
if ssh "${SERVER}" '[ ! -f '"${REMOTE_DIR}"'/.env ]'; then
  warn "no .env in ${REMOTE_DIR} — the agent may fail to start"
fi

info "syncing ${BOLD}$LOCAL_DIR${RESET}${CYAN} → ${BOLD}$SERVER:$REMOTE_DIR"

rsync -avz --delete \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.egg-info/' \
  --exclude='.env' \
  --exclude='node_modules/' \
  --exclude='frontend/build/' \
  --filter=':- .gitignore' \
  "$LOCAL_DIR/" \
  "$SERVER:$REMOTE_DIR/"

success "synced"

info "connecting to ${BOLD}$SERVER${RESET}${CYAN} — running ${BOLD}${RUN_DESC}${RESET}"
ssh -t "${SERVER}" "bash -l -c 'cd ${REMOTE_DIR} && uv sync && ${REMOTE_RUN_CMD}'"

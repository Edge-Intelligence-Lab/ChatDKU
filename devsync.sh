#!/usr/bin/env bash
# devsync.sh  —  rsync local sources to the dev server, then drop into an interactive agent session.
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

info "connecting to ${BOLD}$SERVER${RESET}${CYAN} — running agent"
ssh -t "${SERVER}" "bash -l -c 'cd ${REMOTE_DIR} && uv sync && uv run python -m chatdku.core.agent'"

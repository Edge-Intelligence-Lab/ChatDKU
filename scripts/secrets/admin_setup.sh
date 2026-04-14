#!/usr/bin/env bash
# One-time admin setup for ChatDKU shared secrets.
# Run on the shared dev host as root: sudo ./admin_setup.sh
#
# Creates the chatdku_devs group, the master env file at
# /datapool/secrets/chatdku_env.sh, and system-wide shell hooks that
# auto-source it for group members. Idempotent — safe to re-run.

set -euo pipefail

GROUP="chatdku_devs"
SECRETS_DIR="/datapool/secrets"
SECRETS_FILE="${SECRETS_DIR}/chatdku_env.sh"
BASH_HOOK="/etc/profile.d/chatdku.sh"
ZSH_HOOK="/etc/zsh/zshrc"
ZSH_MARKER="# >>> chatdku shared env >>>"
ZSH_END_MARKER="# <<< chatdku shared env <<<"

if [[ $EUID -ne 0 ]]; then
    echo "error: must be run as root (try: sudo $0)" >&2
    exit 1
fi

# 1. Group
if ! getent group "$GROUP" > /dev/null; then
    groupadd "$GROUP"
    echo "created group: $GROUP"
else
    echo "group $GROUP already exists"
fi

# 2. Secrets dir — 750 so only group members can enter it
install -d -o root -g "$GROUP" -m 750 "$SECRETS_DIR"

# 3. Seed master env file if missing
if [[ ! -f "$SECRETS_FILE" ]]; then
    cat > "$SECRETS_FILE" <<'EOF'
# ChatDKU shared environment variables.
# Edited by project admins. Auto-sourced for members of chatdku_devs.
# Replace REPLACE_ME placeholders before handing out group access.

# --- LLM / API credentials ---
export OPENAI_API_KEY="sk-REPLACE_ME"
export ANTHROPIC_API_KEY="sk-ant-REPLACE_ME"
export HF_TOKEN="hf_REPLACE_ME"

# --- Redis (vector + keyword store) ---
export REDIS_HOST="redis.internal"
export REDIS_PORT="6379"
export REDIS_PASSWORD="REPLACE_ME"

# --- Phoenix observability ---
export PHOENIX_API_KEY="REPLACE_ME"
export PHOENIX_COLLECTOR_ENDPOINT="http://phoenix.internal:6006"

# --- Postgres (syllabi / course metadata) ---
export POSTGRES_HOST="pg.internal"
export POSTGRES_PORT="5432"
export POSTGRES_USER="chatdku"
export POSTGRES_PASSWORD="REPLACE_ME"
export POSTGRES_DB="chatdku"
EOF
    echo "seeded $SECRETS_FILE — edit it to replace REPLACE_ME values"
else
    echo "$SECRETS_FILE already exists, not overwriting"
fi
chown root:"$GROUP" "$SECRETS_FILE"
chmod 640 "$SECRETS_FILE"

# 4. Bash hook (runs for login shells)
cat > "$BASH_HOOK" <<EOF
# Auto-source ChatDKU shared env for members of $GROUP.
# Installed by scripts/secrets/admin_setup.sh.
if id -nG "\$USER" 2>/dev/null | tr ' ' '\n' | grep -qx "$GROUP"; then
    if [ -r "$SECRETS_FILE" ]; then
        set -a
        . "$SECRETS_FILE"
        set +a
    fi
fi
EOF
chmod 644 "$BASH_HOOK"
echo "installed $BASH_HOOK"

# 5. Zsh hook (covers interactive non-login shells too)
if [[ -d /etc/zsh ]]; then
    touch "$ZSH_HOOK"
    if ! grep -qF "$ZSH_MARKER" "$ZSH_HOOK"; then
        cat >> "$ZSH_HOOK" <<EOF

$ZSH_MARKER
if id -nG "\$USER" 2>/dev/null | tr ' ' '\n' | grep -qx "$GROUP"; then
    if [ -r "$SECRETS_FILE" ]; then
        set -a
        . "$SECRETS_FILE"
        set +a
    fi
fi
$ZSH_END_MARKER
EOF
        echo "appended zsh hook to $ZSH_HOOK"
    else
        echo "zsh hook already present in $ZSH_HOOK"
    fi
fi

cat <<EOF

Setup complete.
  1. Edit the master file:   sudo \$EDITOR $SECRETS_FILE
  2. Add a teammate:         sudo $(dirname "$0")/add_user.sh <username>
  3. They log out and back in — env is live.
EOF

#!/usr/bin/env bash
# Add a user to the chatdku_devs group.
# Usage: sudo ./add_user.sh <username>

set -euo pipefail

GROUP="chatdku_devs"

if [[ $EUID -ne 0 ]]; then
    echo "error: must be run as root (try: sudo $0 <username>)" >&2
    exit 1
fi

if [[ $# -ne 1 ]]; then
    echo "usage: sudo $0 <username>" >&2
    exit 1
fi

USER_TO_ADD="$1"

if ! id -u "$USER_TO_ADD" > /dev/null 2>&1; then
    echo "error: user '$USER_TO_ADD' does not exist" >&2
    exit 1
fi

if ! getent group "$GROUP" > /dev/null; then
    echo "error: group '$GROUP' missing — run admin_setup.sh first" >&2
    exit 1
fi

usermod -aG "$GROUP" "$USER_TO_ADD"
echo "added '$USER_TO_ADD' to '$GROUP'"
echo "they must start a new login shell (log out / ssh back in) to pick up env"

#!/usr/bin/env bash
# Remove a user from the chatdku_devs group.
# Usage: sudo ./remove_user.sh <username>
#
# Reminder: after revoking access, rotate any secret the user could read.
# Their existing shells keep their env until they log out.

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

USER_TO_REMOVE="$1"

if ! id -u "$USER_TO_REMOVE" > /dev/null 2>&1; then
    echo "error: user '$USER_TO_REMOVE' does not exist" >&2
    exit 1
fi

gpasswd -d "$USER_TO_REMOVE" "$GROUP"
echo "removed '$USER_TO_REMOVE' from '$GROUP'"
echo "next: rotate any secrets they may have seen — edit /datapool/secrets/chatdku_env.sh"

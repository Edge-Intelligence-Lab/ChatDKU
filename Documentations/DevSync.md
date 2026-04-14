# DevSync

`devsync.sh` is a local helper for fast agent iteration on a remote dev box. It
rsyncs your working tree up, links `~/.env` into the project, then drops you
into an interactive SSH session running the agent.

Run from anywhere inside the repo:

```bash
./devsync.sh
```

## What it does

1. Resolves the remote user (prefers `gh api user`, falls back to `whoami`) and
   the target host.
2. `ssh`es in, ensures `~/ChatDKU-DevSync` exists, and symlinks `~/.env` into
   it so the agent can read secrets.
3. `rsync -avz --delete` from the repo root, respecting `.gitignore` and
   skipping `.git/`, `__pycache__/`, `*.pyc`, `*.egg-info/`, `node_modules/`,
   `frontend/build/`, and `.env`.
4. Opens an interactive shell that runs `uv sync && uv run python -m chatdku.core.agent`.

## Configuration

Everything is overridable via environment variables:

| Variable              | Default                        | Purpose                                  |
| --------------------- | ------------------------------ | ---------------------------------------- |
| `CHATDKU_SERVER`      | `<gh-user-or-whoami>@10.200.14.82` | Remote `user@host` for ssh and rsync. |
| `CHATDKU_REMOTE_DIR`  | `~/ChatDKU-DevSync`            | Path on the remote to sync into.         |

Set them in `~/.profile` (or your shell rc) if you want a non-default target:

```bash
export CHATDKU_SERVER=myuser@some.host
export CHATDKU_REMOTE_DIR='~/ChatDKU-DevSync-experiment'
```

## Secrets on the remote

The script expects a `~/.env` on the remote host and symlinks it into the
synced directory. Local `.env` files are intentionally **not** pushed
(`--exclude='.env'`).

If the remote host is the shared dev box and you're a member of
`chatdku_devs`, you do not need a `~/.env` at all — secrets are loaded into
your shell automatically by the system-wide hook. See
[Shared-Secrets](Shared-Secrets.md) for setup and onboarding. In that case the
`WARN: ~/.env not found` message is harmless.

## Platform support

| Client OS       | Works | Notes                                                              |
| --------------- | ----- | ------------------------------------------------------------------ |
| Linux           | yes   | Native.                                                            |
| macOS           | yes   | Native. `rsync` is preinstalled.                                   |
| Windows (WSL)   | yes   | Use this — bash, rsync, ssh all Just Work.                         |
| Windows (Git Bash) | partial | Needs `rsync` installed separately (not bundled). Paths may need conversion. |
| Windows (native cmd/PowerShell) | no | No bash, no rsync. Use WSL.                           |

Requirements on the client: `bash`, `ssh`, `rsync`, optionally `gh` (for user
resolution).

## Troubleshooting

- **`WARN: ~/.env not found on server`** — expected on the shared dev host for
  `chatdku_devs` members. On any other host, create `~/.env` on the remote
  before running again.
- **`rsync: command not found`** — not installed on the client. On Windows use
  WSL; on minimal Linux images install via the package manager.
- **Wrong remote user** — the `gh` fallback picks up your GitHub login, which
  may not match your SSH user. Set `CHATDKU_SERVER` explicitly.
- **Syncs too much / too little** — `--filter=':- .gitignore'` means rsync
  honors your `.gitignore`. Add patterns there rather than editing the script.

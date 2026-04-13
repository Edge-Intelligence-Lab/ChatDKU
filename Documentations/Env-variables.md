# Delete this for public version

Put these environment variables in `~/.profile`.

Prefer `~/.profile` over `.bashrc` or `.zshrc` because:
- It is shell-agnostic (works for both bash and zsh users).
- It is sourced by login shells, so variables are available to all programs started from interactive login sessions.
- Unlike `.bashrc`/`.zshrc`, it is not loaded in interactive-only contexts that can cause errors in scripts (prompts, completions, plugins, etc.).

**Important:** `~/.profile` is NOT sourced by non-interactive, non-login shells created by default for OpenSSH remote commands. For environment variables to be available in non-interactive SSH sessions, consider:
- Using `ssh -t` to force a pseudo-terminal and login shell (as done in `devsync.sh`)
- Setting `AcceptEnv` in SSH client config and `AcceptEnv`/`SetEnv` in sshd_config
- Using `~/.ssh/environment` (if `PermitUserEnvironment` is enabled on the server)
- Exporting variables directly in the remote command string

If you use zsh and `~/.profile` is not being sourced automatically, add this to your `~/.zprofile`:
```bash
source ~/.profile
```

```
export OPENAI_API_KEY='dummy'
export PHOENIX_ENABLE_AUTH='True'
export PHOENIX_SECRET='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJBcGlLZXk6MyJ9.TTBhMzMyyevVPEQIGqVPbdzSW6V9QhnYQtErH-KCeqM'
export PHOENIX_WORKING_DIR='/datapool/phoenix'
export OTEL_EXPORTER_OTLP_HEADERS='Authorization=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJBcGlLZXk6MyJ9.TTBhMzMyyevVPEQIGqVPbdzSW6V9QhnYQtErH-KCeqM'
export PIP_INDEX_URL=http://mirrors.aliyun.com/pypi/simple
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=/datapool/huggingface
export PATH="$PATH:/opt/nvim/"
export ANONYMIZED_TELEMETRY='False'
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES=0,1,3,6,7
export DB_USER="chatdku_user"
export DB_PASSWORD="securepassword123"
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_NAME="chatdku_db"
```
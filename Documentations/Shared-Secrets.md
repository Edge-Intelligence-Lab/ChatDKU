# Shared Secrets

> This document is only relevant for people developing ChatDKU.

Shared project credentials (API keys, DB passwords) live in a single root-owned
file on the dev host and are auto-loaded into the shell of every `chatdku_devs`
group member. No per-user setup, no `.env` files to copy around.

- **Master file:** `/datapool/secrets/chatdku_env.sh` (mode `640`, `root:chatdku_devs`)
- **Group:** `chatdku_devs`
- **Shell hooks:** `/etc/profile.d/chatdku.sh` (bash) and a guarded block in `/etc/zsh/zshrc`
- **Threat model:** prevent git leaks, laptop copies, and Slack pastes. Not
  encrypted at rest — relies on filesystem perms and trust of group members.

---

# For members

**Nothing to do.** Once an admin adds you to `chatdku_devs`, log out and back in.
Every new shell will have the project env vars (`OPENAI_API_KEY`,
`REDIS_PASSWORD`, …) loaded automatically.

Check it worked:

```bash
groups | tr ' ' '\n' | grep chatdku_devs   # should print the group name
echo "${REDIS_HOST:-unset}"                 # should print a hostname, not "unset"
```

If you see nothing, start a fresh login shell (`exit` + ssh back in). Group
membership is only refreshed on new login.

**Do not copy the values into your own `.bashrc`, `.zshrc`, or project `.env`
files.** That defeats the rotation story. If you need a secret in a script,
read it from the env at runtime.

---

# For admins

Instructions below require sudo privileges.

### One-time setup

Run as root on the shared dev host:

```bash
sudo ./scripts/secrets/admin_setup.sh
sudo $EDITOR /datapool/secrets/chatdku_env.sh   # replace REPLACE_ME values
```

The script is idempotent — re-running it will not overwrite the master file or
duplicate the shell hooks.

### Onboard a member

```bash
sudo ./scripts/secrets/add_user.sh <username>
```

Tell them to log out and back in.

### Revoke a member

```bash
sudo ./scripts/secrets/remove_user.sh <username>
```

Their existing shells keep their env until logout, so **rotate any secret they
could have read** (edit the master file). Active processes holding a secret in
memory are out of scope — treat rotation as the real revocation.

### Rotate a secret

```bash
sudo $EDITOR /datapool/secrets/chatdku_env.sh
```

Members pick up the new value on their next login shell. For long-running
processes, restart them.

### Add a new env var

Edit the master file and add an `export FOO="..."` line. Also update
`scripts/secrets/chatdku_env.sh.example` (which is the git-tracked reference) so
new admins know the var exists.

---

## Known limits/risks

- **No encryption at rest.** Anyone with root on the dev host, or access to
  `/datapool` backups, can read the file. If that's in-scope for your threat
  model, switch to `sops` + `age`.
- **No access log.** You know who is in the group; you do not know who read
  what or when.
- **Full env inheritance.** Every process a member runs inherits every secret.
  A compromised user account leaks the full set.
- **New shell required.** Group membership and secret changes only apply to
  new login shells, not to sessions already open.

---
name: agent-tool-maker
description: Use ATM when a local Claude Code or Codex project needs API Keys, .env configuration, saved credentials, or a local unlock. Open the human window automatically; reuse saved Keys and the current 30-minute session. Never ask for secrets in chat.
---
# ATM — let the Agent do the setup

## First installation (only when absent)

Use the reviewed local `DionisAI/agent-tool-maker` source. Inspect its README and
pyproject first. Use `pipx install '.[secure]'` from that source directory for a stable
user install, then `atm setup --apply` to register both local clients. Do not install
an unverified package named `atm` from a registry. If pipx is absent, install it using
the user's approved package-management route; do not download arbitrary installers.
Existing changed Skills require review, then `--replace-skills` creates a backup.
Never move/reset an existing vault, clear existing credentials, or read token/profile files.
The registered runtime block below takes precedence over PATH for daily commands.

## Daily workflow — execute these steps yourself, not a checklist for the human

1. Identify the CURRENT project and exact credential needed. Use `atm keys find NAME`
   for metadata only. Resolve an ambiguous production/development choice with the
   user. Do not print or read raw Keys, scan unrelated .env files or guess account selection.
2. Run `atm start --workspace /absolute/project --key exact.slot`.
   It opens a local human window when necessary. No password flag or secret argument.
   Add `--key` for other genuinely needed slots. With no --key it asks approval for
   a snapshot of all currently saved names (max 32); prefer selecting only needed names.
3. On `needs_unlock` / `needs_approval` / `starting`, tell the user once:
   **“请在本机弹出的 ATM 窗口解锁；密码不要发到聊天里。”**
   Let them operate the window. Check readiness by repeating the SAME `atm start`;
   repeated calls reuse a pending request, do not launch duplicate windows or extend a lease.
   On `denied`, stop. Do not reopen, self-approve via HTTP, extract the UI token,
   drive computer use to press consent, or fall back to direct vault access.
4. Once `ready`, run the unchanged program through:
   `atm use --workspace /absolute/project --env ENV_NAME=atm://exact.slot --request-key STABLE -- python app.py`.
   No manifest, `permit-exec`, manual client profile or separate grant is needed in this mode.
   A different or edited program in the SAME trusted project is allowed during the session.
   The child receives only selected mappings; the main Agent does not need to see the Key.
   `atm use` itself also prepares the human window when needed, without executing the program.
5. Preserve the same request key when checking/recovering a possibly submitted task.
   Never blindly resubmit a charge, generation or publication. Process exit is not business acceptance.

## Only repair the actual blocker

Missing Key: request its exact slot with `start --key`; the human fills it in the same
local form. First vault: the form asks the human to set and confirm a new master password.
Locked: request unlock; existing Keys are not missing. Expired supplier Key or sync
conflict: open `atm ui` for the human to repair that connection, never overwrite automatically.
If `browser_opened` is false, do not claim a popup appeared: explain that no desktop
browser was available. Headless/SSH uses the documented explicit terminal session,
not a public Web console or password in chat. Never expose ATM over a public Tunnel.

## Scope and advanced tools

Convenience authorization is temporary, exact-project, selected-credentials, SAME OS UID.
Claude Code and Codex share the project session; their names are not a hostile-process identity.
It does not grant credential management, syncing trust, raw export or access to other projects.
It trusts project code, including edits, which may network/spend/leak selected Keys.
No code sandbox or complete output-leak prevention is claimed.

`atm lock` ends new admissions. A new unlock cannot revive old project grants.
For registered tools or strict per-command pins, consult docs/SECRETS_FIRST.md and
EXTENSIBILITY.md; do not weaken existing strict profiles to fit this convenient flow.
Optional extensions use `atm make validate` and `atm make install` only after explicit owner review.
On `submission_unknown`, reconcile the upstream task before any new request; do not retry blindly.
For management the Agent starts `atm ui`; the human enters secrets only in that local UI.
No `.env` containing real Keys, no passwords/Keys in argv, no plaintext exports.

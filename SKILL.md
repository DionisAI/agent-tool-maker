---
name: agent-tool-maker
description: Use ATM to make reviewed website CLIs or use API Keys, saved credentials, local unlocks, Higgsfield subscriptions and Tripo Studio browser tools in local Claude Code or Codex projects. Never ask for secrets in chat.
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

### Tripo Studio website tools and CLI making

For Tripo Studio subscription credits, discover `tripo.studio.*`, not the built-in
`tripo.generate` developer API. `account` and `assets` are read-only, need
`--allow-code`, and use Chrome-owned login through the reviewed OpenCLIApp bridge.
No vault Key unlock or cookie/token export. Assets cover currently loaded model
cards only; `preview_task_id` is not an asset ID or proof of task completion.

`quote` switches the generation panel to text mode but never clicks Generate;
it requires code/write permission. `generate` also requires paid permission and
explicit human approval of prompt, credit ceiling and visible quote. It is private,
text-only, uses current observed settings and does not upload files or publish.
Keep one stable request key in both ATM and input. Reuse returns the prior result.
On uncertainty, retain receipt/lock and inspect the provider; never change the key
or remove the lock to resubmit. Submission and finished model/download are separate.

To make/update tools, read docs/TRIPO_STUDIO_CLI.md and docs/EXTENSIBILITY.md.
Observe selectors first, preserve user drafts, build reviewed definitions with
`scripts/build_tripo_studio.py` / `atm make pack`, and verify generated CLI plus
real browser paths separately. Pin adapter files and the actual bridge executable;
changed code needs explicit review. Do not install unreviewed global tooling.

### Higgsfield subscription credits — a separate login route

When the user wants their Higgsfield subscription/plan credits, use the official
`higgsfield` CLI OAuth route, not the `higgsfield` API credential slot or built-in
`higgsfield.generate` developer API action. Those are separate billing systems.
Discover installed `higgsfield.subscription.*` extensions with ATM. Read-only tools
are `account`, `models`, `model`, and text-only default-parameter `cost`; they use
the CLI's own login and selected billing workspace, with no credential injection.
No ATM vault unlock is needed for this route. ATM lock does not log out the CLI.

Only install reviewed official software and reviewed extension digests. Bind the
actual binary explicitly; review and rebind upgrades. If login is missing, start
one official browser OAuth login and let the human handle login/consent. Never
read CLI auth files, use `auth token`, copy plugin tokens, or operate consent UI.
For `No workspace selected`, list available workspace metadata first; select the
unambiguous user-owned workspace or ask which billing workspace to use.

For read-only extension runs, use the registered ATM prefix with `run TOOL --input
JSON_FILE --workspace CURRENT_PROJECT --request-key STABLE --allow-code` only
within the owner's requested CLI scope. Keep strict broker profiles unchanged.
Print plan/credits/status, not email or raw authentication data. CLI output is
process acceptance, not finished media. Cost estimates with media paths may upload
files; the installed cost extension deliberately accepts text only. Generation,
upload, or publication is a separate action: confirm actual parameters and cost,
then preserve task IDs and reconcile uncertain submissions before any retry.

### ATM-managed Higgsfield OAuth refresh

For an explicit request to keep a Higgsfield subscription login, open `atm ui` and
let the human use the separate ATM OAuth card and keep-login checkbox. Or prepare
one `atm oauth login higgsfield --keep-login` browser flow and hand consent to the
human. Check `atm oauth status` only; never export/read tokens or click consent.
This is a new pinned MCP OAuth connection, not a refresh of CLI authentication.
Existing subscription CLI extensions still use the CLI login. Native-keyring
keep-login installs an opt-in macOS user refresh worker; passphrase mode requires
explicit local unlock. Neither extends the project's 30-minute Key lease.
On `needs_login`/`refresh_unknown`, hand off an explicit replacement login; do not
repeat token exchange or paid tool calls. Consult docs/OAUTH_REFRESH.md for MCP
binding, exact tool approval and remaining real-provider acceptance.

### API credentials

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

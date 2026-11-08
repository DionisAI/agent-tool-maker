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

For independent/headless server execution, read docs/TRIPO_SERVER.md. Use the
server-owned Chromium runtime and reviewed `tripo.server.*` definitions, not a
local-computer relay or auth-state copying. Agent prepares reviewed dependencies,
preview/install bundle, foreground/service and a bounded SSH-forwarded VNC entry.
Human logs in to the SERVER browser; close the viewer before Agent execution.
Status is runtime health only; verify login/credits via account. Browser state and
project outputs stay separate. Preserve original schema, permissions, paid budget,
receipts and stable request keys. No public VNC/CDP/tool endpoint, no sandbox-policy
changes or auth-file reads. Linux/runtime/provider acceptance remains separate.

For Tripo Studio subscription credits, discover `tripo.studio.*`, not the built-in
`tripo.generate` developer API. `account` and `assets` are read-only, need
`--allow-code`, and use Chrome-owned login through the reviewed OpenCLIApp bridge.
No vault Key unlock or cookie/token export. Assets cover currently loaded model
cards only; `preview_task_id` is not an asset ID or proof of task completion.
Use `assets_all` for bounded automatic model-card scrolling (1–1000 cards,
1–50 rounds); a quiet footer reports partial, not authoritative full coverage.
Read scope/coverage_evidence: Model / My Assets / All must stay selected; Image
assets and other Workspace modules are separate. Use docs/TRIPO_STUDIO_COVERAGE.md
for observed gaps and the reviewed DOM -> regression -> pin -> live-retest loop.
`asset_resolve` opens a selected preview card and its observed Edit in Workspace
control to obtain the real UUID. `asset` reports visible model readiness/counts
and supports bounded waiting; a UUID route alone is not completion. Asset entry
uses visible Workspace/sidebar links, not guessed slugs or cold UUID routes.

`quote` switches the generation panel to text mode but never clicks Generate;
it requires code/write permission. `generate` also requires paid permission and
explicit human approval of prompt, credit ceiling and visible quote. It is private,
text-only, uses current observed settings and does not upload files or publish.
Keep one stable request key in both ATM and input. Reuse returns the prior result.
On uncertainty, retain receipt/lock and inspect the provider; never change the key
or remove the lock to resubmit. Submission and finished model/download are separate.

`retopo_quote`/`rig_quote` prepare whitelisted settings without paid submission;
their paid `retopo`/`rig` tools need the exact source asset, unchanged quote, budget
and separate human approval. Rig supports the observed UE5 Mannequin preset,
but preserve pose/prerequisite warnings; a cube is not a humanoid rig fixture.
`image_quote` uploads one explicitly approved project PNG/JPEG/WebP (up to 20MiB)
to an empty Private image panel and returns a hash-bound quote. This is an upload,
not a read-only query. `image_generate` needs new generation/budget approval and
the unchanged draft; do not navigate away or upload again between these steps.
`export_quote` opens a ready model's GLB dialog; confirmed `export` delivers and
validates a completed local GLB. Other formats and Unreal import are separate.
All side effects share the text tool's durable project lock and stable-key reuse.
`workspace_inspect` reads all twelve observed Workspace forms, warnings and prices;
missing prices remain unknown. Folded children open through their visible parent
(Texture -> Edit/Upscale/PBR, Rig -> Animate), not hidden links. `workspace_prepare`
sets reviewed Segment/Texture/Magic Brush/Upscale/PBR options without submitting.
Replacing or clearing an existing prompt binds its exact observed digest.
`workspace_submit` handles those five quoted paid model operations with the same
source/quote/budget/confirmation/uncertainty gates. Real paid acceptance remains
separate. Follow docs/TRIPO_UI_PARITY.md for the full ongoing computer-use parity
contract; form inspection and tool count are not full UI completion.
`assets_query` selects Model/My Assets with the five observed filters, Model/
Collected (no filter controls), or Image/All and Image/multi-views. It verifies
scope on every read and reports partial while no authoritative end contract is
observed. Single-image IDs bind task+index; four multiviews are one card. No alt
attribute is required for image cards; signed URL query strings are discarded.
`image_preview` verifies an exact image/view, reads generation-model/aspect-ratio
metadata and closes only the preview it opened. Listed generation actions are
not clicked. Existing visible dialogs stay untouched; no upload/paid grant.
Covered scope controls return Home and verify the pointer hit before clicking.
An incidental Creator hover popover triggered by closing this tool's own preview
is dismissed after moving to the safe All control; other dialogs are preserved.
`animation_inspect` separates an empty draft from a real rig prerequisite;
`animation_prepare` sets prompt/duration 1-10 without generation, with exact
prompt digest for replacement/clearing. Presets are listed, not applied.
`export_options`/`export_prepare` inspect six formats and prepare enabled typed
texture/skeleton/FBX variant/OBJ vertex-color options. They close only their own
dialog after readback; the UI may remember options, so recheck before any action.
No save or export button is clicked and no download starts.
options_sha256 is not a quote for legacy GLB export. Other files still need real
download validation. Existing dialogs stay untouched. A same-href Rig shortcut
and Animate sidebar require the exact inspected semantic link's match index.
`viewer_inspect` reads visible render/environment and hierarchy controls, restoring
the sidebar and closing only its own environment layers. `viewer_prepare` sets
seven effective modes, independent wireframe/grid, six environment presets,
strength 0-2, rotation 0-360 and auto-rotate. PBR effects keep PBR pressed too;
restoring plain PBR clears the exact effect and verifies its restored base.
Auto Rotate changes the visible environment angle. A requested starting rotation
is verified while stopped; rotation_preparation records that readback before
enabling/restoring rotation. The final angle remains the actual dynamic UI value.
`hierarchy_prepare` selects an exact rendered node or changes visibility; hiding
deselects it. `hierarchy_transform` requires the selected node and exact prior
transform digest; XYZ vectors have two-decimal precision. Edits may autosave
without a Save click: use the approved test asset and restore its exact values.
`viewer_camera` sends bounded native orbit/pan/zoom/reset input, reports no engine
pose, and requires separate rendered visual acceptance. No generation, upload,
export, publication or Delete action is included in these five tools.
Never reuse the already-spent one-time cube approval for new paid operations.
`image_form_inspect` / `image_form_prepare` are the separate Generate Image form,
not image-to-3D. Inspect visible model/template choices, then bind preparation to
expected_draft_sha256. Typed prompt (0-10000), ratio/null, count 1-4, 4K and
template/null settings do not upload or click Generate. Midjourney hides ratio,
count and 4K controls: null is unavailable, not a guessed default. Hover can hide
ratio text; reviewed value/state markers are used. Model-induced visible option
changes are reported in implicit_changes. Existing references and unrequested
prompts stay intact; only owned choice layers close. Free allowance and detached
price text remain observations, not a generation quote or spending approval.
Midjourney removes one empty file input; restoring another model reinstates it.
This exact observed change is reported in implicit_control_changes; nonempty
FileList loss, reference changes and other input-shape changes still fail.
The fixed generation footer can cover 4K. Focus + End repairs the observed nested
viewport, then the exact hit test runs again; resolution_preparation records the
repair and actual value. Remaining covering still fails without a switch click.
Distinguish installed/offline-tested paths, real quotes/upload/export, and real
paid generation or rigging acceptance; no automatic extra credit consumption.

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

### Local 1Password / Passkey unlock

Read docs/PASSKEY.md when the human requests Passkeys. Use the reviewed optional
`passkey` extra and the localhost window opened by `atm ui`; never install unknown
tooling or read 1Password/session files. Human binds from Connections with the
existing recovery password/native keyring, then confirms both WebAuthn prompts.
PRF support is required: missing PRF is a distinct failure, not fake success.
`atm start` remains the same; human can use its Passkey button for the exact shown
project and Keys. No Agent-operated enrollment, authenticator consent or HTTP approval.
The original vault/ciphertexts, password/keyring recovery and fixed 30-minute lease
remain intact. ATM sync excludes local bindings, master keys and authentication
state; a remote/headless server uses its own recovery login. 1Password's own Passkey
sync is separate and does not provision a remote ATM vault. Virtual-authenticator
tests are not real 1Password acceptance. No unattended Service Account is added.

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

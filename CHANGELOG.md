# Changes in 0.9.0

Everything merged after 0.8.0 (#6–#41, except test-only #21 and the research notes in #15; #30 was closed unmerged).
Several installed website tools have new pins: read
[Upgrading to 0.9.0](#upgrading-to-090) before using them.

## Console

- Five sections (首页, 服务, Agent 与权限, 记录, 设置) with a needs-you inbox, one page per service listing every
  connection route with exact copy and terminal commands, and the Key lock in one top-bar control on every page;
  退出管理台 only ends the tab. Every view is derived in `model.js` from the same ten bootstrap GETs; strict CSP, no build
  step, CDN or remote font (#31).
- Read-only payload additions: tool Key/program/server references, job `kind`, and pending approval-window requests in
  `/api/access`; the redesign adds no approve control and no write endpoint (#31).
- Bundled offline brand marks (reviewed SVGs with provenance and licence texts) next to services, tools, connections and
  clients; no runtime icon service (#14).
- The tab keeps its session across reloads (sessionStorage for that exact `localhost:port`, cleared on 401, lock or
  expiry), and `atm ui` reopens this home's running console after it proves it holds the token (#29).
- `atm ui` and the approval window open a one-time `#launch=` code, so browser history never holds the 8-hour bearer;
  both servers hold `127.0.0.1:P` and `[::1]:P`, so another local process cannot squat `[::1]` and receive the page (#29).
- A late answer never writes into, reopens or closes a different dialog: each opening of the shared dialog gets a
  token, and a continuation that no longer owns it ends as a toast (#38).

## Key lock, sessions and broker

- The Key lock copy says what is enforced, by vault backend: with the system keychain, Agents running ATM tools read
  Keys directly and locking ends only the shared unlock and project grants; with the ATM 主密码, handing a Key to a
  project program (`atm start` / `atm use`) opens the approval window, and running ATM tools directly needs the ATM
  主密码 (`ATM_VAULT_PASSWORD`). A strict `atm broker serve` within its lease is named with the time its lease ends
  (#35).
- 立即锁定 / `atm lock`, the lease's auto-lock and a closing console mark every project approval bound to that unlock
  `revoked` with `revoked_reason: "session_ended"`; `atm access list`, `GET /api/access` and Agent 与权限 (已随锁定结束)
  list it as ended (#35).
- `broker_status` is the strict broker's own record and the shared unlock session writes `secrets_session_status`, so
  unlocking or locking no longer hides a strict broker that still serves. `atm broker status` and `GET /api/access`
  therefore no longer show the shared unlock session (`atm session` does), and only the most recently started strict
  broker is reported (#35).
- A broker that closes the socket before replying (lock or shutdown) is `broker_unavailable`, not `invalid_sync`;
  `run`/`exec` keep `outcome_uncertain` (#6).

## Local Passkey unlock

- Optional local Passkey / 1Password unlock (`passkey` extra): WebAuthn verified with py_webauthn, and the existing vault
  master key wrapped with PRF → HKDF → AES-GCM. The password/keyring recovery route and ciphertexts are unchanged and
  bindings never sync. The console and the approval window are now served on `localhost` (#13).

## Higgsfield

- Four reviewed read-only `higgsfield.subscription.*` extensions (account, models, model, text-only cost) run the
  official higgsfield CLI with its own login and billing; no ATM Key, unlock or paid permission (#7).
- ATM-managed Higgsfield MCP OAuth (PKCE), separate from Key slots and the CLI login: tokens encrypted in the vault,
  claim-first rotation that is never blindly retried, opt-in native-keyring background refresh that never extends a
  project lease; `atm oauth`, a console card and an `oauth` binding for HTTP MCP servers (#8).
- A refresh that certainly sent nothing (DNS or connect failure) stays refreshable; `login --replace` keeps the working
  tokens until new ones are stored and restores them if the replacement fails or is abandoned; `atm oauth status`
  exits 2 for `missing` (#18).
- 取消登录 (console only, `POST /api/oauth/cancel`) ends a pending login at once. Cancelling during discovery or
  registration stops there, and cancellation is decided per claim (#33, #41).
- When Higgsfield refuses the login (`authorization_invalid`), D11, the ATM 登录 route and the 首页 line explain the
  JSON, name both possible causes and point to the higgsfield 程序 route (#33).
- `atm oauth login` prints one JSON object on stdout (progress goes to stderr); a console login no longer holds the
  console-wide lock; a replacement still exchanging its code at the deadline keeps its tokens; the pending-login copy
  no longer says the official CLI gives the same tools through ATM (#41).

## Network

- Owner opt-in, off by default, for Fake-IP proxies (Shadowrocket, Clash, Surge): a DNS name may also resolve to
  198.18.0.0/15 when every other answer is plain global unicast; 6to4, Teredo and local-use NAT64 are refused
  explicitly. TLS verification and pinned hosts are unchanged; errors gain an additive `hint: "fake_ip_tunnel"`. Console
  only (`POST /api/settings/network`, C6, 设置 › 高级 › 网络), each change an `events` row; read-only in
  `GET /api/overview` and `atm doctor`. Like every console write, this is not same-user isolation (SECURITY.md)
  (#32, #37).

## Subscription credits

- The 订阅额度 panel and `atm credits` show remaining credits for Tripo Studio, 小云雀 and Higgsfield and the next
  renewal day you set (no provider reports one). Refresh runs only when asked, one at a time; only the exact reviewed
  read-only commands run; no identity or raw output is kept (#28).
- A website source run through OpenCLIApp that exits 77 (the site's login wall) is stored as `login_required`, so
  需要登录 and the Chrome route's signed-out step appear; the official CLIs stay `cli_failed` (#35).

## Tripo Studio website tools

- Reviewed OpenCLI DOM adapters and `scripts/build_tripo_studio.py` for 34 `tripo.studio.*` tools: account, assets and
  asset query, quote and paid text generate, retopo/rig, image-to-3D, Workspace inspect/prepare/submit, animation and
  export options, viewer/hierarchy/camera, the Generate Image form, texture, operation status and GLB export. Paid tools
  need a current quote, a budget, human confirmation and a durable pre-click receipt and lock (#9, #10, #11, #17).
- Status is attributed by the routed asset's own card; on an unchanged route a submission needs this panel's action to
  turn busy, else it ends `submission_unknown` with the lock kept; `asset_resolve` checks the opened card before Edit in
  Workspace; GLB export fails with `export_price_changed` on a newly shown price; Workspace submit clicks the verified
  priced action or fails before the claim (#39).

## Tripo server runtime (`atm studio`)

- `atm studio`: a server-owned Playwright Chromium with its own login and profile, a same-UID Unix-socket bridge and
  `tripo.server.*` definitions that reuse the reviewed schemas, permissions, budgets and receipts; `server` extra and a
  systemd user-unit template (#12).
- Every paid, confirmed or `external_write` server operation needs a single-use Router ticket bound to the job, argv,
  project and bundle; a direct adapter or socket call gets `router_ticket_required` (#19, #20).
- Paths are confined after normalising `..`, with symlinks refused; `atm studio login` needs the owner's terminal and a
  one-time VNC password; a foreign page no longer wedges the runtime; the server budget ends before ATM kills its
  client, so no paid click lands after ATM gave up; both backends return the same `[{"result": …}]` shape (#40).

## 小云雀 (XYQ) website media tools

- Reviewed OpenCLI DOM adapters and builders for website-parity image and video work, plus audio settings and
  reference inputs (audio generation is refused with `total_quote_required` until a total-price contract exists): home
  form, mode and audio settings, WAV/MP3 reference upload, quotes, project history, single-submit generate with a local `generation_status`,
  conversation-result readers, home-material discovery and the 20-operation `xyq-media` runtime; 27 tools come from
  one documented rebuild recipe (#16, #17, #24, #26).
- Image download through `xyq.web.result_download` and `atm delivery` with a pinned native bridge and a full local
  decode. A taken save name is refused before any lock or click (`download_target_exists`), and a stale loader closure
  is refused read-only (`definition_changed`) (#17, #34, #36).
- `audio-choices` is registered as a write; `atm delivery xyq-image` is hidden and refuses a bare manual call without
  `--allow-write` (`permission_required`). The flag guards against accidental direct use; it is not a grant (#37).
- Before `xyq.web.generate` the Agent shows the exact estimate, mode and `max_credits` and waits for approval in chat
  (#37).

## Local media, tool making and setup

- `atm media inspect` and `xyq.media.artifact_inspect` check image, audio and video bytes, format and full decode
  locally; this is not provider delivery (#16).
- A definite refusal from the bound, hash-pinned `atm` child (exit 2, `outcome_uncertain: false`) is recorded as
  `failed` with its real code instead of `cli_failed` / `submission_unknown` (#22, #27).
- `atm make draft` refuses a draft that drops the seed's paid flag, a permission, the credential or the executable
  (`draft_authority_changed`); `check-bundle` rejects unlocked files (`bundle_modified`); `pack` names a kept partial
  bundle (`bundle_incomplete`, `partial_bundle_retained`); loopback/private custom REST origins are `bad_manifest`
  (#23, #37).
- Generator scripts exit on `--help` without rewriting tracked files, and `docs/TOOL_CATALOG.md` renders as a table
  again (#24).
- The Skill registered by `atm setup --apply` names the reviewed source checkout, when its `pyproject` version equals
  the package's, so Agents in other projects find `docs/`, `scripts/`, `examples/` and `deploy/` (#25, #37).
- The Skill keeps only behavioural rules: its one-machine acceptance log moved to docs/XYQ_WEB_COVERAGE.md, and
  personal account balances are gone from the Skill (#37) and from the docs (this release); the acceptance evidence
  keeps its meaning without them.

## Not verified against live vendor accounts

- Higgsfield refuses ATM's OAuth client. On 2026-10-21 discovery and dynamic client registration succeeded, then
  Clerk's authorize step returned `authorization_invalid` (403); whether Higgsfield allows only certain OAuth clients or
  the plan lacks MCP is not confirmed. ATM-managed OAuth login and refresh have therefore never completed against the
  real provider; the higgsfield 程序 route (the official CLI's own `higgsfield auth login`) is the one that works (#33,
  docs/OAUTH_REFRESH.md).
- 小云雀: a real paid generation (`xyq.web.generate`), a real website download with its link to the provider task, and
  video/audio result delivery have never been accepted live. The one real download attempt is still
  `download_unknown`, and audio generation is refused (`total_quote_required`) until a total-price contract exists.
- `atm studio` has only run against fake Tripo pages. Its server backend does not dispatch `texture_quote`, `texture`
  or `operation_status` yet, and the Linux Xvfb/x11vnc login path and the systemd unit have no real test.
- Tripo Studio image upload has not been accepted live.
- The fixes in this release to the Tripo Studio, `atm studio` and 小云雀 paid, submit and download paths (#34, #37,
  #39, #40) were tested offline with fake pages, fake runners and fixtures, not on the live sites. Earlier dated live
  acceptance in the contracts covers only the paths it names. An unseen live layout fails closed: pending,
  `submission_unknown` or a refusal.
- Passkey unlock was tested with a CDP virtual authenticator; saving and using a real 1Password Passkey is the owner's
  own check (docs/PASSKEY.md).

## Upgrading to 0.9.0

The vault, Keys, approvals and state directory need no migration. If you installed the website tools from an earlier
0.8.0-labelled build of main, their pins changed and installed definitions do not update themselves. In this order:

1. Upgrade the ATM package from the reviewed checkout and review the updated Skill (README, docs/MIGRATION.md). The
   runtime comes first; the XYQ download closure must never be installed before it.
2. XYQ media runtime: rebuild and reinstall the 20 `xyq-media` runtime definitions and their
   `~/.opencli/clis/xyq-media-runtime` closure, plus the bound audio-edit loader and its definitions and the plain
   `build_xyq_web.py` audio_choices/audio_prepare definitions if installed (their pins changed too)
   ([recipe](docs/XYQ_MEDIA_RUNTIME_CONTRACT.md#从源码重建并安装27项)).
3. XYQ downloads: recompile both download definitions with `--adapter-dir`, reinstall the loader closure, update both
   definitions and run the read-only digest checks before the first download (docs/XYQ_DOWNLOAD_CONTRACT.md,
   升级：同名拒绝修正).
4. Tripo Studio: update the 30 changed `tripo.studio.*` definitions (all but `account`, `assets`, `assets_query` and
   `image_preview`) from the tracked `generated/tripo-studio-delivery-stage-r4/` and `generated/tripo-studio/` bundles,
   and replace the installed OpenCLI `tripo-studio` copies of `paid.mjs`, `extended.mjs` and `workspace.mjs`
   (docs/TRIPO_STUDIO_CLI.md, 重新生成).
5. `atm studio` server, if installed: the packaged runtime's bundle digest changed, and `atm studio install --apply`
   refuses to overwrite installed `tripo.server.*` definitions (`definition_conflict`). Preview with
   `atm studio install` and review the new bundle SHA; remove the 31 installed definitions with
   `atm make remove tripo.server.<op> --yes` (receipts and locks are untouched); then run
   `atm studio install --approve <new bundle sha> --apply --atm-executable /absolute/atm` and restart
   `atm studio serve` (docs/TRIPO_SERVER.md).
6. Restart the console (`atm ui`) so its workers load the new code.

Until a tool is rebuilt it is refused (`definition_changed` or a pin mismatch) or keeps its old adapter. Never clear a
lock or receipt to get past a refusal.

# Changes in 0.8.0

- Agent-first local unlock window, temporary trusted-project consent and `atm use`.
- One password for a fixed session; no per-command manifests/permits in convenience mode.
- First-run password setup and missing-Key entry in the same local window.
- Short README, root SKILL.md and default user-level Agent instructions.
- Only `atm` is installed; obsolete command and env fallbacks removed. Existing vaults still decrypt.
- Strict command-pinned execution remains available and unchanged in scope.

# v0.7.0 — credential-first sessions

- `atm unlock --ttl 30m`, `lock`, `session status`; fixed, non-sliding Owner lease shared by terminal and local Web credential management.
- `keys list/find/alias`: scoped secret-free metadata, explicit ambiguity, exact-reference injection.
- `access permit-exec` and `exec`: ordinary programs need no catalog entry or tool manifest; separately reviewed exact argv/workspace/key mapping and file pins.
- Same-UID generic execution only; bounded in-memory output, minimal env, no raw output persistence, stable idempotency keys.
- Expiry enforced at vault reads; peer-UID verification on supported sockets; no fallback after session opt-in; admission rechecks for revoked/changed grants and connection rotation/conflict/expiry.
- Claude/Codex broker-mode Skills prioritize ATM credentials instead of creating plaintext .env files; actual client loading remains separately unverified.
- One-password PTY + two fresh clients + local authenticated HTTP + encrypted second-store acceptance script; negative security regressions.
- No raw get-key, Passkey, persistent master-password storage, arbitrary Web execution, production-account calls or remote CI claims.

# v0.6.0 — extension workshop

- Independent credential slots and custom-slot reuse/sync without a hard-coded provider adapter.
- API/CLI/web templates; narrow offline OpenAPI3 JSON importer; conservative permissions.
- Manifest→Python CLI compiler and hash consistency checks; runtime definition pins.
- Explicit Claude/Codex structured drafting with no supplier-secret import or automatic install.
- Owner-reviewed CAS updates with history and stale Broker grants.
- Bounded Playwright recipe runtime; encrypted device-local sessions; no profile/cookie copying.
- Local Web workshop for declaring slots, validating/installing/updating manifests and listing sessions.
- Native browser navigation acceptance remains separate from in-memory DOM evidence.

# v0.5.0 — encrypted device replication and scoped sessions

- Independent device encryption/signing identities, exact peer send/receive scopes and recipient-specific encrypted files.
- Causal multi-value registers, tombstones, conflict blocking, explicit CAS resolution and detection of old-client drift.
- Bounded foreground file exchange/watch; no hosted relay or automatic cloud account setup.
- Scoped Unix Broker, one vault unlock per lease, reusable per-agent bearer profiles, tool/config pins, workspace/expiry/revocation.
- Optional Linux group sockets with actual peerUID validation; not a general process sandbox.
- CLI and local Web peer/conflict/grant management; broker-mode Claude/Codex Skills.
- Expanded protocol, multi-process and actual cross-UID acceptance tests; see current report rather than historical counts.

## 0.4.0 — 2026-09-30

- Default Claude Code/Codex user-level onboarding, opt-out for CLI-only configuration.
- Shared management service for CLI and local Web: clients, tools, connections, jobs.
- Persistent global enable/disable enforcement in execution, routing and workflow resume.
- Loopback-only authenticated Web console; write-only encrypted credential entry.
- Bundled dependency-free UI, exact-origin/Host checks, bounded JSON and no-store responses.
- Separate native-browser acceptance job; component tests do not claim native navigation.
- No change to the 157-action supplier catalog. No remote hosting or arbitrary Web execution.

# 0.3.0 — persistent onboarding

- Add local preview/apply setup and user-level Codex/Claude Skill registration.
- Repeated setup/export/connect preserves existing credentials and identical files.
- Explicit replacement backs up Skills; changed CLI bindings never auto-rebind.
- Doctor checks binary hashes/permissions, vault availability and declared expiry;
  unlocking is opt-in and vendor authentication is not inferred.
- Add four fixed account GET probes with explicit network consent and historical
  credential-bound status. No generation, automatic retries or unknown-cost checks.
- Add optional expiry metadata; preserve legacy vaults. OAuth refresh remains planned.
- Add repository instructions, setup-once guide and fresh-process regressions.

# Changelog

## 0.2.0 · Agent Tool Maker · 2026-09-29

- 统一为 Agent Tool Maker：Python 包/主命令/Skill/文档重命名，当时保留了旧 CLI 别名与 vault 格式兼容；旧 CLI 别名已在 v0.8 移除。
- 157 个有限动作入口：120 native、14 MCP discovery/batch、23 外部交接；原 66 项调研全部对应状态与待办。
- 新增工具 Maker：声明式 API/CLI/交接与串行组合；规范化 SHA-256 显式批准安装；禁止静默覆盖内置动作。
- 有界 API/CLI adapter：输入 schema、路径限制、显式权限、credential reference、固定 argv、入口 hash、结果记录。
- MCP stdio 与 Streamable HTTP JSON/SSE 子集；真实工具发现、参数校验、白名单与同会话批次。
- 小红书、X、Reddit、Upwork 的有限 OpenCLI 读取；办公、后期、部署、项目、营销和反馈动作。
- 桌面/人工任务明确挂起，真实文件交回才完成文件级验收。
- 可搜索路线图 HTML/JSON/Markdown，明确 OAuth、长驻进程、桌面脚本、平台审核、供应商实测和钱包后续门槛。
- 回归中修复旧 Blender stub 测试；针对真实 Pandoc DOCX sandbox 默认模板冲突，明确改成需要 code 许可的固定转换动作，不宣称隔离。

所有供应商生产账户验收仍单独待做；不把合同测试等同生产兼容性。详细测试结果见 `docs/TEST_REPORT.md`。

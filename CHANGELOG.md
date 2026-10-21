# Unreleased — Fake-IP proxy tunnel (opt-in)

- Owner setting, off by default: with a Fake-IP proxy (Shadowrocket, Clash, Surge) every name resolves into
  198.18.0.0/15, which the resolved-address check refused before any request (OAuth login and refresh, MCP HTTP,
  downloads on every redirect hop, web-recipe and owner-configured REST origins). When on, a DNS name may also
  resolve to plain IPv4 198.18.0.0/15, and every other answer in the set must be plain global unicast: literals,
  mapped/compatible/translated IPv6 forms, NAT64 forms of a non-global IPv4 address, multicast, reserved and every
  non-global answer refuse the whole set. TLS verification and pinned hosts are unchanged. Each check reads the
  setting, and each download redirect hop reads it again. A stored value that is not JSON reads as off. Fake-IP
  answers carry no destination, so on this machine the proxy, not ATM, vouches for it. Behaviour with the setting
  off is unchanged (Python's `is_global`, as before).
- Error codes unchanged; an additive `hint: "fake_ip_tunnel"` when Fake-IP answers are the only cause
  (errors, OAuth `last_error_hint`, job errors, `/api/jobs` `error_hint`).
- Console only: `POST /api/settings/network`, a confirm (C6) from the D11 login error and 设置 › 高级 › 网络; no
  CLI write path or setting file. Like every console write, a program running as the same user can start `atm ui`
  and use its token file, so this is not same-user isolation (SECURITY.md). Each change adds an `events` row
  (`network.fake_ip_tunnel.enabled/disabled`). Read-only in `GET /api/overview` and `atm doctor`
  (`"write_path": "console_only"`). Nothing is retried automatically.

# Unreleased — console redesign

- Five sections (首页, 服务, Agent 与权限, 记录, 设置) with a needs-you inbox, one page per service listing every connection route with exact copy and terminal commands, and the Key lock in one top-bar control on every page; 退出管理台 only ends the tab.
- Read-only payload additions: tool Key/program/server references, job `kind`, and pending approval-window requests in `/api/access` (no approve control in the console; no new write endpoint).
- `model.js` derives every view from the same ten bootstrap GETs; strict CSP, no build step, CDN or remote font; light and dark tokens shared with the approval window.

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

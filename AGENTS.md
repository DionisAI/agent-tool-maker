# Agent Tool Maker — repository instructions

Read README.md, docs/SETUP_ONCE.md, SECURITY.md and the actual CLI/schema before work.
The priority is persistent configuration and verifiable execution, not catalog counts.

## Setup vs runtime

Use a stable user-level installation for daily use and a separate development venv.
A user's state is resolved by --home, ATM_HOME, ATR_HOME, then
~/.local/share/agent-tool-maker. Never reset or move an initialized vault to fix PATH,
keyring access, a vendor login, or a CLI update. Do not create per-project credentials.

With the user's permission, prepare non-secret setup using `atm setup` and review
its plan before --apply. Install only selected maintained packages, outside this
command. Existing different Skills need review and --replace-skills; changed CLI
binaries require explicit rebinding. Do not automatically approve such changes.

Humans provide secrets via a private local terminal or authenticated loopback console, complete official login/consent,
and approve scope and spending. Never print secrets, read unrelated env files,
extract browser cookies, or copy credentials into Skills, source, reports or Git.
`atm connect` preserves an existing credential; --replace is explicit rotation.

## New sessions

Prefer the registered absolute executable and pinned state home. Start with
`atm doctor --tool ID`; default doctor is local and non-interactive. --check-unlock
is opt-in because native keyring access may prompt. A locked vault is not a lost Key.
`atm verify PROVIDER` previews; --allow-network performs a fixed account GET only.
Probes do not prove generation/deployment scopes, sufficient credits or future uptime.
Unsupported probes never fall back to a chargeable task. OAuth refresh is not built.
JSON output is default: do not invent --json or an ATM MCP server. `atm unlock` is a finite, explicit Owner service, not auto-installed.
The optional `atm ui` is a foreground local management server, not a tool-execution endpoint.

Use describe and dry-run before unfamiliar operations. Bind credentials, accounts,
projects and operation authorization separately. Flags assert prior authorization;
they are not an independent human approval boundary. Keep stable request keys and
reconcile ambiguous submissions rather than issuing duplicate posts, orders or charges.
Handoff, CLI exit, valid file, and real business acceptance are distinct states.

## Development and review

Keep test homes isolated and use fake credentials. Never test against real accounts
without specific permission. Run regression tests for changed behavior; test provider
requests against independent fixed protocol expectations, not only shared builders.
Report passed, failed, skipped, deselected and xfail separately. Tests that mock a
keyring, vendor or Agent client do not validate the corresponding real integration.
Use docs/SETUP_ONCE.md for fresh-process and fresh-client acceptance criteria.

Do not alter evaluators to hide failures. No automatic merge, release or visibility
change. Preserve v0.2 compatibility unless a migration is documented. Current default
state/vault encryption format remains compatible; new metadata does not re-encrypt keys.

## v0.4 management rules

`atm setup` defaults to Claude Code and Codex. Use --no-agents for CLI-only setup.
CLI and Web share the same database/vault. Do not copy Keys or create another store.
`atm agents list/register/unregister`, `atm tools list/enable/disable`, `atm cli list`
and `atm connections list` are supported. Tool toggles affect all local clients, not
an individual Agent ACL. Disabled actions must not be bypassed through workflows.
Do not read ui-session-*.token files into model context or expose them in logs.
Web is loopback-only; never publish it with Tunnel/reverse proxy. No remote host option.
UI GETs do not authenticate with providers; write operations are bounded management.
Run native browser navigation acceptance separately. Do not change a managed browser
policy when it forbids localhost. Report component vs HTTP vs native browser evidence.


## v0.5 multi-device and broker rules

Read docs/MULTI_DEVICE.md and docs/SYNC_PROTOCOL_V1.md before enabling replication.
Never clone the entire live state directory to another online device; initialize its own vault and identity.
Sync only approved credential slots. Do not synchronize private identity, master key, client token, cookies,
CLI paths, service origins, MCP configuration or access policies. Verify full public fingerprints out of band.
A conflict is not missing configuration: stop affected calls and ask the Owner to choose a whole revision.
Do not use wall-clock order or concatenate Key strings. Do not reset the vault to fix sync_state_drift.

Use an installed broker-mode Skill's exact `atm --client NAME` prefix. No direct fallback on rejection;
do not read profile contents into model context, pass --allow-* flags, issue grants or extend expiry yourself.
Owner operations remain explicit; `sync watch` and `broker serve` are foreground, bounded leases.
Same OS-user default mode is not adversarial isolation. Linux UID binding does not sandbox approved project code.
Keep real credentials out of tests and Git. Run the normal suite and independently record cross-UID acceptance.
The new external file transport and cryptographic envelope are not third-party audited or production-account verified.


## v0.6 extension work

Read docs/EXTENSIBILITY.md and data/EXTENSION_AUTHORING.md before adding an adapter.
Prefer custom JSON definitions and a credential slot over editing a vendor name list.
Only owner-reviewed definitions are installed. Draft-model calls are opt-in, separate
from tool execution and supplier Key access. No self-approval of new origins/grants.
Browser sessions are local-only encrypted records, never API sync entries or repository files.
New web_recipe tests must state whether navigation is native or an in-memory test adapter.
Keep acceptance/test_recipe_native_v06.py separate from claimed local DOM coverage.
Do not change managed browser policy to make a test pass. Ensure new definitions,
credential references and expected-definition pins are enforced through both CLI and Broker.
Existing default-client config, synchronization and conflict regressions remain required.


## v0.7 credential-first acceptance and security

Read docs/SECRETS_FIRST.md and docs/SECURITY_REVIEW_V07.md. Ordinary scripts need no
ATM tool manifest. Discover metadata first; use exact `atm://` references and an
Owner-reviewed `access permit-exec`. CLI `--apply --approve` is not an independent
human-identity boundary against a same-UID hostile Agent. Never self-approve.

Use the scoped prefix registered by `atm setup --broker`; new sessions query
`session status` and `keys find`, not .env files or client-profile contents. Generic
exec is same-UID only; do not weaken this into running another user's arbitrary code
with Broker privileges. Scope pins argv, workspace, program and file operands but
NOT all imports/libraries, network or dependencies. No sandbox claims.

Unlock defaults to fixed 30 minutes and can be invoked in the Owner terminal or
local Web management. Active sessions share only controlled credential operations,
not a raw master-key API. Owner profile remains separate from Agent profiles. Never
synchronize any profile, session token or unlock password. Read-only discovery does
not decrypt. Session expiry/revoke denies NEW admissions, not copies already delivered.

Test runtime paths using fake Keys, independent headless processes, a real PTY and
local HTTP fixture. Distinguish these from real Claude/Codex client loading and
real cross-machine/public-network tests. No live production calls without permission.

Historical `scripts/finalize_release.py` / v0.2 report generators are not the v0.7 release path. Do not reuse their hard-coded version or test counts. Run the current pytest gate and generate reports from its actual XML plus separate acceptance receipts.

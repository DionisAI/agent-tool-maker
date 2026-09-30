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

Humans provide secrets via a private local terminal, complete official login/consent,
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
JSON output is default: do not invent --json, atm unlock, an ATM daemon or MCP server.

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

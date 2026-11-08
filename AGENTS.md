# ATM repository instructions

Read README.md and SKILL.md first. The default experience is **Agent prepares;
human unlocks in one local window; Agent continues**. Do not hand the user a long
list of installation, grant, profile and execution commands.

## User workflow

- Stable user installation and user-level Skills for local Claude Code + Codex.
- `atm start` creates a bounded local consent window; `atm use` injects selected
  credentials into ordinary programs. Neither requires a tool manifest.
- Keep secrets in the existing vault. Never reset or move it for an upgrade.
- Human password/Key input is only in the local window or explicit private terminal,
  never chat. The Agent must not read session/profile files or approve its own popup.
- Default convenience mode trusts same-user code in an explicitly approved project;
  it does not claim hostile-code isolation. Old strict scopes remain strict.
- JSON output reports ready, pending, denied, missing, expired and conflicts distinctly.
  Reuse requests. Never silently extend a lease, expand scope, or resubmit side effects.
- Owner-managed Higgsfield OAuth is separate from Key slots and CLI login. Encrypt
  tokens in the existing vault; opt-in native-keyring refresh never extends project
  leases. Keep consent human, resource/issuer pinned and uncertain rotations unretried.

## Changes and tests

Use isolated test state and fake credentials. Do not access production accounts or
install unknown tooling. Keep failure, skip, mock and real integration evidence separate.
Do not disable security checks or remove assertions just to make CI green.
Test protocol behavior, real subprocesses, local HTTP and native browser behavior separately.
Never change a managed browser policy to run a test.

Only `atm` is an installed command. Removed command/env aliases must not return.
Existing encrypted vault formats still need to decrypt; private old-format markers
are data compatibility, not another product name. Do not mass-reencrypt or reset Keys.

When changes are ready, use a new branch/PR and check its exact SHA. The user's
explicit publication/merge instructions govern writes; do not change repository visibility,
bypass branch protections, force-push main, or merge failing CI.
Consult SECURITY.md, docs/SECRETS_FIRST.md, docs/MULTI_DEVICE.md and
EXTENSIBILITY.md only for the respective advanced path, not as a first-use reading list.

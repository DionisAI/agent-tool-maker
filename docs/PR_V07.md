## Goal
Make ATM the credential-first replacement for plaintext project .env files. An unchanged app.py reading os.environ['FAL_KEY'] can run through Owner-reviewed grants without any ATM tool manifest.

## Delivered
- Fixed30m Owner unlock session with explicit unlock/lock/status, shared by terminal and local Web Key CRUD; repeated calls do not extend a lease.
- Scoped key metadata discovery, exact credential references, explicit ambiguity; no raw-secret retrieval RPC.
- Owner-approved command permits: argv/workspace/env mapping/program and file pins; ordinary programs need no catalog entry.
- Same-UID generic execution only; minimal injected environment, bounded memory output, no raw stdout/stderr persistence, stable request keys.
- Key/connection state and grant rechecked before admission. Scoped client never becomes management authority and never falls back on rejection.
- Request-specific unlocked vault snapshot prevents lock races from causing a password/keyring fallback.
- Credential-first Claude/Codex broker Skills, Web unlock controls, actual PTY and independent-process acceptance script.

## Security review and evidence
Read docs/SECURITY_REVIEW_V07.md, docs/TEST_REPORT_V07.md and reports/v07/summary.json.
Tests use fake credentials and local protocol/HTTP fixtures, not real vendor accounts or real Claude/Codex model calls. The two encrypted device stores are on one test machine.
Earlier failed/interrupted development runs are retained in the release archive. A fixture-budget correction separates semantic-error tests from the unchanged dedicated timeout test; no product timeout/approval check was relaxed.

## Boundaries
Same-UID operation is not hostile-agent isolation. Approved code receives plaintext selected secrets and may exfiltrate them; output redaction is best-effort. Generic exec across UIDs is explicitly unsupported, not an escalation to Owner privileges. File pins are not complete dependency attestation or a TOCTOU-free sandbox. Expiry/lock prevents new admissions, not already delivered bytes.
No Passkey, OAuth refresh, unattended service installer, hosted sync relay, hard monetary budget, full independent security audit or Windows acceptance. No claim of native browser navigation/actual host loading or true public-network multi-machine acceptance.

This draft body does not assert remote CI success. Check the exact pushed head after upload; do not auto-merge main or predecessor PRs.

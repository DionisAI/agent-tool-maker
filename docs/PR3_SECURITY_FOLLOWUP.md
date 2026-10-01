# v0.7.0 merge review: grant snapshot binding

The publication record is PR #3 in DionisAI/agent-tool-maker. Earlier reports
saying that v0.5-v0.7 were not uploaded describe their original ZIP deliveries,
not the current publication status. Read the exact PR head's CI and merge status.

## Finding and repair

CodeRabbit identified an owner-local race in `/api/access/grant`: the Web layer
checked a digest using one preview, then `grant(..., apply=True)` recalculated
configuration. A concurrent owner-side writer could change executable/origin
settings in between. The new grant could therefore pin an unapproved snapshot.
This was not evidence of a remote or hostile cross-UID authorization bypass.

The Web layer now passes the approved digest into the grant function. That
function builds one configuration snapshot, checks its digest before creating
any token or policy, and persists the very same snapshot. It never recalculates
pins after approval. Later configuration drift does not enlarge the grant:
normal Broker admission rejects the pinned grant as `grant_stale`.

Seven deterministic regressions cover changes immediately before actual grant
creation, a single configuration capture, a concurrent write at persistence,
and malformed/mismatched approval digests without profile/policy side effects.
On the old implementation three of these regressions failed; after the fix all
seven passed locally. Existing tests and authorization assertions were retained.

```sh
python -m pytest -q tests/test_grant_snapshot_v07.py
python -m pytest -q -m 'not browser and not integration'
python scripts/demo_secrets_first.py --out /tmp/atm-secrets-receipt.json
```

CI separately validates the supported Python versions, real local tools,
browser/native navigation, Linux peer UID, package installation and the core
secrets-first flow. Do not substitute a previous commit's result for final-head CI.

This is a targeted author fix with regression evidence, not an independent
cryptographic audit or protection from an owner-account compromise. No real
vendor credentials or supplier calls are involved in these tests. The v0.7
same-UID generic-exec and already-released-secret limitations remain unchanged.

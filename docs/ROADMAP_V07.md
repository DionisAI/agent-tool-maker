# v0.7 scope and next gates

Implemented: credential-first metadata, ordinary process injection without tool manifests, fixed30m unified Owner session for Key CRUD/exec, specific permits, local Web controls, failure distinctions and security regressions.

Not silently included:
- Real Claude Code / Codex Skill loading, native OS keyring, two physical/networked machines: user-device acceptance.
- Cross-UID generic program execution: requires a separately designed privilege drop/sandbox, NOT running arbitrary Agent code with Owner rights.
- Passkey and recovery: require a proper key-wrapping/unlock design, not treating signatures as decryption keys.
- OAuth refresh; startup services; remote credential service; S3/R2 relay: not in this release.
- Sliding idle timeout: intentionally not default. A fixed30m lease never extends due to Agent activity.
- Broad mutable-project permits: not default. Current exact argv/identified file pins trade convenience for explicit review after edits.
- Full dependency pinning / race-resistant execution / network egress sandbox / trusted human-approval channel: still needed for hostile same-UID programs.
- Arbitrary output secret noninterference: not claimed; selected plaintext can be transformed by approved programs.
- Uniform legacy sync/verify/MCP operations under new session: current unified scope is Key CRUD and program/tool use, not every administrative function.
- Public-package release/remote CI: check actual GitHub state, not local historical reports.

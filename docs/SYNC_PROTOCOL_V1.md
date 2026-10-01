# ATM sync-v1 protocol and security contract

Status: implemented development protocol, **not an independently audited security product or a claim of standardized HPKE**. Dependencies use cryptography's established primitives; composing those primitives into this envelope and operating the endpoints still requires review.

## Identities and envelope

Each device generates two independent key pairs: X25519 encryption and Ed25519 signing. The public card contains format, name, base64 public keys and SHA-256 fingerprint of canonical `{format,encryption_key,signing_key}`. Names are display labels, not identity. The complete fingerprint must be verified out of band before pairing. Private material is AES-256-GCM-encrypted under that device's own existing vault key.

Each recipient packet is a fresh ephemeral X25519 exchange followed by HKDF-SHA256, length32, random32-byte salt, `info = b'ATM-SYNC-v1\x00' + canonical(header)`. AES-256-GCM uses a random12-byte nonce and the same canonical header as AAD. Ed25519 signs canonical `{header,ciphertext}`. Header fields are `format,sender,recipient,packet,ephemeral,salt,nonce`. The signature is verified using the pinned sender card before decrypting. Recipient identity and exact protocol shape are checked. No trust-on-first-use of incoming packets.

The encrypted payload is exactly `{records:{provider:[version,...]}}`. Versions include a random nonce, revision digest, author, vector clock, deleted, value, expires_at and informational created_at. Local registers and device private keys use domain-separated AAD; the old compatible active secret view uses existing provider AAD. Imported values are re-encrypted with a fresh nonce under the receiving device's own vault key. The local master key is never transmitted.

Public transport metadata reveals device IDs, link/timing/size information and random cryptographic values. Provider names and Key content are inside the ciphertext. The packet scheme does **not** have forward secrecy against later compromise of the recipient's static private key. Treat packet archives as sensitive encrypted backups. Passphrase brute-force risk depends on the passphrase; local scrypt parameters remain the earlier vault design.

## Convergence and conflict

Per-provider multi-value registers track causal versions. Join = union of identical revisions, reject distinct revisions with identical vector clocks, retain undominated versions. When all surviving versions have identical `{value,deleted,expires_at}`, one usable value may be materialized while causal heads are retained. Otherwise the register is a conflict and **no usable active Key is materialized**. Do not use clocks for last-write-wins.

Resolution checks a digest of the currently visible heads, selects one whole record and creates a fresh local revision whose vector dominates all observed heads. Concurrent resolutions can conflict again. Tombstones survive merges, preventing old packets from resurrecting deleted values. SQLite transactions keep the register and active compatibility view together. Pre-sync clients modifying that view are detected as drift on later register operations; do not run downgraded clients against a sync-enabled state directory.

These rules protect against replay of observed old state and ordinary concurrent editing. They are not Byzantine consensus. A trusted malicious writer can lie about causal history, deny service or supply a bad value. Do not pair untrusted writers. Restoring a full old local database also restores its knowledge/counters; rollback protection without an external monotonic checkpoint is not provided.

## Permissions and delivery

Pairing stores exact per-provider send and receive lists independently at each device. No private identity, vault password, client bearer, local CLI path, executable digest, origin, MCP config or task artifact is synchronized. Scope changes are explicit and force the next snapshot. Revocation is checked on import/export, does not erase previously delivered material, and is not an instant global revocation broadcast.

File transport performs bounded exchange cycles. Immutable packets are fsynced to a temporary file, then published using same-directory hard-link creation (no overwrite). Payload parsing rejects duplicate keys, non-finite numbers and oversized inputs. Invalid authenticated input does not partially modify records. Already received packets are tracked locally. Transport hiding/deleting packets can prevent freshness; the protocol does not claim availability or detection of every withheld update.

Limits: 8MiB packet, 256 providers, 32 concurrent heads/provider, 64 actors/clock, positive counters below2^53, 512 inbox candidate files/cycle. No automatic historical garbage collection. Filenames are random, not raw secret hashes. Internal snapshot digest remains local. No private sync files should be committed to the source repo.

## Broker security

Broker is a separate local Unix socket, not an extension of the Web console. Owner unlocks once for a bounded lease. Default socket0600, exact random profile bearer, per-grant tool/definition/config pins, workspace and expiry. Server stores token hash; the client profile is a0600 **plaintext capability secret**, not a supplier Key. It must remain outside Git, Skills and transcripts.

Linux group sockets optionally authenticate real SO_PEERCRED UID, permitting a separate client OS user while keeping owner vault files private. This does not sandbox code executed by an approved adapter. MCP, workflows and handoffs are denied in restricted mode until transitive authorization is implemented. Revocation prevents next admission, not cancellation of in-flight work. Memory is cleared by dropping references at stop; Python cannot promise secure zeroization or protection from root/debuggers/swap/core dumps.

No silent fallback after rejection. No secret retrieval/admin/sync API in the broker. Same-UID default mode is a convenience/least-privilege call interface, not a boundary against malicious processes with access to owner files. For high-value production credentials use reviewed OS isolation/egress and consider an independently reviewed external secrets manager or KMS.

## Primary primitive references

- https://cryptography.io/en/latest/hazmat/primitives/asymmetric/x25519/
- https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
- https://cryptography.io/en/latest/hazmat/primitives/aead/
- https://cryptography.io/en/latest/hazmat/primitives/key-derivation-functions/#hkdf

These references specify primitives, not an audit or endorsement of ATM's protocol.

Agent labels such as claude/codex are labels, not executable attestation. The authenticated subject is the capability token plus local UID (where supported). OS process identity, tool sandboxing and vendor-account restrictions remain separate controls.

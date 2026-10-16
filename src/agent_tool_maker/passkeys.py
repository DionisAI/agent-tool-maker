"""Local WebAuthn + PRF key wrapping, never an authentication-state sync format.

Only the human console owns ceremonies. No credential private key, PRF output,
master key or password is persisted/logged/returned. Public records and wrapped
master keys are local to the vault; its original backend remains the recovery path.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import re
import secrets
import threading
import time
from urllib.parse import urlparse

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .errors import RouterError
from .storage import canonical
from .sync import strict_json

SETTING = 'local_passkeys_v1'
RP = 'localhost'
TTL = 180


def encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def decode(value, *, size=None):
    try:
        if not isinstance(value, str) or not 1 <= len(value) <= 16384 or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
            raise ValueError()
        raw = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
        if encode(raw) != value or size is not None and len(raw) != size:
            raise ValueError()
        return raw
    except (ValueError, TypeError):
        raise RouterError('invalid_passkey', 'Malformed bounded Passkey data.') from None


def library():
    try:
        import webauthn
        from webauthn.helpers.cose import COSEAlgorithmIdentifier
        return webauthn, COSEAlgorithmIdentifier
    except ImportError:
        raise RouterError('passkey_dependency_missing', 'Install the reviewed ATM passkey extra before enrollment; the original unlock route remains available.') from None


class Passkeys:
    def __init__(self, state, origin):
        self.state, self.origin = state, origin
        self.pending = None
        self.lock = threading.RLock()
        self.timer = None

    def _supported(self):
        parsed = urlparse(self.origin)
        return parsed.scheme == 'http' and parsed.hostname == RP and parsed.port is not None

    def _ready(self):
        if not self._supported():
            raise RouterError('passkey_origin', 'Use the ATM window opened at localhost for local Passkeys.')
        library()
        cfg = self.state.setting('vault')
        if not cfg:
            raise RouterError('vault_not_initialized', 'Create the recovery-password vault before adding a Passkey.')
        return hashlib.sha256(canonical(cfg).encode()).hexdigest()

    def _records(self):
        value = self.state.setting(SETTING, [])
        if not isinstance(value, list) or len(value) > 16 or any(not isinstance(r, dict) for r in value):
            raise RouterError('passkey_state_invalid', 'Inspect local Passkey metadata; existing vault was preserved.')
        try:
            for record in value:
                for key, size in [('id', None), ('public_key', None), ('user', 32), ('prf_salt', 32), ('nonce', 12), ('wrapped_key', 48)]:
                    decode(record[key], size=size)
                if (type(record['sign_count']) is not int or not 0 <= record['sign_count'] <= 0xffffffff
                        or type(record['disabled']) is not bool or not isinstance(record['label'], str)
                        or not 1 <= len(record['label']) <= 80 or not re.fullmatch('[a-f0-9]{64}', record['vault'])
                        or type(record['created_at']) not in (int, float)):
                    raise ValueError()
            if len({r['id'] for r in value}) != len(value):
                raise ValueError()
        except (KeyError, ValueError, TypeError, RouterError):
            raise RouterError('passkey_state_invalid', 'Local Passkey metadata failed validation; existing vault was preserved.') from None
        return value

    def status(self):
        state_error = None
        try:
            records = self._records()
        except RouterError as error:
            records, state_error = [], error.as_dict()
        available = importlib.util.find_spec('webauthn') is not None
        return {'available': available and self._supported() and state_error is None, 'dependency_present': available,
            'state_error': state_error,
            'origin_supported': self._supported(), 'registered': sum(not r.get('disabled') for r in records),
            'credentials': [{k: r[k] for k in ('id', 'label', 'created_at', 'disabled')} for r in records],
            'mode': 'local_webauthn_prf', 'synced': False, 'recovery_backend_preserved': True, 'secrets_returned': False}

    def clear(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            if self.pending:
                self.pending.pop('master', None)
            self.pending = None

    def _expire(self, identifier):
        with self.lock:
            if self.pending and self.pending['id'] == identifier:
                self.clear()

    def _start(self, phase, intent, **extra):
        with self.lock:
            if self.pending and time.monotonic() < self.pending['expires']:
                raise RouterError('passkey_busy', 'Finish or cancel the current Passkey ceremony; its expiry was not extended.')
            self.clear()
            pending = {'id': secrets.token_hex(16), 'phase': phase, 'intent': intent,
                'challenge': secrets.token_bytes(32), 'expires': time.monotonic() + TTL, **extra}
            self.pending = pending
            self.timer = threading.Timer(max(0, pending['expires'] - time.monotonic()), self._expire, (pending['id'],))
            self.timer.daemon = True
            self.timer.start()
            return pending

    def _take(self, body, phase, intent):
        with self.lock:
            pending = self.pending
            self.pending = None  # Detach, retaining this call's master key until its verification ends.
            self.clear()  # Every finish attempt consumes its challenge, including invalid input.
        if not isinstance(body, dict):
            raise RouterError('invalid_passkey', 'Expected a Passkey proof object.')
        allowed = {'ceremony_id', 'credential'} | ({'prf_first'} if phase != 'register' else set())
        if set(body) - allowed:
            raise RouterError('invalid_passkey', 'Unexpected Passkey proof fields.')
        if not pending or time.monotonic() >= pending['expires'] or pending['phase'] != phase:
            raise RouterError('passkey_expired', 'Passkey ceremony expired or was consumed; start a new explicit ceremony.')
        if not hmac.compare_digest(str(body.get('ceremony_id', '')), pending['id']) or pending['intent'] != intent:
            raise RouterError('passkey_binding', 'Passkey ceremony is bound to another window or operation.')
        return pending

    def _credential(self, body, pending, *, authentication):
        credential = body.get('credential')
        if not isinstance(credential, dict) or len(canonical(credential)) > 50000:
            raise RouterError('invalid_passkey', 'Expected a bounded WebAuthn response.')
        identifier = decode(credential.get('id'))
        if credential.get('type') != 'public-key' or decode(credential.get('rawId')) != identifier:
            raise RouterError('invalid_passkey', 'Credential identity or type changed.')
        try:
            client = strict_json(decode(credential['response']['clientDataJSON']), limit=8192)
        except (KeyError, TypeError):
            raise RouterError('invalid_passkey', 'WebAuthn client data is missing.') from None
        expected_type = 'webauthn.get' if authentication else 'webauthn.create'
        if (not isinstance(client, dict) or client.get('type') != expected_type or client.get('origin') != self.origin
                or client.get('crossOrigin', False) is not False or 'topOrigin' in client
                or decode(client.get('challenge')) != pending['challenge']):
            raise RouterError('passkey_binding', 'WebAuthn origin, challenge or frame binding did not match.')
        return credential

    def _authentication(self, body, pending, record):
        credential = self._credential(body, pending, authentication=True)
        if credential['id'] != record['id']:
            raise RouterError('passkey_binding', 'A different Passkey was returned.')
        user = credential.get('response', {}).get('userHandle')
        if user is not None and decode(user) != decode(record['user']):
            raise RouterError('passkey_binding', 'Passkey user binding changed.')
        module, _ = library()
        try:
            return module.verify_authentication_response(credential=credential,
                expected_challenge=pending['challenge'], expected_rp_id=RP, expected_origin=self.origin,
                credential_public_key=decode(record['public_key']), credential_current_sign_count=record['sign_count'],
                require_user_verification=True)
        except Exception:
            raise RouterError('passkey_verification', 'Passkey signature, presence, verification or counter validation failed.') from None

    def _options(self, pending, record):
        return {'ceremony_id': pending['id'], 'publicKey': {'challenge': encode(pending['challenge']),
            'rpId': RP, 'timeout': int(max(1, pending['expires'] - time.monotonic()) * 1000),
            'userVerification': 'required', 'allowCredentials': [{'type': 'public-key', 'id': record['id']}],
            'extensions': {'prf': {'eval': {'first': record['prf_salt']}}}}}

    @staticmethod
    def _wrapping(prf, record):
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=decode(record['prf_salt'], size=32),
            info=('ATM local Passkey wrap v1\0' + record['vault'] + '\0' + record['id']).encode()).derive(prf)

    @staticmethod
    def _aad(record):
        return canonical({k: record[k] for k in ('vault', 'id', 'user', 'public_key', 'prf_salt')}).encode()

    def register_begin(self, vault, label):
        vault_id = self._ready()
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80 or any(ord(c) < 32 for c in label):
            raise RouterError('invalid_request', 'Use a short nonsecret Passkey label.')
        records = self._records()
        if len(records) >= 16:
            raise RouterError('passkey_limit', 'Local Passkey metadata limit reached; existing records preserved.')
        vault._key = None
        master = vault.unlock()  # Original recovery password/keyring is required for every enrollment.
        pending = self._start('register', 'register', master=master, vault=vault_id,
            records_sha=hashlib.sha256(canonical(records).encode()).hexdigest(), label=label.strip(),
            user=encode(secrets.token_bytes(32)), prf_salt=encode(secrets.token_bytes(32)))
        return {'ceremony_id': pending['id'], 'publicKey': {'challenge': encode(pending['challenge']),
            'rp': {'id': RP, 'name': 'ATM local vault'}, 'user': {'id': pending['user'],
                'name': 'atm-' + vault_id[:12], 'displayName': 'ATM · ' + label.strip()},
            'pubKeyCredParams': [{'type': 'public-key', 'alg': -7}], 'attestation': 'none', 'timeout': TTL * 1000,
            'authenticatorSelection': {'residentKey': 'required', 'requireResidentKey': True, 'userVerification': 'required'},
            'excludeCredentials': [{'type': 'public-key', 'id': r['id']} for r in records], 'extensions': {'prf': {}}}}

    def register_verify(self, body):
        pending = self._take(body, 'register', 'register')
        credential = self._credential(body, pending, authentication=False)
        module, algorithms = library()
        try:
            verified = module.verify_registration_response(credential=credential, expected_challenge=pending['challenge'],
                expected_rp_id=RP, expected_origin=self.origin, require_user_verification=True,
                supported_pub_key_algs=[algorithms.ECDSA_SHA_256])
        except Exception:
            raise RouterError('passkey_verification', 'Passkey registration validation failed; existing vault was preserved.') from None
        record = {'id': encode(verified.credential_id), 'public_key': encode(verified.credential_public_key),
            'sign_count': verified.sign_count, **{k: pending[k] for k in ('vault', 'user', 'label', 'prf_salt')},
            'created_at': time.time(), 'disabled': False}
        # Authenticate the newly created credential and evaluate PRF before persisting anything.
        next_step = self._start('bind', 'register', master=pending['master'], record=record,
            records_sha=pending['records_sha'], vault=pending['vault'], expires=pending['expires'])
        return self._options(next_step, record)

    def register_finish(self, body):
        pending = self._take(body, 'bind', 'register')
        record = pending['record']
        verified = self._authentication(body, pending, record)
        prf = decode(body.get('prf_first'), size=32)
        record['sign_count'] = verified.new_sign_count
        record['nonce'] = encode(secrets.token_bytes(12))
        record['wrapped_key'] = encode(AESGCM(self._wrapping(prf, record)).encrypt(decode(record['nonce']), pending['master'], self._aad(record)))
        with self.state.db() as db:
            from .sync import _get, _set
            db.execute('BEGIN IMMEDIATE')
            current = _get(db, SETTING, [])
            cfg = _get(db, 'vault')
            if (hashlib.sha256(canonical(current).encode()).hexdigest() != pending['records_sha']
                    or hashlib.sha256(canonical(cfg).encode()).hexdigest() != pending['vault']
                    or any(r['id'] == record['id'] for r in current)):
                raise RouterError('state_changed', 'Vault or Passkey registrations changed; no record was replaced.')
            _set(db, SETTING, [*current, record])
        return {'status': 'registered', 'label': record['label'], 'secrets_returned': False,
            'original_ciphertexts_preserved': True, 'recovery_backend_preserved': True}

    def auth_begin(self, identifier, intent):
        vault_id = self._ready()
        record = next((r for r in self._records() if r['id'] == identifier and not r['disabled']), None)
        if not record or record['vault'] != vault_id:
            raise RouterError('passkey_missing', 'Select a registered active Passkey for this local vault.')
        pending = self._start('authenticate', intent, record=record,
            record_sha=hashlib.sha256(canonical(record).encode()).hexdigest())
        return self._options(pending, record)

    def auth_finish(self, vault, body, intent):
        pending = self._take(body, 'authenticate', intent)
        record = pending['record']
        verified = self._authentication(body, pending, record)
        try:
            key = AESGCM(self._wrapping(decode(body.get('prf_first'), size=32), record)).decrypt(
                decode(record['nonce'], size=12), decode(record['wrapped_key']), self._aad(record))
        except InvalidTag:
            raise RouterError('passkey_unwrap_failed', 'PRF did not unwrap this vault; use the recovery password.') from None
        with self.state.db() as db:
            from .sync import _get, _set
            db.execute('BEGIN IMMEDIATE')
            records = _get(db, SETTING, [])
            current = next((r for r in records if r['id'] == record['id']), None)
            if not current or hashlib.sha256(canonical(current).encode()).hexdigest() != pending['record_sha']:
                raise RouterError('state_changed', 'Passkey was changed or disabled during verification.')
            vault.unlock_with_key(key)
            _set(db, SETTING, [{**r, 'sign_count': verified.new_sign_count} if r['id'] == record['id'] else r for r in records])

    def disable(self, vault, identifier):
        self._ready()
        vault._key = None
        vault.unlock()  # Always require recovery authentication, not an ambient project lease.
        with self.state.db() as db:
            from .sync import _get, _set
            db.execute('BEGIN IMMEDIATE')
            records = _get(db, SETTING, [])
            if not any(r['id'] == identifier for r in records):
                raise RouterError('passkey_missing', 'Local Passkey record not found.')
            _set(db, SETTING, [{**r, 'disabled': True} if r['id'] == identifier else r for r in records])
        return {'status': 'disabled', 'existing_session_unchanged': True, 'secrets_returned': False}

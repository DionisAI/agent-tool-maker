"""Compile reviewed Tripo DOM adapters into ATM manifests and executable CLI bundles.

No login, credentials, provider requests or automatic installation.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# This reviewed repository's factory retains failed builds. An older installed
# factory used destructive temporary cleanup: never select it by ambient PATH.
sys.path.insert(0, str(ROOT / 'src'))
import agent_tool_maker.extensions as extensions
if not Path(extensions.__file__).resolve().is_relative_to(ROOT / 'src'):
    raise RuntimeError('A different ATM package was already loaded; start a fresh process using the reviewed repository source.')
from agent_tool_maker.extensions import pack
from agent_tool_maker.maker import validate_manifest


def adapter_digest():
    sha = hashlib.sha256()
    for name in ('account.js', 'assets.js', 'core.mjs'):
        sha.update((name + '\0').encode())
        sha.update((ROOT / 'examples/opencli/tripo-studio' / name).read_bytes())
        sha.update(b'\0')
    return sha.hexdigest()


def paid_digest():
    sha = hashlib.sha256(adapter_digest().encode())
    for name in ('quote.js', 'generate.js', 'paid.mjs'):
        sha.update((name + '\0').encode())
        sha.update((ROOT / 'examples/opencli/tripo-studio' / name).read_bytes())
        sha.update(b'\0')
    return sha.hexdigest()


def manifest(operation):
    is_paid_path = operation in ('quote', 'generate')
    argv = ['__opencli_shim', 'tripo-studio', operation, '--pin', paid_digest() if is_paid_path else adapter_digest(), '-f', 'json']
    schema = {'type': 'object', 'properties': {}, 'additionalProperties': False}
    example = {}
    if operation == 'assets':
        schema['properties']['limit'] = {'type': 'integer', 'minimum': 1, 'maximum': 100}
        schema['required'] = ['limit']
        argv.extend(['--limit', {'input': 'limit'}])
        example = {'limit': 20}
    if operation == 'generate':
        schema['properties'] = {
            'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 1000},
            'max_credits': {'type': 'integer', 'minimum': 1, 'maximum': 10000},
            'quote_sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'},
            'request_key': {'type': 'string', 'pattern': '^[A-Za-z0-9_.:-]{1,160}$'},
            'human_confirmed': {'type': 'boolean', 'const': True},
        }
        schema['required'] = list(schema['properties'])
        argv.extend(['--prompt', {'input': 'prompt'}, '--budget', {'input': 'max_credits'},
                     '--quote', {'input': 'quote_sha256'}, '--key', {'input': 'request_key'},
                     '--ledger', {'workspace': ''}, '--confirm'])
    return validate_manifest({
        'id': 'tripo.studio.' + operation, 'provider': 'tripo',
        'title': 'Tripo Studio ' + ('' if is_paid_path else 'readonly ') + operation, 'capabilities': ['account'] if operation == 'account' else ['3d', operation],
        'adapter': 'command', 'executable': 'opencliapp', 'paid': operation == 'generate',
        'permissions': ['external_write'] if is_paid_path else [],
        'schema': schema, **({'example': example} if operation != 'generate' else {}),
        'command': {'argv': argv, 'output': 'json', 'timeout': 90 if operation == 'generate' else 60},
        'sources': ['https://studio.tripo3d.ai/', 'https://www.tripo3d.ai/help/api-plugins/tripo-studiotripo-api'],
        'notes': 'Visible DOM only; reuse browser-owned login, no credential injection. Pin covers adapter files, not hostile-code isolation. Asset coverage is loaded cards, task_status unknown. Paid text path requires current quote, human confirmation, credit ceiling and durable pre-click claim. No upload, publishing or automatic retry.' if is_paid_path else 'Visible DOM only; reuse browser-owned login, no credential injection. Pin covers adapter source files; not hostile-code isolation. Asset coverage is loaded cards only, task_status remains unknown.',
        'completion': 'CLI acceptance only. Paid submission observes a new asset route; finished model and download are separate gates.' if is_paid_path else 'A successful live DOM read is not generation, complete pagination or independent task acceptance.',
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--stage', choices=['readonly', 'paid', 'all'], default='readonly')
    args = parser.parse_args()
    operations = ('account', 'assets') if args.stage == 'readonly' else ('quote', 'generate') if args.stage == 'paid' else ('account', 'assets', 'quote', 'generate')
    result = [pack(manifest(operation), args.out / operation) for operation in operations]
    print(json.dumps({'adapter_sha256': adapter_digest(), 'paid_adapter_sha256': paid_digest(), 'bundles': result, 'installed': False, 'provider_calls': 0}))

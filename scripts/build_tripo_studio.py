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

EXTENDED_OPERATIONS = ('asset', 'asset_resolve', 'assets_all', 'retopo_quote', 'retopo', 'rig_quote', 'rig', 'image_quote', 'image_generate', 'export_quote', 'export')
EXTENDED_FILES = ('account.js', 'assets.js', 'core.mjs', 'quote.js', 'generate.js', 'paid.mjs', 'extended.mjs', 'extended.js')


def extended_digest():
    sha = hashlib.sha256()
    for name in EXTENDED_FILES:
        sha.update((name + '\0').encode())
        sha.update((ROOT / 'examples/opencli/tripo-studio' / name).read_bytes())
        sha.update(b'\0')
    return sha.hexdigest()


def extended_manifest(operation):
    paid = operation in ('retopo', 'rig', 'image_generate')
    writes = operation not in ('asset', 'asset_resolve', 'assets_all')
    argv = ['__opencli_shim', 'tripo-studio', operation.replace('_', '-'), '--pin', extended_digest(), '-f', 'json']
    properties = {}
    example = None
    uuid = {'type': 'string', 'pattern': '^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$'}
    if operation not in ('assets_all', 'asset_resolve', 'image_quote', 'image_generate'):
        properties['asset_id'] = uuid
        argv += ['--asset', {'input': 'asset_id'}]
    if operation == 'asset':
        properties['wait_seconds'] = {'type': 'integer', 'minimum': 0, 'maximum': 120}
        argv += ['--wait', {'input': 'wait_seconds'}]
    if operation == 'asset_resolve':
        properties['preview_task_id'] = uuid
        argv += ['--preview', {'input': 'preview_task_id'}]
    if operation == 'assets_all':
        properties.update(limit={'type': 'integer', 'minimum': 1, 'maximum': 1000}, max_pages={'type': 'integer', 'minimum': 1, 'maximum': 50})
        argv += ['--limit', {'input': 'limit'}, '--pages', {'input': 'max_pages'}]
        example = {'limit': 1000, 'max_pages': 50}
    if operation in ('retopo_quote', 'rig_quote'):
        settings = {'topology': {'enum': ['Quad', 'Triangle']}, 'polygon_count': {'type': 'integer', 'minimum': 500, 'maximum': 200000}, 'smart_mesh': {'type': 'boolean'}} if operation == 'retopo_quote' else {
            'rigging_type': {'enum': ['Humanoid', 'Other']},
            'skeleton': {'enum': ['ActorCore', 'Mixamo', 'UE5 Mannequin', 'VRM 1.0 Humanoid', 'Unity Humanoid Compatible']},
        }
        properties['settings'] = {'type': 'object', 'properties': settings, 'additionalProperties': False}
        argv += ['--settings', {'json': 'settings'}]
    if paid or operation in ('image_quote', 'export'):
        properties.update(request_key={'type': 'string', 'pattern': '^[A-Za-z0-9_.:-]{1,160}$'}, human_confirmed={'type': 'boolean', 'const': True})
        argv += ['--key', {'input': 'request_key'}, '--ledger', {'workspace': ''}, '--confirm']
    if paid or operation == 'export':
        properties['quote_sha256'] = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
        argv += ['--quote', {'input': 'quote_sha256'}]
    if paid:
        properties['max_credits'] = {'type': 'integer', 'minimum': 1, 'maximum': 10000}
        argv += ['--budget', {'input': 'max_credits'}]
    if operation == 'image_quote':
        properties['image'] = {'type': 'string', 'minLength': 1, 'maxLength': 2048}
        argv += ['--file', {'file': 'image'}]
    if operation == 'image_generate':
        properties['image_sha256'] = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
        argv += ['--image-sha', {'input': 'image_sha256'}]
    command = {'argv': argv, 'output': 'json', 'timeout': 900 if operation == 'assets_all' else 180}
    if operation == 'export':
        argv += ['--output', {'output': 'model.glb'}]
        command['outputs'] = ['model.glb']
    return validate_manifest({
        'id': 'tripo.studio.' + operation, 'provider': 'tripo', 'title': 'Tripo Studio ' + operation,
        'capabilities': ['3d', operation], 'adapter': 'command', 'executable': 'opencliapp',
        'paid': paid, 'permissions': ['external_write'] if writes else [],
        'schema': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False},
        **({'example': example} if example is not None else {}), 'command': command,
        'sources': ['https://studio.tripo3d.ai/'],
        'notes': 'Visible UI only; exact asset UUID differs from thumbnail preview UUID. Image quote uploads one explicitly approved project raster. Paid calls require current quote, budget, confirmation and shared durable receipt lock. Export delivers a validated GLB file. Scroll scan reports partial unless explicit UI end is observed. No raw auth, private endpoint replay, publication, silent retry or hostile-code isolation.',
        'completion': 'Submission is not a finished model; use asset status. Export checks the completed local GLB. Pagination coverage is explicit; a quiet footer is not authoritative completeness.',
    })


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
    if operation in EXTENDED_OPERATIONS:
        return extended_manifest(operation)
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
    parser.add_argument('--stage', choices=['readonly', 'paid', 'extended', 'all'], default='readonly')
    args = parser.parse_args()
    operations = ('account', 'assets') if args.stage == 'readonly' else ('quote', 'generate') if args.stage == 'paid' else EXTENDED_OPERATIONS if args.stage == 'extended' else ('account', 'assets', 'quote', 'generate', *EXTENDED_OPERATIONS)
    result = [pack(manifest(operation), args.out / operation) for operation in operations]
    print(json.dumps({'adapter_sha256': adapter_digest(), 'paid_adapter_sha256': paid_digest(), 'extended_adapter_sha256': extended_digest(), 'bundles': result, 'installed': False, 'provider_calls': 0}))

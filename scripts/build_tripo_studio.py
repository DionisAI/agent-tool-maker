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
WORKSPACE_OPERATIONS = ('workspace_inspect', 'workspace_prepare', 'workspace_submit')
WORKSPACE_MODULES = ('model', 'image', 'segment', 'fill_parts', 'retopo', 'smart_uv', 'texture', 'edit', 'upscale', 'pbr', 'rig', 'animate')
WORKSPACE_FILES = (*EXTENDED_FILES, 'workspace.mjs', 'workspace.js')
QUERY_OPERATIONS = ('assets_query', 'image_preview')
QUERY_FILES = ('core.mjs', 'asset-query.mjs', 'asset-query.js')
UI_OPTIONS_OPERATIONS = ('animation_inspect', 'animation_prepare', 'export_options', 'export_prepare')
UI_OPTIONS_FILES = (*WORKSPACE_FILES, 'ui-options.mjs', 'ui-options.js')
VIEWER_OPERATIONS = ('viewer_inspect', 'viewer_prepare', 'viewer_camera', 'hierarchy_prepare', 'hierarchy_transform')
VIEWER_FILES = (*WORKSPACE_FILES, 'viewer.mjs', 'viewer.js')
IMAGE_FORM_OPERATIONS = ('image_form_inspect', 'image_form_prepare')
IMAGE_FORM_FILES = (*WORKSPACE_FILES, 'image-form.mjs', 'image-form.js')
DELIVERY_OPERATIONS = ('texture_quote', 'texture', 'operation_status')
DELIVERY_FILES = (*WORKSPACE_FILES, 'delivery.mjs', 'delivery.js')


def delivery_manifest(operation):
    if operation not in DELIVERY_OPERATIONS:
        raise ValueError('Unknown Tripo delivery operation')
    h = hashlib.sha256()
    for name in DELIVERY_FILES:
        path = ROOT/'examples/opencli/tripo-studio'/name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Delivery sources must be regular reviewed files')
        h.update((name+'\0').encode())
        h.update(path.read_bytes())
        h.update(b'\0')
    properties = {}
    argv = ['__opencli_shim', 'tripo-studio', operation.replace('_', '-'), '--pin', h.hexdigest(), '-f', 'json']
    if operation in ('texture_quote', 'texture'):
        properties['asset_id'] = {'type': 'string', 'pattern': '^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$'}
        argv += ['--asset', {'input': 'asset_id'}]
    if operation == 'texture_quote':
        properties['settings'] = {'type': 'object', 'properties': {
            'resolution': {'enum': ['2K', '4K', '8K']}, 'prompt': {'type': 'string', 'maxLength': 1000},
            'remove_lighting': {'type': 'boolean'}, 'expected_prompt_sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}}, 'additionalProperties': False}
        argv += ['--settings', {'json': 'settings'}]
    else:
        properties['request_key'] = {'type': 'string', 'pattern': '^[A-Za-z0-9_.:-]{1,160}$'}
        argv += ['--key', {'input': 'request_key'}, '--ledger', {'workspace': ''}]
    if operation == 'texture':
        properties.update(quote_sha256={'type': 'string', 'pattern': '^[a-f0-9]{64}$'},
                          max_credits={'type': 'integer', 'minimum': 1, 'maximum': 10000},
                          human_confirmed={'type': 'boolean', 'const': True})
        argv += ['--quote', {'input': 'quote_sha256'}, '--budget', {'input': 'max_credits'}, '--confirm']
    if operation == 'operation_status':
        properties['wait_seconds'] = {'type': 'integer', 'minimum': 0, 'maximum': 120}
        argv += ['--wait', {'input': 'wait_seconds'}]
    return validate_manifest({'id': 'tripo.studio.'+operation, 'provider': 'tripo', 'title': 'Tripo Studio '+operation,
        'capabilities': ['3d', operation], 'adapter': 'command', 'executable': 'opencliapp', 'paid': operation == 'texture',
        'permissions': ['execute_code'] + ([] if operation == 'operation_status' else ['external_write']),
        'schema': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False},
        'command': {'argv': argv, 'output': 'json', 'timeout': 180}, 'sources': ['https://studio.tripo3d.ai/'],
        'notes': 'Texture is the existing reviewed workspace texture contract, not a new provider backend. Status binds one retained project model receipt and its actual output UUID. Unknown submissions and source-only processing remain unresolved; never release their locks or resubmit.',
        'completion': 'Provider-ready model is separate from a submitted operation and validated export. Texture/rig/retopo quality and positive real paid acceptance remain distinct. No Cookie, token, profile or unrelated receipt reads.'})


def image_form_digest():
    sha = hashlib.sha256()
    for name in IMAGE_FORM_FILES:
        sha.update((name + '\0').encode())
        sha.update((ROOT / 'examples/opencli/tripo-studio' / name).read_bytes())
        sha.update(b'\0')
    return sha.hexdigest()


def image_form_manifest(operation):
    prepare = operation == 'image_form_prepare'
    properties = {'asset_id': {'type': 'string', 'pattern': '^(?:[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})?$'}}
    argv = ['__opencli_shim', 'tripo-studio', operation.replace('_', '-'), '--pin', image_form_digest(), '-f', 'json', '--asset', {'input': 'asset_id'}]
    if prepare:
        fields = {'model': {'enum': ['GPT Image 2', 'GPT Image 2.5', 'Nano Banana Pro', 'Nano Banana 2', 'Nano Banana', 'Midjourney v8.2']},
            'aspect_ratio': {'enum': ['1:1', '16:9', '9:16', '4:3', '3:4', None]},
            'number_images': {'type': 'integer', 'minimum': 1, 'maximum': 4}, 'resolution_4k': {'type': 'boolean'},
            'template': {'enum': ['Character Extraction', 'Head Extraction', 'T Pose', '3D Enhance', 'Character Completion', 'Photo to Figure', 'Asset Extraction', 'Variants', '3D Print-Ready', None]},
            'prompt': {'type': 'string', 'minLength': 0, 'maxLength': 10000},
            'expected_draft_sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}}
        properties['settings'] = {'type': 'object', 'properties': fields, 'required': ['expected_draft_sha256'], 'additionalProperties': False}
        argv += ['--settings', {'json': 'settings'}]
    return validate_manifest({'id': 'tripo.studio.' + operation, 'provider': 'tripo', 'title': 'Tripo Studio ' + operation,
        'capabilities': ['3d', operation], 'adapter': 'command', 'executable': 'opencliapp', 'paid': False,
        'permissions': ['external_write'] if prepare else [],
        'schema': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False},
        'command': {'argv': argv, 'output': 'json', 'timeout': 240}, 'sources': ['https://studio.tripo3d.ai/'],
        'notes': 'Generate Image form only, separate from image-to-3D. Reviewed model/template choices and typed prompt/ratio/count/4K preparation bind the exact inspected draft digest. Ratios may be unselected; Midjourney hides ratio/count/4K controls and reports null. Existing layers are preserved; close only owned choice layers. No upload, generation, history replay, publishing, raw login state or automatic extra credits.',
        'completion': 'Visible draft and available controls are read back, not a paid quote or completed image. Free allowance and detached price text do not establish generation cost. Model changes can hide controls; implicit visible changes are explicit. Configuration may be remembered; restore the approved test draft. Image editing/output acceptance remains separate.'})


def viewer_digest():
    sha = hashlib.sha256()
    for name in VIEWER_FILES:
        sha.update((name + '\0').encode())
        sha.update((ROOT / 'examples/opencli/tripo-studio' / name).read_bytes())
        sha.update(b'\0')
    return sha.hexdigest()


def viewer_manifest(operation):
    properties = {'asset_id': {'type': 'string', 'pattern': '^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$'}}
    argv = ['__opencli_shim', 'tripo-studio', operation.replace('_', '-'), '--pin', viewer_digest(), '-f', 'json', '--asset', {'input': 'asset_id'}]
    if operation == 'viewer_camera':
        properties['action'] = {'enum': ['reset', 'orbit_left', 'orbit_right', 'orbit_up', 'orbit_down', 'pan_left', 'pan_right', 'pan_up', 'pan_down', 'zoom_in', 'zoom_out']}
        argv += ['--action', {'input': 'action'}]
    if operation.startswith('hierarchy_'):
        properties['node_name'] = {'type': 'string', 'minLength': 1, 'maxLength': 256}
        argv += ['--node', {'input': 'node_name'}]
    if operation in ('viewer_prepare', 'hierarchy_prepare', 'hierarchy_transform'):
        if operation == 'viewer_prepare':
            fields = {'render_mode': {'enum': ['solid', 'pbr', 'normal', 'unlit', 'toon', 'sketch', 'hologram']},
                'wireframe': {'type': 'boolean'}, 'grid': {'type': 'boolean'},
                'environment': {'type': 'object', 'properties': {
                    'surrounding': {'enum': ['Beach', 'Desert', 'Forest', 'Interior', 'Night', 'Studio']},
                    'strength': {'type': 'number', 'minimum': 0, 'maximum': 2},
                    'rotation': {'type': 'number', 'minimum': 0, 'maximum': 360},
                    'auto_rotate': {'type': 'boolean'}}, 'additionalProperties': False}}
        elif operation == 'hierarchy_prepare':
            fields = {'select': {'enum': [True]}, 'visible': {'type': 'boolean'}}
        else:
            fields = {key: {'type': 'array', 'minItems': 3, 'maxItems': 3, 'items': {'type': 'number', 'minimum': -1000000, 'maximum': 1000000}} for key in ('position', 'rotation', 'scale')}
            fields['expected_transform_sha256'] = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
        properties['settings'] = {'type': 'object', 'properties': fields, 'additionalProperties': False}
        if operation == 'hierarchy_transform':
            properties['settings']['required'] = ['expected_transform_sha256']
        argv += ['--settings', {'json': 'settings'}]
    return validate_manifest({'id': 'tripo.studio.' + operation, 'provider': 'tripo', 'title': 'Tripo Studio ' + operation,
        'capabilities': ['3d', operation], 'adapter': 'command', 'executable': 'opencliapp', 'paid': False,
        'permissions': [] if operation == 'viewer_inspect' else ['external_write'],
        'schema': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False},
        'command': {'argv': argv, 'output': 'json', 'timeout': 240}, 'sources': ['https://studio.tripo3d.ai/'],
        'notes': 'Visible semantic viewer and hierarchy controls only. Exact model UUID, typed render/environment values, bounded native camera inputs, exact node name and prior transform digest. Preserve existing dialogs and close only owned environment layers. No generation, upload, export, publication, save-button click or raw authentication.',
        'completion': 'Editor state is read back, not provider persistence, mesh quality or validated files. Camera actions report bounded input dispatched without inventing an engine pose; rendered visual acceptance is separate. Environment/render choices may be remembered. Transform edits may autosave even without a Save-button click; use an explicitly approved test asset. Transforms are two-decimal values within the reviewed magnitude bound. Destructive node menu items are not clicked.'})


def ui_options_digest():
    sha = hashlib.sha256()
    for name in UI_OPTIONS_FILES:
        sha.update((name + '\0').encode())
        sha.update((ROOT / 'examples/opencli/tripo-studio' / name).read_bytes())
        sha.update(b'\0')
    return sha.hexdigest()


def ui_options_manifest(operation):
    prepare = operation.endswith('_prepare')
    properties = {'asset_id': {'type': 'string', 'pattern': '^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$'}}
    argv = ['__opencli_shim', 'tripo-studio', operation.replace('_', '-'), '--pin', ui_options_digest(), '-f', 'json', '--asset', {'input': 'asset_id'}]
    if prepare:
        settings = {'prompt': {'type': 'string', 'minLength': 0, 'maxLength': 1000},
            'duration': {'type': 'integer', 'minimum': 1, 'maximum': 10},
            'expected_prompt_sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}} if operation == 'animation_prepare' else {
            'format': {'enum': ['USD','FBX','OBJ','STL','GLB','3MF']},
            'texture_resolution': {'enum': ['512','1k','2k','4k','8k']},
            'export_skeleton': {'type': 'boolean'}, 'fbx_variant': {'enum': ['Blender','Mixamo','3dsmax']}, 'vertex_colors': {'type': 'boolean'}}
        properties['settings'] = {'type': 'object', 'properties': settings, 'additionalProperties': False}
        argv += ['--settings', {'json': 'settings'}]
    return validate_manifest({'id': 'tripo.studio.' + operation, 'provider': 'tripo', 'title': 'Tripo Studio ' + operation,
        'capabilities': ['3d', operation], 'adapter': 'command', 'executable': 'opencliapp', 'paid': False,
        'permissions': ['external_write'] if prepare else [],
        'schema': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False},
        'command': {'argv': argv, 'output': 'json', 'timeout': 180}, 'sources': ['https://studio.tripo3d.ai/'],
        'notes': 'Visible semantic UI controls only. Exact source UUID, typed settings and actual enabled options. Animation preserves an existing prompt unless replacement binds its digest. Export preserves existing dialogs, opens and closes only its own transient dialog. No generation, preset application, download, upload, publication or raw authentication.',
        'completion': 'Animation form readiness is not a completed motion. Export options are read back before closing the owned dialog; UI may remember settings, so inspect again before any action. No save or export button click, no paid quote or downloaded/validated file. Multi-format output acceptance remains separate.'})


def query_digest():
    sha = hashlib.sha256()
    for name in QUERY_FILES:
        sha.update((name + '\0').encode())
        sha.update((ROOT / 'examples/opencli/tripo-studio' / name).read_bytes())
        sha.update(b'\0')
    return sha.hexdigest()


def query_manifest(operation):
    argv = ['__opencli_shim', 'tripo-studio', operation.replace('_', '-'), '--pin', query_digest(), '-f', 'json']
    if operation == 'assets_query':
        properties = {'category': {'enum': ['Model', 'Image']},
            'ownership': {'enum': ['My Assets', 'Collected', 'Image Assets']},
            'filter': {'enum': ['All', 'Smart Mesh', 'Untextured', 'Textured', 'Rigged', 'multi-views']},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
            'max_pages': {'type': 'integer', 'minimum': 1, 'maximum': 50}}
        argv += ['--category', {'input': 'category'}, '--ownership', {'input': 'ownership'}, '--filter', {'input': 'filter'},
            '--limit', {'input': 'limit'}, '--pages', {'input': 'max_pages'}]
        example = {'category': 'Image', 'ownership': 'Image Assets', 'filter': 'All', 'limit': 100, 'max_pages': 5}
    else:
        uuid = '[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}'
        properties = {'card_id': {'type': 'string', 'pattern': '^(?:image:' + uuid + ':(?:single|[0-9]|[1-9][0-9])|multiview:' + uuid + ')$'},
            'view_index': {'type': 'integer', 'minimum': 0, 'maximum': 3}}
        argv += ['--card', {'input': 'card_id'}, '--view', {'input': 'view_index'}]
        example = None
    return validate_manifest({'id': 'tripo.studio.' + operation, 'provider': 'tripo', 'title': 'Tripo Studio ' + operation,
        'capabilities': ['3d', operation], 'adapter': 'command', 'executable': 'opencliapp', 'paid': False,
        'permissions': [], 'schema': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False},
        **({'example': example} if example is not None else {}),
        'command': {'argv': argv, 'output': 'json', 'timeout': 900}, 'sources': ['https://studio.tripo3d.ai/'],
        'notes': 'Observed DOM only. Model scope and Image scope are checked on each read. Collected has no filter. Image task plus index preserves distinct images; four multiview images are one card. Signed query strings are discarded. Existing dialogs are preserved. No upload, generation, publication or private API.',
        'completion': 'Query is always partial without an observed authoritative end contract. Image preview verifies exact task/index and closes only the preview it opened. Preview metadata and listed actions are not completed generation.'})


def workspace_digest():
    sha = hashlib.sha256()
    for name in WORKSPACE_FILES:
        sha.update((name + '\0').encode())
        sha.update((ROOT / 'examples/opencli/tripo-studio' / name).read_bytes())
        sha.update(b'\0')
    return sha.hexdigest()


def workspace_manifest(operation):
    paid = operation == 'workspace_submit'
    modules = list(WORKSPACE_MODULES) if operation == 'workspace_inspect' else ['segment', 'texture', 'edit', 'upscale', 'pbr']
    uuid_pattern = '[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}'
    properties = {'module': {'enum': modules}, 'asset_id': {'type': 'string', 'pattern': '^' + ('(?:' + uuid_pattern + ')?' if operation == 'workspace_inspect' else uuid_pattern) + '$'}}
    argv = ['__opencli_shim', 'tripo-studio', operation.replace('_', '-'), '--pin', workspace_digest(), '-f', 'json', '--module', {'input': 'module'}, '--asset', {'input': 'asset_id'}]
    if operation == 'workspace_prepare':
        properties['settings'] = {'type': 'object', 'properties': {
            'detail_level': {'enum': ['Simple','Balanced','Detailed']}, 'resolution': {'enum': ['2K','4K','8K']},
            'prompt': {'type': 'string','minLength':0,'maxLength':1000}, 'remove_lighting': {'type':'boolean'},
            'creativity_strength': {'type':'number','minimum':0,'maximum':1},
            'expected_prompt_sha256': {'type':'string','pattern':'^[a-f0-9]{64}$'},
        }, 'additionalProperties': False}
        argv += ['--settings', {'json':'settings'}]
    if paid:
        properties.update(quote_sha256={'type':'string','pattern':'^[a-f0-9]{64}$'},max_credits={'type':'integer','minimum':1,'maximum':10000},
            request_key={'type':'string','pattern':'^[A-Za-z0-9_.:-]{1,160}$'},human_confirmed={'type':'boolean','const':True})
        argv += ['--quote', {'input':'quote_sha256'}, '--budget', {'input':'max_credits'}, '--key', {'input':'request_key'}, '--ledger', {'workspace':''}, '--confirm']
    return validate_manifest({'id':'tripo.studio.'+operation,'provider':'tripo','title':'Tripo Studio '+operation,
        'capabilities':['3d',operation],'adapter':'command','executable':'opencliapp','paid':paid,
        'permissions':[] if operation == 'workspace_inspect' else ['external_write'],
        'schema':{'type':'object','properties':properties,'required':list(properties),'additionalProperties':False},
        **({'example':{'module':'model','asset_id':''}} if operation == 'workspace_inspect' else {}),
        'command':{'argv':argv,'output':'json','timeout':180},'sources':['https://studio.tripo3d.ai/'],
        'notes':'Observed visible workspace form only. No arbitrary selectors, JS, URL, profile or provider replay. Preparation validates typed semantic settings and exact source, preserves drafts unless replacement binds their digest. Paid submissions retain shared uncertainty lock and stable request key. Missing price stays unknown.',
        'completion':'Form inspection/preparation is not submission. Submitted observes provider UI progress or a new asset, not finished model/export. Full UI parity remains separately audited.'})


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
    if operation in DELIVERY_OPERATIONS:
        return delivery_manifest(operation)
    if operation in IMAGE_FORM_OPERATIONS:
        return image_form_manifest(operation)
    if operation in VIEWER_OPERATIONS:
        return viewer_manifest(operation)
    if operation in UI_OPTIONS_OPERATIONS:
        return ui_options_manifest(operation)
    if operation in QUERY_OPERATIONS:
        return query_manifest(operation)
    if operation in WORKSPACE_OPERATIONS:
        return workspace_manifest(operation)
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
    parser.add_argument('--stage', choices=['readonly', 'paid', 'extended', 'workspace', 'asset-query', 'ui-options', 'viewer', 'image-form', 'delivery', 'all'], default='readonly')
    args = parser.parse_args()
    operations = ('account', 'assets') if args.stage == 'readonly' else ('quote', 'generate') if args.stage == 'paid' else EXTENDED_OPERATIONS if args.stage == 'extended' else WORKSPACE_OPERATIONS if args.stage == 'workspace' else QUERY_OPERATIONS if args.stage == 'asset-query' else UI_OPTIONS_OPERATIONS if args.stage == 'ui-options' else VIEWER_OPERATIONS if args.stage == 'viewer' else IMAGE_FORM_OPERATIONS if args.stage == 'image-form' else DELIVERY_OPERATIONS if args.stage == 'delivery' else ('account', 'assets', 'quote', 'generate', *EXTENDED_OPERATIONS, *WORKSPACE_OPERATIONS, *QUERY_OPERATIONS, *UI_OPTIONS_OPERATIONS, *VIEWER_OPERATIONS, *IMAGE_FORM_OPERATIONS, *DELIVERY_OPERATIONS)
    result = [pack(manifest(operation), args.out / operation) for operation in operations]
    print(json.dumps({'adapter_sha256': adapter_digest(), 'paid_adapter_sha256': paid_digest(), 'extended_adapter_sha256': extended_digest(), 'workspace_adapter_sha256': workspace_digest(), 'query_adapter_sha256': query_digest(), 'ui_options_adapter_sha256': ui_options_digest(), 'viewer_adapter_sha256': viewer_digest(), 'image_form_adapter_sha256': image_form_digest(), 'delivery_adapter_sha256': delivery_manifest('operation_status')['command']['argv'][4], 'bundles': result, 'installed': False, 'provider_calls': 0}))

"""Local owner-only extension workshop. No model call, login or tool execution endpoint."""
from __future__ import annotations
import tempfile
from pathlib import Path
from .errors import RouterError
from .maker import validate_manifest, digest, install
from .storage import atomic_write, canonical


def inventory(router):
    from .web_recipe import sessions
    custom = router.state.setting('custom_tools', [])
    return {'custom_tools': [{'id': t['id'], 'title': t['title'], 'adapter': t['adapter'],
                             'sha256': digest(t), 'permissions': t.get('permissions', []),
                             'paid': t.get('paid', False)} for t in custom],
            'credential_slots': sorted(router.state.setting('credential_registry', {})),
            'browser_sessions': sessions(router.state)['sessions'], 'secrets_returned': False}


def inspect(router, manifest):
    tool = validate_manifest(manifest, router.catalog)
    old = next((t for t in router.state.setting('custom_tools', []) if t['id']==tool['id']), None)
    if tool['id'] in router.catalog.tools and old is None:
        raise RouterError('tool_exists', 'Built-in tools cannot be replaced by an extension.')
    return {'id': tool['id'], 'sha256': digest(tool), 'previous_sha256': digest(old) if old else None,
            'action': 'update' if old else 'install', 'adapter': tool['adapter'],
            'permissions': tool['permissions'], 'paid': tool['paid'],
            'origins': tool.get('recipe', {}).get('allowed_origins', [tool['request']['origin']] if 'request' in tool else []),
            'credential_references': sorted({tool.get('credential')} - {None} | set(tool.get('command', {}).get('credential_env', {}).values())),
            'validation': 'schema_only_not_security_audit_or_live_test', 'executed': False}


def mutate(router, path, body):
    from .webapp import fields, flag, text
    from .extensions import declare_credential, update_manifest
    if path == '/api/credentials/declare':
        fields(body, ('name',), ('label','apply'))
        return declare_credential(router,text(body,'name'),label=text(body,'label'),apply=flag(body,'apply'))
    if path not in {'/api/extensions/validate','/api/extensions/install'}:
        raise RouterError('not_found','No model generation, login or execution Web endpoint exists.')
    fields(body, ('manifest',), ('approved_sha256','expected_sha256'))
    summary = inspect(router,body['manifest'])
    if path.endswith('/validate'):
        return summary
    if text(body,'approved_sha256') != summary['sha256']:
        raise RouterError('approval_mismatch','Preview the manifest and approve its exact digest.')
    # Use the same strict core installer as CLI. Input is data, not arbitrary file paths.
    with tempfile.TemporaryDirectory(prefix='atm-extension-') as folder:
        manifest_path=Path(folder)/'manifest.json'
        atomic_write(manifest_path,canonical(body['manifest']).encode())
        if summary['action']=='update':
            return update_manifest(router.state,router.catalog,manifest_path,
                                   approval=summary['sha256'],expected=text(body,'expected_sha256'))
        if text(body,'expected_sha256') is not None:
            raise RouterError('definition_changed','Expected an existing definition, but no custom tool is installed.')
        return install(router.state,router.catalog,manifest_path,summary['sha256'])

"""A rich, FAKE console home for the redesign acceptance tests and screenshots.

Isolated paths only: fake Keys, fake programs (shell scripts), seeded cached records.
No provider, network, OS keyring or real Agent configuration is touched.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.extensions import declare_credential, new_template
from agent_tool_maker.maker import validate_manifest
from agent_tool_maker.onboarding import setup
from agent_tool_maker.quickstart import scope_plan
from agent_tool_maker.secrets_provider import fingerprint
from agent_tool_maker.storage import canonical
from agent_tool_maker.vault import Vault
from agent_tool_maker.web_recipe import save_session

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_subscription_credits import TRIPO, XYQ, definitions, install_tool  # noqa: E402

PASSWORD = 'fake-redesign-console-password'
SECRET = 'FAKE-REDESIGN-KEY-NEVER-SHOWN'
TRIPO_OPS = ('account', 'assets', 'quote', 'generate', 'asset', 'assets_all', 'retopo_quote', 'retopo',
             'rig_quote', 'rig', 'image_quote', 'image_generate', 'export_quote', 'export')
XYQ_OPS = ('account', 'surface', 'form_inspect', 'form_options')


def fake_program(folder, name, body='exit 0'):
    path = folder / name
    path.write_text('#!/bin/sh\n# Fake program for an isolated console fixture.\n' + body + '\n')
    path.chmod(0o700)
    return path


def recipe_tool():
    tool = new_template('fixture.export', 'web', url='https://fixture.example/')
    tool['paid'] = False
    tool['title'] = 'Fixture website export'
    tool['recipe']['session'] = 'fixture-login'
    return validate_manifest(tool)


def job(state, workspace, tool, status, *, age, verification=None, cost=None, cost_status='unknown', artifacts=0, key=None):
    record, _ = state.create_job(tool, {'fixture': uuid.uuid4().hex}, workspace, key)
    state.update_job(record['id'], status, verification=verification, cost_usd=cost, cost_status=cost_status,
                     artifacts=[{'path': 'fixture-%d.bin' % i} for i in range(artifacts)])
    with state.db() as db:
        db.execute('UPDATE jobs SET created=?, updated=? WHERE id=?', (time.time() - age, time.time() - age + 30, record['id']))
    return record['id']


def build(root, *, saved_elevenlabs=False, empty=False, sync=True):
    """Returns paths and ids. `empty` gives a fresh home (no vault, no agents); `sync=False` has no device identity."""
    root = Path(root).resolve()
    home, user, bin_dir, workspace = root / 'atm', root / 'user', root / 'bin', root / 'demo-video'
    for folder in (user, bin_dir, workspace):
        folder.mkdir(parents=True, exist_ok=True)
    fake_program(bin_dir, 'codex')  # Detected on PATH but not registered.
    fake_program(bin_dir, 'blender')
    router = Router(home)
    if empty:
        router.close()
        return {'home': home, 'user': user, 'bin': bin_dir, 'workspace': workspace}
    vault = Vault(router.state, password=PASSWORD)
    vault.init('passphrase')
    router.vault = vault
    now = time.time()
    if saved_elevenlabs:
        vault.put('elevenlabs', SECRET + '-elevenlabs', expires_at=now + 120 * 86400)
    vault.put('tripo', SECRET + '-tripo', expires_at=now + 70 * 86400)
    vault.put('fal', SECRET + '-fal', expires_at=now - 2 * 86400)
    vault.put('firecrawl', SECRET + '-firecrawl')
    # Exa: two devices hold different versions; the register keeps both and pauses its tools.
    summary = {'state': 'conflict', 'expected': hashlib.sha256(b'fixture-exa').hexdigest(),
               'heads': [{'revision': 'a' * 64, 'clock': {}, 'author': 'b' * 64, 'deleted': False, 'expires_at': None, 'created_at': now - 7200},
                         {'revision': 'c' * 64, 'clock': {}, 'author': 'd' * 64, 'deleted': False, 'expires_at': None, 'created_at': now - 3600}]}
    with router.state.db() as db:
        db.execute('INSERT OR REPLACE INTO sync_registers VALUES (?,?,?,?)', ('exa', canonical(summary), b'0' * 12, b'fixture'))
    router.state.set_setting('sync_conflict:exa', True)
    # Website tools that use the owner's Chrome login through OpenCLIApp, plus credits sources.
    tools = definitions(home)
    for op in TRIPO_OPS:
        install_tool(router, TRIPO.manifest(op))
    for op in XYQ_OPS:
        install_tool(router, XYQ.manifest(op))
    for tool_id in ('tripo.server.account', 'higgsfield.subscription.account', 'pippit.cli.credit_balance'):
        install_tool(router, tools[tool_id])
    install_tool(router, recipe_tool())
    for name in ('opencliapp', 'higgsfield', 'xyq', 'ffprobe'):
        bind_cli(router.state, name, str(fake_program(bin_dir, 'fake-' + name)))
    ffmpeg = fake_program(bin_dir, 'fake-ffmpeg')
    bind_cli(router.state, 'ffmpeg', str(ffmpeg))
    router.state.set_setting('cli_hash:ffmpeg', hashlib.sha256(ffmpeg.read_bytes()).hexdigest())
    ffmpeg.write_text(ffmpeg.read_text() + '# updated by a fake upgrade\n')  # Bound, then changed.
    router.state.set_setting('tool_enabled:tripo.studio.generate', False)
    # Linear MCP: a reviewed binding that names a Key that is not saved.
    router.state.set_setting('mcp:linear', {'transport': 'http', 'url': 'https://mcp.linear.example/mcp',
                                            'credential': 'linear', 'env_credentials': {}, 'allow_tools': []})
    # Higgsfield ATM login: ready, keep-login requested, background service failed to load.
    meta = {'status': 'ready', 'expires_at': now + 5 * 3600, 'refreshable': True, 'keep_login': True,
            'last_refresh_at': now - 3600, 'last_error': None, 'login_deadline': None}
    with router.state.db() as db:
        db.execute('INSERT OR REPLACE INTO oauth_connections VALUES (?,?,?,?)',
                   ('higgsfield', canonical(meta), b'0' * 12, b'fixture-not-a-token'))
    router.state.set_setting('oauth_service', {'status': 'load_failed', 'label': 'fixture.atm.oauth'})
    # Cached credits only: nothing is run when the console is viewed.
    router.state.set_setting('credits:tripo_studio', {
        'provider': 'tripo_studio', 'status': 'ok', 'credits': 6396, 'plan': None, 'unit': 'credits',
        'source': 'tripo.studio.account', 'checked_at': now - 7200, 'last_ok_at': now - 7200, 'error': None})
    router.state.set_setting('credits:xyq', {
        'provider': 'xyq', 'status': 'ok', 'credits': 880, 'plan': None, 'unit': 'credits',
        'source': 'pippit.cli.credit_balance', 'checked_at': now - 960, 'last_ok_at': now - 960, 'error': None})
    router.state.set_setting('credits:higgsfield', {
        'provider': 'higgsfield', 'status': 'error', 'credits': 1234567, 'plan': 'pro', 'unit': 'credits',
        'source': 'higgsfield.subscription.account', 'checked_at': now - 3600, 'last_ok_at': now - 3 * 86400,
        'error': {'code': 'login_required', 'message': 'Fixture: log in to the higgsfield program first.'}})
    router.state.set_setting('credits_cycle:tripo_studio', {'day': 15})
    # Records: what Agents ran, including one that needs the owner and one credits refresh.
    job(router.state, workspace, 'tripo.studio.generate', 'submission_unknown', age=3 * 3600, cost=None)
    job(router.state, workspace, 'elevenlabs.web', 'requires_browser', age=2 * 3600, verification='waiting_for_external_execution')
    job(router.state, workspace, 'elevenlabs.tts', 'completed', age=5 * 3600, verification='ffprobe', cost=0.18,
        cost_status='provider_estimate', artifacts=1)
    job(router.state, workspace, 'ffmpeg.probe', 'completed', age=30 * 3600, verification='parsed_json',
        cost_status='local_no_provider_charge')
    job(router.state, workspace, 'fal.generate', 'failed', age=50 * 3600, verification=None)
    job(router.state, workspace, 'xyq.web.account', 'completed', age=960, verification='parsed_json',
        key='credits-xyq-' + uuid.uuid4().hex)
    # Owner-declared Key name; a web login that expired.
    declare_credential(router, 'acme.production', label='Acme 生产环境', apply=True)
    save_session(vault, 'fixture-login', ['https://fixture.example'],
                 {'cookies': [{'name': 'sid', 'value': 'FAKE-SESSION', 'domain': 'fixture.example', 'path': '/',
                               'expires': now + 3600, 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}], 'origins': []},
                 expires_at=now + 3600)
    with router.state.db() as db:
        db.execute('UPDATE browser_sessions SET expires_at=? WHERE name=?', (now - 86400, 'fixture-login'))
    # Claude Code has ATM; Codex is detected on PATH but not installed.
    atm = fake_program(bin_dir, 'atm')
    previous = os.environ.pop('CLAUDE_CONFIG_DIR', None)
    try:
        setup(router, agents=['claude'], executable=str(atm), apply=True, user_home=user)
    finally:
        if previous is not None:
            os.environ['CLAUDE_CONFIG_DIR'] = previous
    # This computer has a sync identity and trusts one other (fake) device for the Tripo Key.
    if sync:
        from agent_tool_maker.storage import State
        from agent_tool_maker.sync import Sync
        local = Sync(vault)
        local.initialize('laptop')
        remote = Sync(Vault(State(root / 'remote'), password=PASSWORD))
        remote.vault.init('passphrase')
        remote.initialize('build-server')
        card = remote.identity()
        local.trust(card, card['id'], send=['tripo'], receive=['tripo'], apply=True)
    # One project the approval window approved earlier.
    grant = uuid.uuid4().hex
    router.state.set_setting('access:' + grant, {
        'id': grant, 'kind': 'project_session', 'agent': 'local-project', 'workspace': str(workspace),
        'credentials': ['firecrawl', 'tripo'], 'tools': [], 'pins': {}, 'exec_rules': [], 'permissions': [],
        'allow_paid': False, 'socket': str(root / 'fixture.sock'), 'client_uid': os.getuid(),
        'created_at': now - 600, 'expires_at': now + 1500, 'revoked': False, 'token_hash': '0' * 64})
    router.close()
    return {'home': home, 'user': user, 'bin': bin_dir, 'workspace': workspace, 'grant': grant}


def pending_request(home, workspace, names=('elevenlabs', 'tripo')):
    """A request the approval window is showing right now (fresh heartbeat). Written right before page load."""
    router = Router(home)
    try:
        plan = scope_plan(router.state, workspace, list(names))
        ident = uuid.uuid4().hex
        now = time.time()
        router.state.set_setting('desktop-request:' + ident, {'id': ident, **plan, 'status': 'needs_unlock',
                                 'created_at': now - 180, 'heartbeat': now, 'approval_sha256': fingerprint(plan)})
        router.state.set_setting('desktop-active:' + hashlib.sha256(str(workspace).encode()).hexdigest()[:24], ident)
        return ident
    finally:
        router.close()


def heartbeat(home, ident):
    router = Router(home)
    try:
        record = router.state.setting('desktop-request:' + ident)
        router.state.set_setting('desktop-request:' + ident, {**record, 'heartbeat': time.time()})
    finally:
        router.close()


if __name__ == '__main__':
    print(json.dumps({k: str(v) for k, v in build(Path(sys.argv[1]), saved_elevenlabs='--saved' in sys.argv).items()}))

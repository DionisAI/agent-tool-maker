"""Local protocol/storage checks. Mock and maintained-verifier evidence are distinct."""
import base64
import hashlib
import json
import os
import struct
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import uuid
import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from agent_tool_maker import passkeys as pk
from agent_tool_maker.errors import RouterError
from agent_tool_maker.quickstart import scope_plan, ready
from agent_tool_maker.quickstart_web import ApprovalWindow
from agent_tool_maker.secrets_provider import fingerprint
from agent_tool_maker.session import status
from agent_tool_maker.storage import State, canonical
from agent_tool_maker.vault import Vault
from agent_tool_maker.webapp import Console

PASSWORD = 'fake-passkey-recovery-20261005'
KEY = 'fake-passkey-slot-not-production'
PRF = hashlib.sha256(b'fake-authenticator-prf').digest()


def cbor(value):
    """Minimal fixture encoder; production uses the maintained verifier parser."""
    def head(major, count):
        if count < 24: return bytes([major * 32 + count])
        if count < 256: return bytes([major * 32 + 24, count])
        return bytes([major * 32 + 25]) + struct.pack('>H', count)
    if isinstance(value, int): return head(0 if value >= 0 else 1, value if value >= 0 else -1-value)
    if isinstance(value, bytes): return head(2,len(value)) + value
    if isinstance(value, str): return head(3,len(value.encode())) + value.encode()
    if isinstance(value, dict): return head(5,len(value)) + b''.join(cbor(k)+cbor(v) for k,v in value.items())
    raise AssertionError('unexpected fixture input')


class Authenticator:
    def __init__(self):
        self.private = ec.generate_private_key(ec.SECP256R1())
        numbers = self.private.public_key().public_numbers()
        self.public = cbor({1:2,3:-7,-1:1,-2:numbers.x.to_bytes(32,'big'),-3:numbers.y.to_bytes(32,'big')})
        self.identifier = os.urandom(32)
        self.counter = 0
        self.user = None

    def response(self, step, origin, *, registration=False, flags=5, rp='localhost', counter=None):
        client = canonical({'type':'webauthn.create' if registration else 'webauthn.get',
            'challenge':step['publicKey']['challenge'],'origin':origin,'crossOrigin':False}).encode()
        if counter is None:
            self.counter += 1
            counter = self.counter
        auth = hashlib.sha256(rp.encode()).digest() + bytes([flags | (64 if registration else 0)]) + struct.pack('>I',counter)
        response = {'clientDataJSON':pk.encode(client)}
        if registration:
            self.user = step['publicKey']['user']['id']
            auth += bytes(16) + struct.pack('>H',len(self.identifier)) + self.identifier + self.public
            response['attestationObject'] = pk.encode(cbor({'fmt':'none','authData':auth,'attStmt':{}}))
        else:
            response.update(authenticatorData=pk.encode(auth), signature=pk.encode(self.private.sign(
                auth + hashlib.sha256(client).digest(),ec.ECDSA(hashes.SHA256()))),userHandle=self.user)
        return {'ceremony_id':step['ceremony_id'], 'credential':{'id':pk.encode(self.identifier),
            'rawId':pk.encode(self.identifier),'type':'public-key','response':response,'clientExtensionResults':{}}}

    def proof(self, step, origin, **kw):
        return {**self.response(step, origin, **kw), 'prf_first':pk.encode(PRF)}


@pytest.fixture(params=['mock','real'])
def verifier(request, monkeypatch):
    if request.param == 'real':
        pytest.importorskip('webauthn', reason='Reviewed dependency installation pending; real verification distinct from mocks')
        return 'real'
    def registration(**kw):
        assert kw['require_user_verification'] is True
        return SimpleNamespace(credential_id=request.node.auth.identifier,
            credential_public_key=request.node.auth.public,sign_count=request.node.auth.counter)
    def authentication(**kw):
        assert kw['require_user_verification'] is True
        return SimpleNamespace(new_sign_count=request.node.auth.counter)
    fake = SimpleNamespace(verify_registration_response=registration,verify_authentication_response=authentication)
    monkeypatch.setattr(pk,'library',lambda:(fake,SimpleNamespace(ECDSA_SHA_256=-7)))
    return 'mock'


@pytest.fixture
def local(tmp_path, verifier, request):
    state=State(tmp_path/'state')
    vault=Vault(state,password=PASSWORD);vault.init('passphrase');vault.put('fal',KEY)
    auth=Authenticator();request.node.auth=auth
    manager=pk.Passkeys(state,'http://localhost:34567')
    try: yield manager,vault,auth
    finally: manager.clear()


def enroll(manager, vault, auth):
    step=manager.register_begin(vault,'fixture')
    bind=manager.register_verify(auth.response(step,manager.origin,registration=True))
    result=manager.register_finish(auth.proof(bind,manager.origin))
    assert result['status']=='registered'
    return pk.encode(auth.identifier)


def snapshot(state):
    with state.db() as db: return state.setting('vault'),db.execute('SELECT * FROM secrets ORDER BY name').fetchall()


def test_roundtrip_ciphertexts_recovery_restart_metadata(local):
    manager,vault,auth=local;before=snapshot(vault.state)
    identifier=enroll(manager,vault,auth);restarted=pk.Passkeys(vault.state,manager.origin);locked=Vault(vault.state)
    try:
        step=restarted.auth_begin(identifier,'console.unlock')
        restarted.auth_finish(locked,auth.proof(step,restarted.origin),'console.unlock')
        assert locked.get('fal')==KEY and snapshot(vault.state)==before
        assert Vault(vault.state,password=PASSWORD).get('fal')==KEY
        assert vault.state.setting(pk.SETTING)[0]['sign_count']==auth.counter
        visible=canonical(restarted.status())
        for secret in [KEY,PASSWORD,pk.encode(PRF),pk.encode(locked._key),'wrapped_key','public_key']:assert secret not in visible
        persisted=canonical(vault.state.setting(pk.SETTING))
        assert pk.encode(PRF) not in persisted and pk.encode(locked._key) not in persisted
    finally: restarted.clear()


@pytest.mark.parametrize('change,error',[
    ('wrong_prf','passkey_unwrap_failed'),('missing_prf','invalid_passkey'),
    ('origin','passkey_binding'),('challenge','passkey_binding'),('cross_origin','passkey_binding'),
    ('top_origin','passkey_binding'),('type','passkey_binding'),('user','passkey_binding'),
    ('ceremony','passkey_binding'),('intent','passkey_binding'),('credential','passkey_binding'),('expiry','passkey_expired')])
def test_failed_proof_never_unlocks_and_single_use(local,change,error):
    manager,vault,auth=local;identifier=enroll(manager,vault,auth)
    step=manager.auth_begin(identifier,'console.unlock');body=auth.proof(step,manager.origin)
    if change in {'origin','challenge','cross_origin','top_origin','type'}:
        client=json.loads(pk.decode(body['credential']['response']['clientDataJSON']))
        field={'cross_origin':'crossOrigin','top_origin':'topOrigin'}.get(change,change)
        client[field]={'origin':'http://localhost:1','challenge':pk.encode(b'x'*32),'cross_origin':True,'top_origin':manager.origin,'type':'webauthn.create'}[change]
        body['credential']['response']['clientDataJSON']=pk.encode(canonical(client).encode())
    elif change=='wrong_prf':body['prf_first']=pk.encode(b'x'*32)
    elif change=='missing_prf':body.pop('prf_first')
    elif change=='user':body['credential']['response']['userHandle']=pk.encode(b'x'*32)
    elif change=='credential':body['credential']['id']=body['credential']['rawId']=pk.encode(b'x'*32)
    elif change=='ceremony':body['ceremony_id']='wrong'
    elif change=='expiry':manager.pending['expires']=time.monotonic()-1
    locked=Vault(vault.state)
    with pytest.raises(RouterError) as failure:manager.auth_finish(locked,body,'wrong' if change=='intent' else 'console.unlock')
    assert failure.value.code==error and locked._key is None
    with pytest.raises(RouterError) as replay:manager.auth_finish(locked,body,'console.unlock')
    assert replay.value.code=='passkey_expired'


def test_disable_recovery_and_inflight_cas(local):
    manager,vault,auth=local;identifier=enroll(manager,vault,auth)
    step=manager.auth_begin(identifier,'console.unlock');body=auth.proof(step,manager.origin)
    with pytest.raises(RouterError):manager.disable(Vault(vault.state,password='wrong'),identifier)
    manager.disable(Vault(vault.state,password=PASSWORD),identifier)
    with pytest.raises(RouterError) as failure:manager.auth_finish(Vault(vault.state),body,'console.unlock')
    assert failure.value.code=='state_changed' and manager.status()['registered']==0
    assert len(vault.state.setting(pk.SETTING))==1
    with pytest.raises(RouterError):manager.auth_begin(identifier,'console.unlock')


def test_legacy_marker_and_wrong_unwrapped_key(local):
    manager,vault,auth=local;cfg=vault.state.setting('vault')
    cfg['check']=base64.b64encode(AESGCM(vault.unlock()).encrypt(base64.b64decode(cfg['check_nonce']),b'ATR-v1',b'vault-check')).decode()
    vault.state.set_setting('vault',cfg);identifier=enroll(manager,vault,auth);locked=Vault(vault.state)
    manager.auth_finish(locked,auth.proof(manager.auth_begin(identifier,'test'),manager.origin),'test')
    assert locked.get('fal')==KEY
    with pytest.raises(RouterError) as e:Vault(vault.state).unlock_with_key(b'x'*32)
    assert e.value.code=='passkey_vault_mismatch'


def test_timeout_and_cancel_drop_master_reference(local,monkeypatch):
    manager,vault,auth=local;monkeypatch.setattr(pk,'TTL',.05)
    step=manager.register_begin(vault,'fixture');pending=manager.pending
    assert pending['master']==vault.unlock();time.sleep(.1)
    assert manager.pending is None and 'master' not in pending
    with pytest.raises(RouterError):manager.register_verify(auth.response(step,manager.origin,registration=True))
    manager.register_begin(vault,'fixture');pending=manager.pending;manager.clear()
    assert manager.pending is None and 'master' not in pending


def test_registration_cas_and_fixed_deadline(local):
    manager,vault,auth=local;step=manager.register_begin(vault,'fixture');deadline=manager.pending['expires']
    with pytest.raises(RouterError) as e:manager.register_begin(vault,'other')
    assert e.value.code=='passkey_busy'
    bind=manager.register_verify(auth.response(step,manager.origin,registration=True))
    assert manager.pending['expires']==deadline
    vault.state.set_setting(pk.SETTING,[{'changed':True}])
    with pytest.raises(RouterError) as e:manager.register_finish(auth.proof(bind,manager.origin))
    assert e.value.code=='state_changed'


def test_passkey_binding_excluded_from_real_sync_packet(local,tmp_path):
    from agent_tool_maker.sync import Sync
    manager,vault,auth=local;enroll(manager,vault,auth)
    remote=Vault(State(tmp_path/'remote'),password='distinct-remote-recovery-only');remote.init('passphrase')
    sender,receiver=Sync(vault),Sync(remote);sender.initialize('laptop');receiver.initialize('server')
    sender.trust(receiver.identity(),receiver.identity()['id'],send=['fal'],receive=[],apply=True)
    receiver.trust(sender.identity(),sender.identity()['id'],send=[],receive=['fal'],apply=True)
    before=remote.state.setting('vault')
    receiver.import_packet(sender.export_packet(receiver.identity()['id']),apply=True)
    assert remote.get('fal')==KEY and remote.unlock()!=vault.unlock()
    assert remote.state.setting('vault')==before and remote.state.setting(pk.SETTING) is None
    assert vault.state.setting(pk.SETTING)


def test_corrupt_records_visible_but_password_recovery_preserved(local):
    manager,vault,auth=local;enroll(manager,vault,auth)
    vault.state.set_setting(pk.SETTING,[{'id':'bad'}])
    visible=manager.status()
    assert visible['available'] is False and visible['state_error']['code']=='passkey_state_invalid'
    assert Vault(vault.state,password=PASSWORD).get('fal')==KEY
    with pytest.raises(RouterError) as e:manager.auth_begin('bad','test')
    assert e.value.code=='passkey_state_invalid'


def test_dependency_missing_and_ip_origin(tmp_path,monkeypatch):
    import builtins
    original=builtins.__import__
    def absent(name,*args,**kw):
        if name=='webauthn':raise ImportError('fixture missing')
        return original(name,*args,**kw)
    monkeypatch.setattr(builtins,'__import__',absent)
    with pytest.raises(RouterError) as e:pk.library()
    assert e.value.code=='passkey_dependency_missing'
    manager=pk.Passkeys(State(tmp_path/'state'),'http://127.0.0.1:1234')
    with pytest.raises(RouterError) as e:manager._ready()
    assert e.value.code=='passkey_origin'


@pytest.mark.parametrize('failure',['signature','rp','uv','presence','counter'])
def test_real_verifier_cryptographic_failures(local,verifier,failure):
    if verifier=='mock':pytest.skip('Signature checks require maintained verifier, not a mock')
    manager,vault,auth=local;identifier=enroll(manager,vault,auth);step=manager.auth_begin(identifier,'test')
    kw={'rp':'evil.example'} if failure=='rp' else {'flags':1} if failure=='uv' else {'flags':4} if failure=='presence' else {'counter':0} if failure=='counter' else {}
    body=auth.proof(step,manager.origin,**kw)
    if failure=='signature':body['credential']['response']['signature']=pk.encode(b'x'*64)
    locked=Vault(vault.state)
    with pytest.raises(RouterError) as e:manager.auth_finish(locked,body,'test')
    assert e.value.code=='passkey_verification' and locked._key is None


@pytest.fixture
def http_console(local):
    manager,vault,auth=local;server=Console(vault.state.home,localhost=True)
    manager.origin=server.origin;server.passkeys=manager
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=httpx.Client(base_url=server.origin,headers={'Authorization':'Bearer '+server.token,'Origin':server.origin},trust_env=False)
    try:yield manager,vault,auth,server,client
    finally:client.close();server.shutdown();server.server_close();thread.join(5)


def http_enroll(client,manager,auth):
    step=client.post('/api/passkeys/register/begin',json={'passphrase':PASSWORD,'label':'fixture'}).json()
    assert 'publicKey' in step,step
    bind=client.post('/api/passkeys/register/verify',json=auth.response(step,manager.origin,registration=True)).json()
    assert 'publicKey' in bind,bind
    result=client.post('/api/passkeys/register/finish',json=auth.proof(bind,manager.origin))
    assert result.status_code==200,result.text
    return pk.encode(auth.identifier)


def test_http_enrollment_unlock_lease_and_gates(http_console):
    manager,vault,auth,server,client=http_console;identifier=http_enroll(client,manager,auth)
    assert client.get('/api/passkeys',headers={'Authorization':'Bearer wrong'}).status_code==401
    assert client.post('/api/passkeys/auth/begin',json={'credential_id':identifier},headers={'Origin':'http://localhost:1'}).status_code==403
    assert client.get('/api/passkeys',headers={'Host':'127.0.0.1:'+str(server.server_port)}).status_code==403
    step=client.post('/api/passkeys/auth/begin',json={'credential_id':identifier}).json();proof=auth.proof(step,server.origin)
    result=client.post('/api/session/unlock',json={'passkey':proof});assert result.status_code==200,result.text
    before=status(vault.state.home)['seconds_remaining'];assert 1700<before<=1800
    same=client.post('/api/session/unlock',json={'passkey':proof}).json()
    assert same['action']=='unchanged' and same['seconds_remaining']<=before
    assert client.post('/api/session/lock',json={}).status_code==200
    step=client.post('/api/passkeys/auth/begin',json={'credential_id':identifier}).json()
    result=client.post('/api/session/unlock',json={'passkey':auth.proof(step,server.origin),'ttl':'1h'})
    assert result.status_code==400 and not status(vault.state.home)['unlocked']
    assert client.post('/api/session/unlock',json={'passphrase':PASSWORD}).status_code==200


def test_project_scope_and_real_program_injection(local,tmp_path):
    manager,vault,auth=local;identifier=enroll(manager,vault,auth)
    workspace=tmp_path/'project';workspace.mkdir();(workspace/'probe.py').write_text('import os;print("PRESENT",bool(os.environ.get("FAL_KEY")))')
    plan=scope_plan(vault.state,workspace,['fal']);rid=uuid.uuid4().hex
    vault.state.set_setting('desktop-request:'+rid,{'id':rid,**plan,'status':'needs_unlock','created_at':time.time(),'approval_sha256':fingerprint(plan)})
    server=ApprovalWindow(vault.state.home,rid,localhost=True);server.passkeys=manager;manager.origin=server.origin
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with httpx.Client(base_url=server.origin,headers={'Authorization':'Bearer '+server.token,'Origin':server.origin},trust_env=False) as client:
            scope={'approved_sha256':fingerprint(plan),'consent':True}
            assert client.post('/api/desktop/passkey/begin',json={**scope,'approved_sha256':'wrong','credential_id':identifier}).status_code==400
            step=client.post('/api/desktop/passkey/begin',json={**scope,'credential_id':identifier}).json();proof=auth.proof(step,server.origin)
            bad=client.post('/api/desktop/approve',json={**scope,'passkey':proof,'credentials':{'tripo':'fake-extra'}})
            assert bad.status_code==400 and not status(vault.state.home)['unlocked']
            result=client.post('/api/desktop/approve',json={**scope,'passkey':proof,'credentials':{}})
            assert result.status_code==200,result.text
            assert ready(vault.state,workspace,['fal'])['status']=='ready' and ready(vault.state,tmp_path,['fal']) is None
            for run in range(2):
                child=subprocess.run([sys.executable,'-m','agent_tool_maker','--home',str(vault.state.home),'use',
                    '--workspace',str(workspace),'--env','FAL_KEY=atm://fal','--request-key','passkey-'+str(run),'--',sys.executable,'probe.py'],
                    env={k:v for k,v in os.environ.items() if k not in {'ATM_VAULT_PASSWORD','FAL_KEY'}},capture_output=True,text=True,timeout=20)
                assert child.returncode==0,child.stdout+child.stderr
                assert json.loads(child.stdout)['stdout'].strip()=='PRESENT True'
                assert KEY not in child.stdout and PASSWORD not in child.stdout
            assert client.post('/api/passkeys/register/begin',json={}).status_code==404
            assert client.post('/api/desktop/lock',json={}).status_code==200
            assert not status(vault.state.home)['unlocked']
    finally:server.shutdown();server.server_close();thread.join(5)

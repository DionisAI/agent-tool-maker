"""Native HTTP/CSP/WebAuthn-PRF with isolated Chrome virtual authenticator, not 1Password."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid
import pytest
from agent_tool_maker.quickstart import scope_plan, ready
from agent_tool_maker.quickstart_web import ApprovalWindow
from agent_tool_maker.secrets_provider import fingerprint
from agent_tool_maker.session import status
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault
from agent_tool_maker.webapp import Console
from agent_tool_maker.passkeys import SETTING

PASSWORD='fake-browser-passkey-recovery'
KEY='fake-browser-passkey-only'


def virtual(context,page,*,prf=True):
    cdp=context.new_cdp_session(page);cdp.send('WebAuthn.enable')
    authenticator=cdp.send('WebAuthn.addVirtualAuthenticator',{'options':{
        'protocol':'ctap2','ctap2Version':'ctap2_1','transport':'internal',
        'hasResidentKey':True,'hasUserVerification':True,'isUserVerified':True,
        'automaticPresenceSimulation':True,'hasPrf':prf}})['authenticatorId']
    return cdp,authenticator


@pytest.mark.browser
@pytest.mark.parametrize('plain_array',[False,True],ids=['native-buffer','extension-array-shape'])
def test_native_prf_enrollment_management_and_project_unlock(tmp_path,plain_array):
    pytest.importorskip('webauthn',reason='Reviewed passkey dependency required for native crypto acceptance')
    from playwright.sync_api import sync_playwright,expect
    chrome=os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not chrome:pytest.skip('Native Chromium path not supplied')
    state=State(tmp_path/'state');vault=Vault(state,password=PASSWORD);vault.init('passphrase');vault.put('fal',KEY)
    with state.db() as db:before=db.execute('SELECT * FROM secrets').fetchall()
    server=Console(state.home,localhost=True,user_home=tmp_path/'user')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    approval=None;approval_thread=None
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=chrome,headless=True)
            context=browser.new_context(viewport={'width':1300,'height':1000})
            if plain_array:
                # Simulate only the reported extension return representation.
                # The authenticator, signatures, PRF and HTTP remain native.
                context.add_init_script("""(() => {
                  const original=PublicKeyCredential.prototype.getClientExtensionResults;
                  PublicKeyCredential.prototype.getClientExtensionResults=function(){
                    const result=original.call(this),first=result.prf?.results?.first;
                    if(first)result.prf.results.first=Array.from(new Uint8Array(first));
                    return result;
                  };
                })();""")
            page=context.new_page();page.set_default_timeout(15000);expect.set_options(timeout=15000)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            failures=[]
            requests=[]
            def request_failed(request):
                failures.append({'path':request.url.split('/api/',1)[-1].split('#',1)[0], 'transport':request.failure})
            page.on('requestfailed',request_failed)
            def response_failure(response):
                if '/api/' in response.url:
                    requests.append({'path':response.url.split('/api/',1)[1],'status':response.status})
                if '/api/' in response.url and response.status >= 400:
                    failures.append({'path':response.url.split('/api/',1)[1],'status':response.status,'error':response.json().get('error')})
            page.on('response',response_failure)
            cdp,identifier=virtual(context,page)
            page.goto(server.origin+'/#token='+server.token)
            page.get_by_role('heading',name='开始使用 ATM').wait_for()
            page.get_by_role('button',name='设置',exact=True).click()
            page.get_by_role('button',name='绑定 Passkey',exact=True).click()
            page.get_by_label('ATM 主密码（首次绑定需要验证）',exact=True).fill(PASSWORD)
            page.get_by_role('button',name='开始绑定',exact=True).click()
            expect(page.locator('#modal')).not_to_be_visible()
            try: expect(page.locator('#passkeys-panel')).to_contain_text('1Password · 已绑定')
            except AssertionError:
                pytest.fail('Passkey enrollment failed: '+json.dumps(failures)+'; toast='+page.locator('#toast').inner_text()+'; registered='+str(bool(state.setting(SETTING))))
            assert state.setting(SETTING) and not status(state.home)['unlocked']
            assert not page.locator('input[type=password]').evaluate_all('xs=>xs.some(x=>x.value)')
            page.get_by_role('button',name='首页',exact=True).click()
            page.get_by_role('button',name='解锁 30 分钟',exact=True).click()
            page.get_by_role('button',name='用 Passkey 解锁 30 分钟',exact=True).click()
            try: expect(page.locator('#credential-session')).to_contain_text('已解锁')
            except AssertionError:
                pytest.fail('Passkey unlock failed: '+json.dumps(failures)+'; toast='+page.locator('#toast').inner_text()+'; responses='+json.dumps(requests))
            assert 1700<status(state.home)['seconds_remaining']<=1800
            page.get_by_role('button',name='立即锁定',exact=True).click()
            expect(page.locator('#credential-session')).to_contain_text('已锁定')
            workspace=tmp_path/'project';workspace.mkdir()
            (workspace/'probe.py').write_text('import os;print("PRESENT",bool(os.environ.get("FAL_KEY")))')
            plan=scope_plan(state,workspace,['fal']);rid=uuid.uuid4().hex
            state.set_setting('desktop-request:'+rid,{'id':rid,**plan,'status':'needs_unlock','created_at':time.time(),'approval_sha256':fingerprint(plan)})
            approval=ApprovalWindow(state.home,rid,localhost=True)
            approval_thread=threading.Thread(target=approval.serve_forever,daemon=True);approval_thread.start()
            # Same browser authenticator, different process window/port; exact Origin bound per challenge.
            page.goto(approval.origin+'/#token='+approval.token)
            page.get_by_role('button',name='用 Passkey 解锁并继续',exact=True).click()
            page.get_by_role('heading',name='已解锁，交给 Agent。').wait_for()
            assert ready(state,workspace,['fal'])['status']=='ready'
            assert ready(state,tmp_path,['fal']) is None
            for run in range(2):
                child=subprocess.run([sys.executable,'-m','agent_tool_maker','--home',str(state.home),'use',
                    '--workspace',str(workspace),'--env','FAL_KEY=atm://fal','--request-key','browser-passkey-'+str(run),
                    '--',sys.executable,'probe.py'],env={k:v for k,v in os.environ.items() if k not in {'ATM_VAULT_PASSWORD','FAL_KEY'}},
                    capture_output=True,text=True,timeout=20)
                assert child.returncode==0,child.stdout+child.stderr
                assert json.loads(child.stdout)['stdout'].strip()=='PRESENT True' and KEY not in child.stdout
            page.get_by_role('button',name='立即锁定所有项目',exact=True).click()
            expect(page.locator('#error')).to_contain_text('已锁定')
            assert not status(state.home)['unlocked']
            # Original recovery route and persisted binding survive a new console request.
            page.goto(server.origin+'/#token='+server.token)
            page.get_by_role('button',name='解锁 30 分钟',exact=True).click()
            page.get_by_label('ATM 主密码',exact=True).fill(PASSWORD)
            page.get_by_role('button',name='用主密码解锁',exact=True).click()
            expect(page.locator('#credential-session')).to_contain_text('已解锁')
            with state.db() as db:assert db.execute('SELECT * FROM secrets').fetchall()==before
            assert not errors,errors
            browser.close()
    except BaseException as error:
        error.add_note('Native transport diagnostics: '+json.dumps({'failures':locals().get('failures',[]),'responses':locals().get('requests',[])}))
        raise
    finally:
        if approval:approval.shutdown();approval.server_close();approval_thread.join(5)
        server.shutdown();server.server_close();thread.join(5)


@pytest.mark.browser
def test_native_missing_prf_does_not_persist_binding(tmp_path):
    pytest.importorskip('webauthn',reason='Reviewed passkey dependency required')
    from playwright.sync_api import sync_playwright,expect
    chrome=os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not chrome:pytest.skip('Native Chromium path not supplied')
    state=State(tmp_path/'state');vault=Vault(state,password=PASSWORD);vault.init('passphrase')
    server=Console(state.home,localhost=True,user_home=tmp_path/'user')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=chrome,headless=True)
            context=browser.new_context();page=context.new_page();expect.set_options(timeout=15000)
            cdp,identifier=virtual(context,page,prf=False)
            page.goto(server.origin+'/#token='+server.token)
            page.get_by_role('button',name='设置',exact=True).click()
            page.get_by_role('button',name='绑定 Passkey',exact=True).click()
            page.get_by_label('ATM 主密码（首次绑定需要验证）',exact=True).fill(PASSWORD)
            page.get_by_role('button',name='开始绑定',exact=True).click()
            expect(page.locator('#modal-alert')).to_contain_text('passkey_prf_missing')  # Stays inside the dialog.
            assert state.setting(SETTING) is None and server.passkeys.pending is None
            assert not status(state.home)['unlocked']
            assert Vault(state,password=PASSWORD).unlock()
            assert page.get_by_label('ATM 主密码（首次绑定需要验证）',exact=True).input_value()==''
            browser.close()
    finally:server.shutdown();server.server_close();thread.join(5)


@pytest.mark.browser
def test_native_keyring_modal_omits_absent_password_node(tmp_path):
    """Rendering acceptance with an in-memory fake keyring, not native Keychain."""
    # The bind entry is disabled without the verifier, so the modal is unreachable.
    pytest.importorskip('webauthn',reason='Reviewed passkey dependency required')
    from playwright.sync_api import sync_playwright,expect
    from agent_tool_maker.engine import Router
    chrome=os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not chrome:pytest.skip('Native Chromium path not supplied')
    class FakeKeyring:
        def __init__(self):self.values={}
        def set_password(self,service,account,value):self.values[(service,account)]=value
        def get_password(self,service,account):return self.values.get((service,account))
    state=State(tmp_path/'state');keyring=FakeKeyring()
    Vault(state,keyring_backend=keyring).init('keyring')
    def router_factory(password=None):return Router(state.home,vault=Vault(state,keyring_backend=keyring))
    server=Console(state.home,localhost=True,user_home=tmp_path/'user',router_factory=router_factory)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=chrome,headless=True)
            page=browser.new_page()
            page.goto(server.origin+'/#token='+server.token)
            page.get_by_role('button',name='设置',exact=True).click()
            page.get_by_role('button',name='绑定 Passkey',exact=True).click()
            expect(page.locator('#modal-body')).not_to_contain_text('null')
            expect(page.locator('#modal-body input[type=password]')).to_have_count(0)
            expect(page.get_by_role('button',name='开始绑定',exact=True)).to_be_enabled()
            assert state.setting(SETTING) is None and not status(state.home)['unlocked']
            browser.close()
    finally:server.shutdown();server.server_close();thread.join(5)

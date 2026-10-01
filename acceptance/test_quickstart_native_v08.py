"""Native localhost/CSP acceptance. No navigation bridge or policy bypass."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import pytest
from agent_tool_maker.engine import Router
from agent_tool_maker.quickstart import scope_plan
from agent_tool_maker.quickstart_web import ApprovalWindow
from agent_tool_maker.secrets_provider import fingerprint
from agent_tool_maker.vault import Vault


def test_one_local_password_window_then_two_fresh_clients():
    from playwright.sync_api import sync_playwright, expect
    with tempfile.TemporaryDirectory(prefix='native8-') as td:
        root=Path(td).resolve();r=Router(root/'s');password='fake-native-08-password'
        r.vault=Vault(r.state,password=password);r.vault.init('passphrase');r.vault.put('fal','fake-native08-key')
        w=root/'project';w.mkdir();(w/'app.py').write_text('import os;print("OK",bool(os.environ["FAL_KEY"]))')
        plan=scope_plan(r.state,w,['fal']);identifier=uuid.uuid4().hex
        r.state.set_setting('desktop-request:'+identifier,{'id':identifier,**plan,'status':'needs_unlock',
                         'created_at':time.time(),'approval_sha256':fingerprint(plan)})
        ui=ApprovalWindow(r.state.home,identifier);thread=threading.Thread(target=ui.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=os.environ.get('ATM_CHROMIUM') or pw.chromium.executable_path,headless=True)
                page=browser.new_page(viewport={'width':1100,'height':1000})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                response=page.goto(ui.origin+'/#token='+ui.token)
                assert response.status==200
                assert "script-src 'self'" in response.headers['content-security-policy']
                expect(page.get_by_role('heading',name='解锁一次，Agent 继续。')).to_be_visible()
                expect(page.locator('#workspace')).to_have_text(str(w))
                page.get_by_label('ATM 主密码',exact=True).fill(password)
                page.get_by_role('button',name='解锁并继续',exact=True).click()
                expect(page.get_by_role('heading',name='已解锁，交给 Agent。')).to_be_visible()
                assert password not in page.content() and 'fake-native08-key' not in page.content()
                assert page.locator('input[type=password]').count()==0
                for i in range(2):
                    p=subprocess.run([sys.executable,'-m','agent_tool_maker','--home',str(r.state.home),'use',
                        '--workspace',str(w),'--env','FAL_KEY=atm://fal','--request-key','native-'+str(i),'--',sys.executable,'app.py'],
                        stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=20)
                    assert p.returncode==0,p.stdout+p.stderr
                    assert json.loads(p.stdout)['stdout']=='OK True\n'
                # Refresh does not demand manual copy/paste of a hidden token.
                page.reload();expect(page.get_by_role('heading',name='已解锁，交给 Agent。')).to_be_visible()
                page.get_by_role('button',name='立即锁定所有项目').click()
                expect(page.get_by_role('alert')).to_contain_text('已锁定')
                assert not errors,errors
                browser.close()
        finally:
            ui.shutdown();ui.server_close();thread.join(5);r.close()

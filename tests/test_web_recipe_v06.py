"""Actual Chromium DOM/downloads via an explicit in-memory test page adapter.
Native navigation is separately provided in acceptance, not claimed here.
"""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import time

import pytest
from agent_tool_maker.errors import RouterError
from agent_tool_maker.extensions import new_template
from agent_tool_maker.maker import validate_manifest
from agent_tool_maker.web_recipe import (validate_recipe,save_session,load_session,sessions,remove_session,execute_web,login,health)
from agent_tool_maker.storage import canonical, State
from agent_tool_maker.vault import Vault
from agent_tool_maker.sync import Sync
from test_browser_integration import chromium


def recipe_tool():
    t=new_template('fixture.export','web',url='https://fixture.example/')
    t['paid']=False
    t['schema']={'type':'object','properties':{'text':{'type':'string','maxLength':200}},'required':['text'],'additionalProperties':False}
    t['recipe'].update(timeout_ms=1000,steps=[
        {'op':'fill','target':{'label':'Message'},'value':{'input':'text'}},
        {'op':'click','target':{'role':'button','name':'Create file'}},
        {'op':'expect_text','target':{'css':'#state'},'value':'completed'},
        {'op':'extract','target':{'css':'#state'},'name':'state'},
        {'op':'download','target':{'role':'link','name':'Download result'},'filename':'output.txt'}])
    return validate_manifest(t)


HTML='''<!doctype html><html><body><label>Message<input id="message"></label><button id="create">Create file</button><p id="state">idle</p><script>
let count=0;document.querySelector('#create').onclick=()=>{count++;document.querySelector('#state').textContent='completed';let a=document.createElement('a');a.textContent='Download result';a.download='result.txt';a.href=URL.createObjectURL(new Blob([document.querySelector('#message').value],{type:'text/plain'}));document.body.append(a);fetch('https://unapproved.example/tracker').catch(()=>{});};
</script></body></html>'''


def storage():
    return {'cookies':[{'name':'auth','value':'FAKE-browser-session-secret','domain':'fixture.example','path':'/','expires':time.time()+3600,'httpOnly':True,'secure':True,'sameSite':'Lax'}],
            'origins':[{'origin':'https://fixture.example','localStorage':[{'name':'token','value':'FAKE-local-storage-secret'}]}]}


@pytest.mark.parametrize('mutate',[
 lambda r:r.update(allowed_origins=['https://fixture.example/']),
 lambda r:r.update(allowed_origins=['https://*.example']),
 lambda r:r.update(allowed_origins=[{}]),
 lambda r:r.update(start_url='http://fixture.example'),
 lambda r:r.update(start_url='https://user:secret@fixture.example'),
 lambda r:r.update(steps=[]),
 lambda r:r.update(steps=[{'op':'eval','value':'document.cookie'}]),
 lambda r:r.update(steps=[{'op':[],'target':{'css':'body'}}]),
 lambda r:r.update(steps=[{'op':'click','target':{'css':'body'}}]),
 lambda r:r['steps'][0].update(value={'credential':'fal'}),
 lambda r:r['steps'][0].update(value={'input':[]}),
 lambda r:r['steps'][0].update(target={'css':'body','role':'button'}),
 lambda r:r['steps'][-1].update(filename='../secret'),
 lambda r:r['steps'][-1].update(filename='result.json'),
 lambda r:r.update(session='../browser'),
 lambda r:r.update(total_timeout_ms=300001),
 lambda r:r.update(timeout_ms=True),
])
def test_invalid_recipes_never_run(mutate):
    t=recipe_tool();mutate(t['recipe'])
    with pytest.raises(RouterError):validate_manifest(t)


def test_session_encrypted_scoped_and_not_a_key_slot(router):
    saved=save_session(router.vault,'studio',['https://fixture.example'],storage(),expires_at=int(time.time()+3600))
    assert saved['saved_encrypted'] and not saved['synced']
    assert b'FAKE-browser-session-secret' not in router.state.path.read_bytes()
    assert 'studio' not in router.state.secret_names()
    loaded=load_session(router.vault,'studio',['https://fixture.example'])
    assert loaded['cookies'][0]['value']=='FAKE-browser-session-secret'
    assert router.vault.redact('FAKE-browser-session-secret')!='FAKE-browser-session-secret'
    with pytest.raises(RouterError):load_session(router.vault,'studio',['https://other.example'])
    with pytest.raises(RouterError):save_session(router.vault,'studio',['https://fixture.example'],storage())
    fresh=Vault(State(router.state.home),password='unit-test-passphrase-long')
    assert load_session(fresh,'studio',['https://fixture.example'])==loaded
    assert 'FAKE' not in canonical(sessions(router.state))
    remove_session(router.state,'studio')
    with pytest.raises(RouterError):load_session(fresh,'studio',['https://fixture.example'])


@pytest.mark.parametrize('field',['nonce','ciphertext','expires_at'])
def test_session_tampering_is_detected(router,field):
    save_session(router.vault,'studio',['https://fixture.example'],storage())
    with router.state.db() as db:
        db.execute('UPDATE browser_sessions SET '+field+'=? WHERE name=?', (time.time()+3600 if field=='expires_at' else b'bad-tampering','studio'))
    with pytest.raises(RouterError):load_session(router.vault,'studio',['https://fixture.example'])


@pytest.mark.parametrize('value',[
 {'cookies':[{'domain':'evil.example'}]},
 {'origins':[{'origin':'https://evil.example','localStorage':[]}]},
 {'cookies':'bad'}, {'cookies':[{'domain':123}]}, {'origins':{}},
 {'cookies':[],'origins':[],'raw_profile':'not-supported'},
])
def test_storage_cannot_import_other_sites(router,value):
    with pytest.raises(RouterError):save_session(router.vault,'studio',['https://fixture.example'],value)


@pytest.mark.parametrize('expiry',[float('nan'),float('inf'),True,time.time()-1,'tomorrow'])
def test_session_bad_expiry_rejected(router,expiry):
    with pytest.raises(RouterError):save_session(router.vault,'studio',['https://fixture.example'],storage(),expires_at=expiry)


def test_browser_state_not_in_sync_export(router,tmp_path):
    save_session(router.vault,'studio',['https://fixture.example'],storage())
    a=Sync(router.vault);a.initialize('first')
    v=Vault(State(tmp_path/'other'),password='other-long-password');v.init('passphrase');b=Sync(v);b.initialize('second')
    router.vault.put('acme','FAKE-key-to-sync')
    a.trust(b.identity(),b.identity()['id'],send=['acme'],receive=[],apply=True)
    b.trust(a.identity(),a.identity()['id'],receive=['acme'],send=[],apply=True)
    b.import_packet(a.export_packet(b.identity()['id']),apply=True)
    assert v.get('acme')=='FAKE-key-to-sync'
    assert sessions(b.state)['sessions']==[]


def test_login_needs_human_tty(router,monkeypatch):
    monkeypatch.setattr('sys.stdin.isatty',lambda:False)
    with pytest.raises(RouterError) as e:login(router,'fixture.export')
    assert e.value.code=='interactive_required'


def synthetic_context(chromium, html=HTML, received=None, clicks=None):
    # This environment forbids browser navigation. We do not alter that policy.
    # Only in tests, replace goto with set_content and label the intended URL.
    class MemoryPage:
        def __init__(self,page):self.page=page
        @property
        def url(self):return 'https://fixture.example/'
        def goto(self,url,**kw):
            assert url=='https://fixture.example/'
            self.page.set_content(html)
        def __getattr__(self,name):return getattr(self.page,name)
    class MemoryContext:
        def __init__(self,ctx):self.ctx=ctx
        def new_page(self):return MemoryPage(self.ctx.new_page())
        def __getattr__(self,name):return getattr(self.ctx,name)
    @contextmanager
    def context(storage=None):
        if received is not None:received.append(storage)
        ctx=chromium.new_context(storage_state=storage,accept_downloads=True,service_workers='block')
        try:yield MemoryContext(ctx)
        finally:
            # HTML counts real button clicks in the page; read it before the page is gone.
            if clicks is not None:clicks.extend(p.evaluate('count') for p in ctx.pages)
            ctx.close()
    return context


@pytest.mark.browser
@pytest.mark.integration
def test_real_browser_dom_recipe_download_no_retry(router,workspace,chromium,monkeypatch):
    import agent_tool_maker.web_recipe as wr
    t=recipe_tool();router.catalog.tools[t['id']]=t
    monkeypatch.setattr(wr,'open_context',synthetic_context(chromium))
    first=router.run(t['id'],{'text':'actual generated file'},workspace,request_key='web-task',grants=['external_write'])
    assert first['status']=='completed',first
    assert (Path(first['data']['artifacts'][0]['path'])).read_text()=='actual generated file'
    assert first['data']['result']=={'state':'completed'}
    assert router.run(t['id'],{'text':'actual generated file'},workspace,request_key='web-task',grants=['external_write'])['id']==first['id']
    assert len(router.state.jobs())==1


@pytest.mark.browser
@pytest.mark.integration
def test_missing_locator_after_side_effect_is_unknown_not_resubmitted(router,workspace,chromium,monkeypatch):
    import agent_tool_maker.web_recipe as wr
    # Keep the recipe's normal per-step budget: it also bounds navigation and the pre-click
    # fill/click, so the 100 ms minimum let those time out under load ('failed', no click).
    # Only the missing post-click target exhausts it.
    t=recipe_tool();t['recipe']['steps'][2]['target']={'css':'#does-not-exist'}
    opened,clicks=[],[]
    router.catalog.tools[t['id']]=t;monkeypatch.setattr(wr,'open_context',synthetic_context(chromium,received=opened,clicks=clicks))
    job=router.run(t['id'],{'text':'one click'},workspace,request_key='uncertain',grants=['external_write'])
    assert job['status']=='submission_unknown'
    error=job['data']['error']
    assert error['code']=='browser_execution_failed' and error['outcome_uncertain'] is True
    assert error['message'].startswith('Browser step 3 failed.')  # fill and click finished; expect_text did not
    assert clicks==[1]
    assert 'does-not-exist' not in canonical(job['data'].get('error'))
    assert router.run(t['id'],{'text':'one click'},workspace,request_key='uncertain',grants=['external_write'])['id']==job['id']
    assert opened==[None] and len(router.state.jobs())==1


@pytest.mark.browser
@pytest.mark.integration
def test_login_blocked_returns_not_completed(router,workspace,chromium,monkeypatch):
    import agent_tool_maker.web_recipe as wr
    t=recipe_tool();t['recipe']['login_check']={'role':'heading','name':'Sign in'}
    router.catalog.tools[t['id']]=t;monkeypatch.setattr(wr,'open_context',synthetic_context(chromium,'<h1>Sign in</h1>'))
    job=router.run(t['id'],{'text':'no call'},workspace,grants=['external_write'])
    assert job['status']=='login_required' and job['data']['browser_steps_completed']==0


@pytest.mark.browser
@pytest.mark.integration
def test_new_context_receives_saved_session_but_does_not_echo_it(router,workspace,chromium,monkeypatch):
    import agent_tool_maker.web_recipe as wr
    state=storage();state['origins']=[]
    save_session(router.vault,'studio',['https://fixture.example'],state)
    t=recipe_tool();t['recipe'].update(session='studio',steps=[{'op':'extract','target':{'css':'#token'},'name':'result'}])
    router.catalog.tools[t['id']]=t
    html='<div id="token">FAKE-browser-session-secret</div>'; received=[]
    monkeypatch.setattr(wr,'open_context',synthetic_context(chromium,html,received))
    job=router.run(t['id'],{'text':'unused'},workspace,grants=['external_write'])
    assert job['status']=='completed' and job['data']['result']['result']!='not-signed-in'
    assert 'FAKE-browser-session-secret' not in canonical(router.public_job(job))
    assert received[0]['cookies'][0]['value']=='FAKE-browser-session-secret'


@pytest.mark.parametrize('url,permit',[
 ('https://fixture.example/path',True),('https://fixture.example.evil.test/',False),
 ('http://fixture.example/',False),('file:///etc/passwd',False),
 ('https://other.example/',False),('https://user:pass@fixture.example/',False)])
def test_recipe_request_guard_checks_exact_origin(router,url,permit):
    from agent_tool_maker.web_recipe import restrict_context
    class C:
        def route(self,pattern,handler):self.guard=handler
        def route_web_socket(self,pattern,handler):self.ws=handler
    class R:
        request=type('Request',(),{'url':url})()
        state=None
        def abort(self,*args):self.state='blocked'
        def fallback(self):self.state='allowed'
    ctx=C();blocked=restrict_context(ctx,router,recipe_tool()['recipe']);req=R();ctx.guard(req)
    assert req.state==('allowed' if permit else 'blocked')
    assert bool(blocked)==(not permit)


def test_managed_browser_policy_error_is_not_bypassed(router,workspace,monkeypatch):
    import agent_tool_maker.web_recipe as wr
    @contextmanager
    def denied(storage=None):
        raise RuntimeError('Page.goto ERR_BLOCKED_BY_ADMINISTRATOR https://some-url-with-private-text')
        yield
    t=recipe_tool();router.catalog.tools[t['id']]=t;monkeypatch.setattr(wr,'open_context',denied)
    job=router.run(t['id'],{'text':'test'},workspace,grants=['external_write'])
    assert job['status']=='failed' and job['data']['error']['code']=='browser_policy_blocked'
    assert 'some-url' not in canonical(job['data']['error'])


def test_api_key_and_web_session_health_remain_separate(router):
    t=recipe_tool();t['recipe']['session']='studio'
    router.vault.put('studio','not-a-browser-state')
    assert health(router,t)['state']=='browser_session_missing'

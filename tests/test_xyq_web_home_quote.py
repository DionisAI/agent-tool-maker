"""Draft-bound displayed home credits: fixtures are not actual paid execution."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_xyq_web_cli import native_page,load
from test_xyq_web_form import b,form_html

ROOT=Path(__file__).resolve().parents[1]
def test_home_quote_manifest_is_exact_read_only_and_not_paid():
    t=b.home_quote_manifest()
    assert t['id']=='xyq.web.home_quote' and t['permissions']==['execute_code'] and not t['paid']
    assert t['command']['argv'][1:3]==['xyq-web','home-quote-bound']
    assert b.bundle_digest(b.HOME_QUOTE_FILES) in t['command']['argv']
    assert t['schema']['properties']['settings']['required']==['expected_draft_sha256']
    assert t['schema']['properties']['settings']['additionalProperties'] is False
    assert 'credential' not in t and 'credential_env' not in t['command']

def test_quote_pin_matches_node_and_prior_closures_stay_intact():
    p=subprocess.run(['node','--input-type=module','-e',"import {homeQuoteDigest} from './examples/opencli/xyq-web/home-quote.mjs';console.log(homeQuoteDigest());"],cwd=ROOT,capture_output=True,text=True,check=True)
    assert p.stdout.strip()==b.bundle_digest(b.HOME_QUOTE_FILES) and len(b.HOME_QUOTE_FILES)==10
    assert b.bundle_digest(b.HOME_BOUND_FILES)=='8f5f2abbb2610665312d4380ccdeeb995f8336cd6aef1cbbd5f647e785ac8d55'
    assert b.bundle_digest(b.AUDIO_UPLOAD_BOUND_FILES)=='f33eecb64e8a6cb2b744235ea38e70b5d81b6847f0050a94a67141290d097d27'

@pytest.mark.parametrize('combo',[False,True])
def test_compiler_adds_quote_and_preserves_all_existing_routes(tmp_path,combo):
    out=tmp_path/'stage';p=subprocess.run([sys.executable,str(ROOT/'scripts/build_xyq_web.py'),'--out',str(out),*(['--bound-home','--bound-audio-quote','--bound-audio-edit','--bound-audio-upload'] if combo else [])],cwd=ROOT,capture_output=True,text=True,check=True)
    m=json.loads(p.stdout);assert len(m['operations'])==18 and m['home_quote_binding']=='explicit-browser'
    assert m['home_quote_adapter_sha256']==b.bundle_digest(b.HOME_QUOTE_FILES)
    for op in m['operations']:
        expected=b.history_manifest() if op=='project_history_state' else b.home_quote_manifest() if op=='home_quote' else b.home_bound_manifest(op) if combo and op in b.HOME_BOUND_OPERATIONS else b.audio_quote_bound_manifest() if combo and op=='audio_quote' else b.audio_edit_bound_manifest(op) if combo and op in b.AUDIO_EDIT_BOUND_OPERATIONS else b.audio_upload_bound_manifest() if combo and op=='audio_reference_upload' else b.manifest(op) if op in b.OPERATIONS else b.form_manifest(op) if op in b.FORM_OPERATIONS else b.mode_manifest(op) if op in b.MODE_OPERATIONS else b.audio_manifest(op) if op in b.AUDIO_OPERATIONS else b.audio_bound_manifest() if op=='audio_form_state_bound' else b.audio_prompt_manifest() if op=='audio_prompt_prepare' else b.audio_settings_manifest(op) if op in b.AUDIO_SETTINGS_OPERATIONS else b.audio_quote_manifest()
        assert json.loads((out/op/'manifest.json').read_bytes())==expected

def test_fake_subprocess_stable_key_reuses_quote_without_vault_access(router,workspace,tmp_path):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.home_quote_manifest();manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(tool))
    install(router.state,router.catalog,manifest,digest(tool));router.catalog=Catalog(router.state)
    app=tmp_path/'fake-home-quote'
    app.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','home-quote-bound']
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('home-quote-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fixture_only','total_credits':None,'paid_submitted':False}}}}]))
''');app.chmod(0o700);bind_cli(router.state,'opencliapp',str(app));router.vault.get=lambda *a:pytest.fail('No vault reads')
    inputs={'settings':{'expected_draft_sha256':'a'*64}}
    a=router.run(tool['id'],inputs,workspace,request_key='home-quote-once',grants=['execute_code'])
    reused=router.run(tool['id'],inputs,workspace,request_key='home-quote-once',grants=['execute_code'])
    assert a['status']=='completed' and reused['id']==a['id'] and (workspace/'home-quote-count').read_text()=='1'
    fresh=router.run(tool['id'],inputs,workspace,request_key='home-quote-refresh',grants=['execute_code'])
    assert fresh['id']!=a['id'] and fresh['status']=='completed' and (workspace/'home-quote-count').read_text()=='2'

def quote_html(mode='视频生成',amount='600',original='780',missing=False,busy=False,submit_busy=False,hidden=False,rich=False):
    html=form_html(rich=rich).replace('<button aria-label="选择创作模式">视频生成</button>',f'<button aria-label="选择创作模式">{mode}</button>')
    html=html.replace('<button aria-label="开始生成"',f'<button data-slot="home-input-composer-submit-button" aria-busy="{str(submit_busy).lower()}" aria-label="开始生成"')
    label=amount.split('/')[0].strip()
    price='' if missing else f'''<span id="price" data-testid="home-direct-generation-credit-estimate" data-slot="credit-amount" aria-label="积分消耗 {label}" aria-busy="{str(busy).lower()}" {'hidden' if hidden else ''}><span data-slot="amount">{amount}</span>{f'<span data-slot="originalAmount" class="line-through">{original}</span>' if original is not None else ''}</span>'''
    return html.replace('<button id="canvas"',price+'<button id="canvas"').replace('</style>','.line-through{text-decoration-line:line-through}</style>')

def adapter(page,config=None):
    config=config or {};p=subprocess.Popen(['node','tests/fixtures/xyq_home_quote_rpc.mjs',json.dumps(config)],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);quotes=0
    try:
        for line in p.stdout:
            r=json.loads(line)
            if r['type']=='done':p.wait(timeout=5);assert p.returncode==0,p.stderr.read();return r
            assert r['type']=='call' and r['method']=='evaluate'
            assert any(r['source'].startswith('function '+n+'(') for n in ['readHomeDOM','readDraftDOM','readHomeQuoteDOM'])
            response={'id':r['id']}
            if r['source'].startswith('function readHomeQuoteDOM('):
                quotes+=1
                if quotes==2 and config.get('race'):
                    if config['race']=='price':page.locator('#price [data-slot="amount"]').evaluate("e=>{e.innerText='601';e.parentElement.setAttribute('aria-label','积分消耗 601');}")
                    elif config['race']=='prompt':page.locator('#editor').evaluate("e=>{e.innerText='changed';}")
                    elif config['race']=='submit':page.locator('[aria-label="开始生成"]').evaluate("e=>{e.disabled=true;}")
            try:response['value']=page.evaluate(r['source'],r.get('arg'))
            except Exception:response['error']='native_fixture_error'
            p.stdin.write(json.dumps(response,ensure_ascii=False)+'\n');p.stdin.flush()
        pytest.fail('Fixture returned no terminal result')
    finally:
        if p.poll() is None:p.terminate();p.wait(timeout=5)

@pytest.mark.browser
@pytest.mark.parametrize('mode,amount,original,status',[
    ('图片生成','6',None,'quoted_estimate'),('视频生成','600','780','quoted_estimate'),('音频生成','0.33/秒',None,'quoted_rate')])
def test_native_actual_slots_units_discount_and_full_body_preserved(native_page,mode,amount,original,status):
    load(native_page,quote_html(mode,amount,original,rich=True));body=native_page.locator('body').inner_html();out=adapter(native_page)
    assert 'error' not in out,out;r=out['result'][0]['result']
    assert r['status']==status and r['draft_sha256']==out['before']['draft_sha256'] and r['reported_estimate']['credit_amount']==float(amount.split('/')[0])
    assert r['reported_estimate']['original_credit_amount']==(None if original is None else float(original))
    assert r['total_credits'] is None and r['output_duration_seconds'] is None
    assert not r['spend_ceiling_verified'] and not r['charge_scope_verified'] and not r['paid_submitted']
    assert r['browser_session']=='site:xyq-home' and not r['binding_changed']
    assert native_page.locator('body').inner_html()==body and native_page.evaluate('window.submitted')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('flags,status,reason',[
    ({'missing':True},'quote_unavailable','price_missing'),({'hidden':True},'quote_unavailable','price_missing'),
    ({'busy':True},'quote_pending','price_or_submission_busy'),({'submit_busy':True},'quote_pending','price_or_submission_busy'),
    ({'amount':'FAKE_PRIVATE_PRICE','original':None},'quote_unavailable','unsupported_price_format'),
    ({'amount':'600','original':'FAKE_PRIVATE_ORIGINAL'},'quote_unavailable','unsupported_price_format'),
    ({'amount':'600','original':'500'},'quote_unavailable','unsupported_price_format')])
def test_native_pending_missing_unknown_are_not_free_quotes(native_page,flags,status,reason):
    load(native_page,quote_html(**flags));body=native_page.locator('body').inner_html();out=adapter(native_page)
    assert 'error' not in out,out;r=out['result'][0]['result']
    assert r['status']==status and r['reason']==reason and r['reported_estimate'] is None and r['total_credits'] is None
    assert native_page.locator('body').inner_html()==body and native_page.evaluate('window.submitted')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('change',[
    "e=>e.after(e.cloneNode(true))",
    "e=>e.setAttribute('data-slot','wrong')",
    "e=>e.querySelector('[data-slot=amount]').after(e.querySelector('[data-slot=amount]').cloneNode(true))",
    "e=>e.querySelector('[data-slot=originalAmount]').classList.remove('line-through')",
    "e=>e.setAttribute('aria-busy','wrong')",
    "e=>document.querySelector('[aria-label=开始生成]').setAttribute('data-slot','wrong')",
])
def test_native_wrong_association_and_duplicate_slots_fail_without_input(native_page,change):
    load(native_page,quote_html());native_page.locator('#price').evaluate(change);body=native_page.locator('body').inner_html();out=adapter(native_page)
    assert out['error']['code']=='quote_layout_changed',out
    assert native_page.locator('body').inner_html()==body and native_page.evaluate('window.submitted')==0

@pytest.mark.browser
@pytest.mark.parametrize('url,code',[
    ('https://example.test/home','origin_mismatch'),('https://xyq.jianying.com/login','login_required'),('https://xyq.jianying.com/project','unsupported_surface')])
def test_native_wrong_bound_surface_stops_first_read(native_page,url,code):
    load(native_page,quote_html(),url=url);body=native_page.locator('body').inner_html()
    out=adapter(native_page,{'skip_before':True,'settings':{'expected_draft_sha256':'a'*64}})
    assert out['error']['code']==code and native_page.locator('body').inner_html()==body

@pytest.mark.browser
def test_native_existing_masked_menu_stops_without_dismissing(native_page):
    load(native_page,quote_html());native_page.locator('#title-section-prompt-container').evaluate("e=>e.setAttribute('aria-hidden','true')")
    native_page.locator('#prefs').evaluate("e=>e.hidden=false");body=native_page.locator('body').inner_html()
    out=adapter(native_page,{'skip_before':True,'settings':{'expected_draft_sha256':'a'*64}})
    assert out['error']['code']=='dialog_open' and native_page.locator('body').inner_html()==body

@pytest.mark.browser
@pytest.mark.parametrize('race,code',[('price','quote_changed'),('submit','quote_changed'),('prompt','draft_changed')])
def test_native_quote_races_remain_errors_and_never_generate(native_page,race,code):
    load(native_page,quote_html());out=adapter(native_page,{'race':race})
    assert out['error']['code']==code,out
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_stale_draft_sha_stops_before_any_input(native_page):
    load(native_page,quote_html());body=native_page.locator('body').inner_html()
    out=adapter(native_page,{'settings':{'expected_draft_sha256':'0'*64}})
    assert out['error']['code']=='draft_changed' and native_page.locator('body').inner_html()==body

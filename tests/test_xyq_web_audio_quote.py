"""Draft-bound audio rates through actual source, isolated native DOM and subprocesses."""
import json
from pathlib import Path
import subprocess
import pytest
from test_xyq_web_cli import native_page,load
from test_xyq_web_media import b,media_adapter,audio_html,SCOPE

ROOT=Path(__file__).resolve().parents[1]

def test_audio_quote_manifest():
    from agent_tool_maker.maker import validate_manifest
    tool=b.audio_quote_manifest();assert validate_manifest(tool)==tool
    assert tool['id']=='xyq.web.audio_quote' and not tool['paid']
    assert tool['permissions']==['execute_code']
    assert tool['schema']['additionalProperties'] is False
    assert tool['schema']['properties']['settings']['required']==['expected_form_sha256']
    assert 'credential' not in tool and 'credential_env' not in tool['command']

def test_audio_quote_pin_matches_node():
    out=subprocess.run(['node','--input-type=module','-e',"import {audioQuoteDigest} from './examples/opencli/xyq-web/audio-quote.mjs'; console.log(audioQuoteDigest())"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert out.stdout.strip()==b.bundle_digest(b.AUDIO_QUOTE_FILES)

def test_audio_quote_fake_subprocess_exact_once(router,workspace,tmp_path):
    import sys
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.audio_quote_manifest();manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(tool))
    install(router.state,router.catalog,manifest,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-reviewed-xyq-quote';program.write_text(f'''#!{sys.executable}
import sys,json,os
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','audio-quote']
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('quote-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fake_fixture','total_credits':None,'paid_submitted':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *args:pytest.fail('No credential read')
    inputs={**SCOPE,'settings':{'expected_form_sha256':'a'*64}}
    one=router.run(tool['id'],inputs,workspace,request_key='quote-once',grants=['execute_code'])
    two=router.run(tool['id'],inputs,workspace,request_key='quote-once',grants=['execute_code'])
    assert one['status']=='completed' and one['id']==two['id']
    assert (workspace/'quote-count').read_text()=='1'
    fresh=router.run(tool['id'],inputs,workspace,request_key='quote-new-observation',grants=['execute_code'])
    assert fresh['status']=='completed' and fresh['id']!=one['id']
    assert (workspace/'quote-count').read_text()=='2'

def quote_html(*,price='1积分/3s',busy=False,hidden=False,duplicate=False,prompt=True):
    html=audio_html()
    if prompt:html=html.replace('<p><br></p>','<p>FAKE_PRIVATE_PROMPT</p>')
    cost=f'<span title="预计消耗积分" aria-busy="{str(busy).lower()}"'+(' hidden' if hidden else '')+'>'+price+'</span>'
    return html.replace('<button data-action="audio-generate-submit"',cost+(cost if duplicate else '')+'<button data-action="audio-generate-submit"')

def config(**settings):return {'operation':'audio_quote','scope':SCOPE,'settings':settings}

@pytest.mark.browser
@pytest.mark.parametrize('price,credits,seconds',[('1积分/3s',1,3),('0.33积分/s',0.33,1),('0积分/3s',0,3)])
def test_native_exact_audio_rate_read_and_private_draft_preservation(native_page,price,credits,seconds):
    load(native_page,quote_html(price=price),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    body=native_page.locator('body').inner_html();out=media_adapter(native_page,config());assert 'error' not in out,out
    result=out['result'][0]['result'];assert result['status']=='quoted_rate'
    assert result['reported_rate']=={'credit_amount':credits,'per_seconds':seconds,'display_text':price,'estimated':True}
    assert result['form_sha256']==out['before']['form_sha256']
    assert result['total_credits'] is None and result['output_duration_seconds'] is None
    assert not result['spend_ceiling_verified'] and not result['paid_submitted']
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.submitted+window.uploaded')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('flags,status,reason',[
    ({'busy':True},'quote_pending','price_or_submission_busy'),
    ({'hidden':True},'quote_unavailable','price_missing'),
    ({'price':'1积分'},'quote_unavailable','unsupported_price_format'),
    ({'price':'FAKE_PRIVATE_COST'},'quote_unavailable','unsupported_price_format'),
])
def test_native_audio_rate_unknown_busy_or_hidden(native_page,flags,status,reason):
    load(native_page,quote_html(**flags),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    body=native_page.locator('body').inner_html();out=media_adapter(native_page,config());assert 'error' not in out,out
    result=out['result'][0]['result'];assert result['status']==status and result['reason']==reason
    assert result['reported_rate'] is None and result['total_credits'] is None
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.submitted+window.uploaded')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('flags,settings,code',[
    ({'duplicate':True},{},'quote_layout_changed'),
    ({},{'expected_form_sha256':'0'*64},'draft_changed'),
])
def test_native_audio_quote_error_preserves_body(native_page,flags,settings,code):
    load(native_page,quote_html(**flags),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    body=native_page.locator('body').inner_html();out=media_adapter(native_page,config(**settings))
    assert out['error']['code']==code,out
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.submitted+window.uploaded')==0

@pytest.mark.browser
def test_native_audio_quote_reader_guards_scope_and_selected_panel(native_page):
    load(native_page,quote_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=subprocess.run(['node','--input-type=module','-e',"import {readAudioQuoteDOM} from './examples/opencli/xyq-web/audio-quote.mjs'; console.log(readAudioQuoteDOM.toString())"],cwd=ROOT,text=True,capture_output=True,check=True)
    src=out.stdout.strip();assert native_page.evaluate(src,SCOPE)['price_text']=='1积分/3s'
    assert native_page.evaluate(src,{**SCOPE,'canvas_id':'9'})['kind']=='canvas_changed'
    assert native_page.evaluate(src,{**SCOPE,'node_id':'9'})['kind']=='node_changed'
    native_page.locator('span[title="预计消耗积分"]').evaluate("e=>e.setAttribute('aria-busy','UNKNOWN')")
    assert native_page.evaluate(src,SCOPE)['kind']=='quote_layout_changed'
    native_page.locator('[data-xyq-selected-audio-footer-panel]').evaluate("e=>e.setAttribute('aria-hidden','true')")
    assert native_page.evaluate(src,SCOPE)['kind']=='audio_form_closed'
    assert native_page.evaluate('window.submitted+window.uploaded')==0

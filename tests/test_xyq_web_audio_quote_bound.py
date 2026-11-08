"""Explicit audio rate routing: unit price only, independent of real-site acceptance."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_xyq_web_cli import native_page,load
from test_xyq_web_media import b,SCOPE,media_adapter
from test_xyq_web_audio_quote import quote_html

ROOT=Path(__file__).resolve().parents[1]

def test_bound_quote_manifest_changes_only_route_pin_and_routing_notes():
    normal=b.audio_quote_manifest();bound=b.audio_quote_bound_manifest()
    assert bound['id']=='xyq.web.audio_quote' and bound['permissions']==['execute_code'] and not bound['paid']
    assert bound['command']['argv'][1:3]==['xyq-web','audio-quote-bound']
    assert b.bundle_digest(b.AUDIO_QUOTE_BOUND_FILES) in bound['command']['argv']
    bound['command']['argv'][2]=normal['command']['argv'][2]
    bound['command']['argv'][bound['command']['argv'].index('--pin')+1]=b.bundle_digest(b.AUDIO_QUOTE_FILES)
    bound['notes']=normal['notes']
    assert bound==normal

def test_bound_quote_dependency_union_matches_node_and_preserves_old_pins():
    out=subprocess.run(['node','--input-type=module','-e',"import {audioQuoteBoundDigest} from './examples/opencli/xyq-web/audio-quote-bound.mjs';console.log(audioQuoteBoundDigest());"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert out.stdout.strip()==b.bundle_digest(b.AUDIO_QUOTE_BOUND_FILES)
    assert len(b.AUDIO_QUOTE_BOUND_FILES)==10
    assert b.bundle_digest(b.AUDIO_BOUND_FILES)=='7bed12544c154f6dd34a012801c72578695888880cdbd97ad19c9618350530cd'
    assert b.bundle_digest(b.HOME_BOUND_FILES)=='8f5f2abbb2610665312d4380ccdeeb995f8336cd6aef1cbbd5f647e785ac8d55'
    assert b.bundle_digest(b.AUDIO_QUOTE_FILES)=='caad9d8dccce5308b19d5192a1d6b60ea7b80e2615ad66395067dd4fc8f53a9d'

@pytest.mark.parametrize('home_bound',[False,True])
def test_explicit_compiler_keeps_eighteen_tools_and_unselected_definitions(tmp_path,home_bound):
    base=[sys.executable,str(ROOT/'scripts/build_xyq_web.py')]
    default=json.loads(subprocess.run(base+['--out',str(tmp_path/'default')],text=True,capture_output=True,check=True).stdout)
    selected=json.loads(subprocess.run(base+['--out',str(tmp_path/'bound'),'--bound-audio-quote',*(['--bound-home'] if home_bound else [])],text=True,capture_output=True,check=True).stdout)
    assert selected['operations']==default['operations'] and len(selected['operations'])==18
    assert selected['audio_quote_binding']=='explicit-browser'
    assert selected['audio_quote_bound_adapter_sha256']==b.bundle_digest(b.AUDIO_QUOTE_BOUND_FILES)
    for operation in selected['operations']:
        tool=json.loads((tmp_path/'bound'/operation/'manifest.json').read_text())
        expected=b.audio_quote_bound_manifest() if operation=='audio_quote' else b.home_bound_manifest(operation) if home_bound and operation in b.HOME_BOUND_OPERATIONS else json.loads((tmp_path/'default'/operation/'manifest.json').read_text())
        assert tool==expected
    assert 'audio_quote_binding' not in default

def test_bound_quote_fake_subprocess_reuses_history_and_new_observation_reads_again(router,workspace,tmp_path):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.audio_quote_bound_manifest();manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(tool))
    install(router.state,router.catalog,manifest,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-reviewed-bound-rate'
    program.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','audio-quote-bound']
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('quote-bound-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fake_bound_quote_fixture','total_credits':None,'paid_submitted':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program))
    router.vault.get=lambda *args:pytest.fail('No credential access')
    inputs={**SCOPE,'settings':{'expected_form_sha256':'a'*64}}
    one=router.run(tool['id'],inputs,workspace,request_key='bound-quote-once',grants=['execute_code'])
    two=router.run(tool['id'],inputs,workspace,request_key='bound-quote-once',grants=['execute_code'])
    assert one['status']=='completed' and two['id']==one['id']
    assert (workspace/'quote-bound-count').read_text()=='1'
    fresh=router.run(tool['id'],inputs,workspace,request_key='bound-quote-fresh-read',grants=['execute_code'])
    assert fresh['status']=='completed' and fresh['id']!=one['id']
    assert (workspace/'quote-bound-count').read_text()=='2'

@pytest.mark.browser
@pytest.mark.parametrize('flags,status,reason',[
    ({},'quoted_rate',None),
    ({'busy':True},'quote_pending','price_or_submission_busy'),
    ({'hidden':True},'quote_unavailable','price_missing'),
    ({'price':'FAKE_PRIVATE_COST'},'quote_unavailable','unsupported_price_format'),
])
def test_native_bound_audio_rate_preserves_body_and_never_inputs(native_page,flags,status,reason):
    load(native_page,quote_html(**flags),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    body=native_page.locator('body').inner_html()
    out=media_adapter(native_page,{'operation':'audio_quote_bound','scope':dict(SCOPE),'settings':{}})
    assert 'error' not in out,out
    result=out['result'][0]['result']
    assert result['status']==status and result['reason']==reason
    assert result['browser_session']=='site:xyq-web' and result['browser_surface']=='browser'
    assert result['form_sha256']==out['before']['form_sha256']
    assert result['total_credits'] is None and result['output_duration_seconds'] is None
    assert not result['binding_changed'] and not result['spend_ceiling_verified'] and not result['paid_submitted']
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.submitted+window.uploaded')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('flags,settings,code',[
    ({'duplicate':True},{},'quote_layout_changed'),
    ({},{'expected_form_sha256':'0'*64},'draft_changed'),
])
def test_native_bound_audio_quote_failures_preserve_body(native_page,flags,settings,code):
    load(native_page,quote_html(**flags),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    body=native_page.locator('body').inner_html()
    out=media_adapter(native_page,{'operation':'audio_quote_bound','scope':dict(SCOPE),'settings':settings})
    assert out['error']['code']==code,out
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.submitted+window.uploaded')==0

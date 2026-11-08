"""V0.2 contract coverage: real executor, mocked paid network / protocol fixture CLIs."""
import json,sys,shutil
from pathlib import Path
from urllib.parse import urlsplit
import httpx,pytest
from agent_tool_maker.actions import preflight,compile_request
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.errors import RouterError
from agent_tool_maker.storage import canonical

DATA=Path(__file__).parents[1]/'src/agent_tool_maker/data'
ROWS=json.loads((DATA/'catalog-v02.json').read_text())
REST=[r for r in ROWS if r['adapter']=='rest']
CLI=[r for r in ROWS if r['adapter']=='command']
ALL_GRANTS=['external_write','production','execute_code']

def prepare(router,workspace,row):
    if row.get('credential'):
        key='FAKE_'+row['credential']
        if row['request'].get('auth')=='ghost':key='id:'+('a'*64)
        if row['request'].get('auth')=='telegram':key='12345:token'
        if row['request'].get('test_key_only'):key='sk_test_FAKE'
        router.vault.put(row['credential'],key)
    if row.get('request',{}).get('origin_setting'):
        origin='http://127.0.0.1:8188' if row['request'].get('local') else 'https://example.myshopify.com' if row['provider']=='shopify_admin' else 'https://api.example.com'
        router.state.set_setting('origin:'+row['provider'],origin)
    for token in row.get('command',{}).get('argv',[]):
        if not isinstance(token,dict):continue
        if 'file' in token:
            p=workspace/row['example'][token['file']];p.parent.mkdir(exist_ok=True,parents=True)
            if p.suffix=='.png':shutil.copyfile(Path(__file__).parent/'fixtures/image.png',p)
            elif p.suffix=='.wav':shutil.copyfile(Path(__file__).parent/'fixtures/tone.wav',p)
            else:p.write_text('fixture source')
        elif 'dir' in token:(workspace/row['example'][token['dir']]).mkdir(exist_ok=True,parents=True)

@pytest.mark.parametrize('row',REST,ids=lambda r:r['id'])
def test_each_rest_action_request_contract(router,workspace,row):
    prepare(router,workspace,row);seen=[]
    expected=compile_request(router.state,row,row['example'])
    def handler(request):
        seen.append(request)
        assert request.method==expected['method']
        if row['request'].get('auth')!='telegram':assert str(request.url)==expected['url']
        if expected['method'] not in {'GET','HEAD'} and not row['request'].get('form'):
            assert json.loads(request.content)==expected['body']
        return httpx.Response(200,json={'ok':True,'success':True,'data':{'id':'fixture-id'},'items':[]})
    router.net.client.close();router.net.client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
    j=router.run(row['id'],row['example'],workspace,allow_paid=True,grants=ALL_GRANTS)
    assert j['status']=='completed',j
    assert len(seen)==1
    assert j['data']['verification']=='http_and_json_only'
    assert not 'FAKE_' in canonical(router.public_job(j))
    key=row.get('credential')
    if key and row['request'].get('auth') not in {'telegram','none'}:assert any(h.lower() in ['authorization','x-figma-token','x-shopify-access-token','x-n8n-api-key','freelancer-oauth-v1'] for h in seen[0].headers)

@pytest.mark.parametrize('row',CLI,ids=lambda r:r['id'])
def test_each_cli_action_real_protocol_fixture(router,workspace,tmp_path,row,monkeypatch):
    prepare(router,workspace,row)
    binary=tmp_path/('fixture-'+row['executable'])
    binary.write_text(f'''#!{sys.executable}
import sys,os,json
from pathlib import Path
assert 'ATM_VAULT_PASSWORD' not in os.environ
assert 'ELEVENLABS_API_KEY' not in os.environ
args=sys.argv[1:]
Path('received-argv.json').write_text(json.dumps(args))
for value in args:
 if '/.atm/artifacts/' in value:
  p=Path(value)
  if p.suffix:
   p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{{"fixture":true}}')
  else:
   if p.name=='transcript':
    for ext in ['.txt','.json']:Path(str(p)+ext).write_text('{{"fixture":true}}')
   else:p.mkdir(exist_ok=True,parents=True);(p/'fixture.txt').write_text('data')
print(json.dumps({{'accepted':True,'argv_count':len(args)}}))
''');binary.chmod(0o700)
    bind_cli(router.state,row['executable'],str(binary))
    monkeypatch.setenv('ATM_VAULT_PASSWORD','SHOULD_NOT_LEAK');monkeypatch.setenv('ELEVENLABS_API_KEY','SHOULD_NOT_LEAK')
    j=router.run(row['id'],row['example'],workspace,allow_paid=True,grants=ALL_GRANTS)
    assert j['status']=='completed',j
    assert j['data']['verification']=='cli_exit_and_declared_outputs'
    for a in j['data']['artifacts']:assert Path(a['path']).is_file()
    assert (workspace/'received-argv.json').exists()

@pytest.mark.parametrize('tool',[r['id'] for r in ROWS if r.get('permissions')])
def test_gated_actions_refuse_missing_permissions(router,workspace,tool):
    r=router.catalog.get(tool)
    with pytest.raises(RouterError) as error:router.run(tool,r['example'],workspace,allow_paid=True)
    assert error.value.code=='permission_required'
    assert router.state.jobs()==[]

@pytest.mark.parametrize('payload',[{'ok':False,'error':'secret leak'},{'success':False},{'errors':[{'message':'private'}]},{'data':{'productCreate':{'userErrors':[{'message':'bad'}]}}}])
def test_200_application_errors_are_not_success(router,workspace,payload):
    row=router.catalog.get('slack.send');prepare(router,workspace,row)
    router.net.client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=payload)))
    j=router.run(row['id'],row['example'],workspace,grants=ALL_GRANTS)
    assert j['status']=='submission_unknown'
    assert 'secret leak' not in canonical(j)

@pytest.mark.parametrize('body',[b'{not json',b'['*200000],ids=['invalid','nested'])
def test_rest_nested_json_is_unknown_like_invalid_json(router,workspace,body):
    row=router.catalog.get('slack.send');prepare(router,workspace,row);seen=[]
    router.net.client.close();router.net.client=httpx.Client(transport=httpx.MockTransport(lambda req:seen.append(req) or httpx.Response(200,content=body)),trust_env=False)
    j=router.run(row['id'],row['example'],workspace,request_key='deep',grants=ALL_GRANTS)
    assert j['status']=='submission_unknown' and j['data']['error']['code']=='upstream_schema' and j['data']['error']['outcome_uncertain'] is True
    assert router.run(row['id'],row['example'],workspace,request_key='deep',grants=ALL_GRANTS)['id']==j['id'] and len(seen)==1

def test_stripe_live_key_rejected_before_request(router,workspace):
    row=router.catalog.get('stripe.checkout_test');prepare(router,workspace,row);router.vault.put('stripe','sk_live_NEVER_CHARGE')
    def fail(req):pytest.fail('must not call Stripe')
    router.net.client=httpx.Client(transport=httpx.MockTransport(fail))
    j=router.run(row['id'],row['example'],workspace,grants=ALL_GRANTS)
    assert j['status']=='failed' and j['data']['error']['code']=='test_key_required'

def test_output_symlink_and_input_traversal_rejected(router,workspace,tmp_path):
    row=router.catalog.get('imagemagick.resize')
    outside=tmp_path/'outside.png';shutil.copyfile(Path(__file__).parent/'fixtures/image.png',outside)
    (workspace/'link.png').symlink_to(outside)
    with pytest.raises(RouterError):preflight(router,row,{'path':'link.png','geometry':'2x2'},workspace)
    with pytest.raises(RouterError):preflight(router,row,{'path':'../outside.png','geometry':'2x2'},workspace)

def test_argument_option_injection_rejected(router,workspace):
    with pytest.raises(RouterError):preflight(router,router.catalog.get('github.repo'),{'repo':'--help'},workspace)

def test_bind_hash_detects_changed_program(router,workspace,tmp_path):
    p=tmp_path/'cli';p.write_text(f'#!{sys.executable}\nprint("one")\n');p.chmod(0o700)
    bind_cli(router.state,'buffer',str(p));p.write_text(f'#!{sys.executable}\nprint("two")\n')
    j=router.run('buffer.channels',{},workspace)
    assert j['status']=='failed' and j['data']['error']['code']=='executable_changed'

def test_dynamic_api_rejects_path_in_origin(router,workspace):
    from agent_tool_maker.actions import set_origin
    with pytest.raises(RouterError):set_origin(router.state,'posthog','https://api.example.com/steal')
    with pytest.raises(RouterError):set_origin(router.state,'shopify_admin','https://evil.example')
    with pytest.raises(RouterError):set_origin(router.state,'comfyui','http://192.168.1.2:8188')
    assert set_origin(router.state,'comfyui','http://127.0.0.1:8188')['authentication']=='not_verified'

@pytest.mark.integration
@pytest.mark.parametrize('tool,inputs,exe',[
 ('imagemagick.resize',{'path':'image.png','geometry':'8x8'},'magick'),
 ('imagemagick.webp',{'path':'image.png','quality':75},'magick'),
 ('pandoc.to_markdown',{'path':'source.html'},'pandoc'),
 ('pandoc.to_docx',{'path':'source.md'},'pandoc')])
def test_real_installed_media_and_document_programs(router,workspace,tool,inputs,exe):
    path=shutil.which(exe)
    if not path:pytest.skip(exe+' not installed')
    bind_cli(router.state,exe,path)
    shutil.copyfile(Path(__file__).parent/'fixtures/image.png',workspace/'image.png')
    (workspace/'source.html').write_text('<h1>ATM</h1><p>Tool maker.</p>')
    (workspace/'source.md').write_text('# ATM\n\nTool maker.')
    j=router.run(tool,inputs,workspace,grants=router.catalog.get(tool).get('permissions',[]))
    assert j['status']=='completed',j
    f=Path(j['data']['artifacts'][0]['path']);assert f.stat().st_size>0
    if tool=='imagemagick.resize':
        from PIL import Image
        with Image.open(f) as im:assert im.width<=8 and im.height<=8
    if tool=='pandoc.to_docx':
        import zipfile
        assert 'word/document.xml' in zipfile.ZipFile(f).namelist()

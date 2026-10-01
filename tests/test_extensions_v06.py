import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import httpx
import pytest

from agent_tool_maker import extensions as ex
from agent_tool_maker.actions import compile_request
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.errors import RouterError
from agent_tool_maker.maker import validate_manifest, digest, install
from agent_tool_maker.management import known_credentials, connect_value
from agent_tool_maker.network import Network
from agent_tool_maker.storage import canonical


def add(router,tool,tmp_path):
    tool=validate_manifest(tool,router.catalog)
    file=tmp_path/(tool['id']+'.json');file.write_text(canonical(tool))
    install(router.state,router.catalog,file,digest(tool));router.catalog=Catalog(router.state)
    return tool,file


def test_declare_key_without_any_tool(router):
    n=len(router.catalog.tools)
    p=ex.declare_credential(router,'acme.production',label='Production API')
    assert p['action']=='declare' and 'acme.production' not in known_credentials(router)
    ex.declare_credential(router,'acme.production',apply=True)
    saved=connect_value(router,'acme.production','FAKE-standalone-key')
    assert saved['saved_encrypted'] and len(router.catalog.tools)==n
    before=router.state.path.read_bytes()
    assert ex.declare_credential(router,'acme.production',apply=True)['action']=='unchanged'
    assert connect_value(router,'acme.production','do-not-replace')['status']=='already_configured'
    assert router.vault.get('acme.production')=='FAKE-standalone-key'
    assert b'FAKE-standalone-key' not in before


@pytest.mark.parametrize('name',['','A bad name','../../passwd','x','_internal','a\nkey',123,'a'*81])
def test_bad_credential_names_rejected(router,name):
    with pytest.raises(RouterError):ex.declare_credential(router,name,apply=True)


@pytest.mark.parametrize('kind',['api','cli','web'])
def test_new_draft_and_pack_do_not_install(router,tmp_path,kind):
    tool=ex.new_template('acme.test',kind)
    receipt=ex.write_draft(tool,tmp_path/'draft.json',router.catalog)
    assert not receipt['installed'] and 'acme.test' not in router.catalog.tools
    bundle=ex.pack(tool,tmp_path/'bundle',router.catalog)
    assert bundle['generated_python_cli'] and ex.validate_bundle(tmp_path/'bundle')['valid']
    assert 'FAKE' not in (tmp_path/'bundle'/'tool.py').read_text()
    with pytest.raises(RouterError):ex.pack(tool,tmp_path/'bundle',router.catalog)
    (tmp_path/'bundle'/'tool.py').write_text('print("modified")')
    with pytest.raises(RouterError) as e:ex.validate_bundle(tmp_path/'bundle')
    assert e.value.code=='bundle_modified'


def test_update_is_cas_and_archives_old_definition(router,tmp_path):
    old,path=add(router,ex.new_template('acme.list','api'),tmp_path)
    updated={**old,'title':'New name'};path.write_text(canonical(updated));new=validate_manifest(updated,router.catalog)
    with pytest.raises(RouterError):ex.update_manifest(router.state,router.catalog,path,approval=digest(new),expected='bad')
    result=ex.update_manifest(router.state,router.catalog,path,approval=digest(new),expected=digest(old))
    assert result['previous_sha256']==digest(old)
    assert router.state.setting('tool_history:acme.list:'+digest(old))==old
    assert Catalog(router.state).get('acme.list')['title']=='New name'
    with pytest.raises(RouterError):ex.update_manifest(router.state,router.catalog,path,approval=digest(new),expected=digest(old))


def openapi(method='get'):
    return {'openapi':'3.0.3','servers':[{'url':'https://api.example.com/v2'}],
      'components':{'securitySchemes':{'Key':{'type':'apiKey','in':'header','name':'X-Service-Key'}}},
      'security':[{'Key':[]}], 'paths':{'/items/{id}':{method:{'operationId':'item',
      'parameters':[{'name':'id','in':'path','required':True,'schema':{'type':'string'}},
                    {'name':'q','in':'query','schema':{'type':'string'}},
                    {'name':'active','in':'query','schema':{'type':'boolean'}}]}}}}


def test_openapi_independent_expected_wire_request(router):
    tool=ex.import_openapi(openapi(),'item','acme.item',credential='acme.production')
    req=compile_request(router.state,tool,{'id':'hello world','active':False})
    assert req['url']=='https://api.example.com/v2/items/hello%20world?active=false'
    assert req['auth']=='header:X-Service-Key' and req['credential']=='acme.production'
    req=compile_request(router.state,tool,{'id':'one','q':'a & b'})
    assert req['url']=='https://api.example.com/v2/items/one?q=a+%26+b'
    assert tool['paid'] and not tool['permissions']


def test_openapi_json_body_and_local_refs(router):
    doc=openapi('post');doc['components']['schemas']={'Body':{'type':'object','properties':{'title':{'type':'string','nullable':True}},'required':['title']}}
    doc['paths']['/items/{id}']['post']['requestBody']={'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/Body'}}}}
    tool=ex.import_openapi(doc,'item','acme.item',credential='acme.production')
    assert tool['schema']['properties']['body']['properties']['title']['type']==['string','null']
    req=compile_request(router.state,tool,{'id':'one','body':{'title':None}})
    assert req['body']=={'title':None} and req['method']=='POST'
    assert 'external_write' in tool['permissions']


@pytest.mark.parametrize('change',[
 lambda d:d.update(openapi='2.0'),
 lambda d:d['servers'].append({'url':'https://another.example.com'}),
 lambda d:d['servers'][0].update(url='http://api.example.com'),
 lambda d:d['servers'][0].update(variables={'x':{}}),
 lambda d:d['paths']['/items/{id}']['get'].update(parameters=[{'name':'x','in':'cookie','schema':{'type':'string'}}]),
 lambda d:d['paths']['/items/{id}']['get']['parameters'][1].update(schema={'type':'array','items':{'type':'string'}}),
 lambda d:d['paths']['/items/{id}']['get']['parameters'][1].update(schema={'$ref':'https://evil.test/s.json'}),
 lambda d:d['paths']['/items/{id}']['get']['parameters'][1].update(schema={'$ref':'#/missing'}),
 lambda d:d['security'].append({'Other':[]}),
 lambda d:d['components']['securitySchemes']['Key'].update(name='Host'),
 lambda d:d['components']['securitySchemes']['Key'].update(type='oauth2'),
])
def test_openapi_refuses_unsupported_not_guessing(change):
    doc=openapi();change(doc)
    with pytest.raises(RouterError):ex.import_openapi(doc,'item','acme.item',credential='acme.production')


def test_custom_api_injects_exact_new_credential_and_redacts(router,tmp_path,workspace):
    ex.declare_credential(router,'acme',apply=True);connect_value(router,'acme','FAKE-custom-wire-key')
    tool=ex.new_template('acme.status','api');tool['paid']=False
    tool,path=add(router,tool,tmp_path)
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.headers['authorization']=='Bearer FAKE-custom-wire-key'
        return httpx.Response(200,json={'id':'one','echo':'FAKE-custom-wire-key'})
    router.net.close();router.net=Network(httpx.MockTransport(handler),resolver=lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    job=router.run(tool['id'],{},workspace,request_key='custom-api')
    assert job['status']=='completed' and len(calls)==1
    assert 'FAKE-custom-wire-key' not in canonical(router.public_job(job))
    assert router.run(tool['id'],{},workspace,request_key='custom-api')['id']==job['id'] and len(calls)==1


def command_tool():
    t=ex.new_template('acme.echo','cli',executable='acmecli');t['paid']=False
    t['command']={'argv':[],'output':'json','credential_env':{'ACME_KEY':'acme'},'credential_required':True}
    return t


def test_custom_cli_required_key_env_only_no_other_secrets(router,tmp_path,workspace,monkeypatch):
    ex.declare_credential(router,'acme',apply=True);connect_value(router,'acme','FAKE-cli-custom')
    t,_=add(router,command_tool(),tmp_path)
    script=tmp_path/'real-cli'
    script.write_text(f'#!{sys.executable}\nimport os,json,sys\nassert os.environ["ACME_KEY"]=="FAKE-cli-custom"\nassert "OTHER_SECRET" not in os.environ and "ATM_VAULT_PASSWORD" not in os.environ\nassert len(sys.argv)==1\nprint(json.dumps({{"ok":True,"echo":os.environ["ACME_KEY"]}}))\n');script.chmod(0o700)
    bind_cli(router.state,'acmecli',str(script));monkeypatch.setenv('OTHER_SECRET','never-forward');monkeypatch.setenv('ATM_VAULT_PASSWORD','never-forward')
    job=router.run(t['id'],{},workspace,grants=['execute_code'])
    assert job['status']=='completed'
    assert 'FAKE-cli-custom' not in canonical(router.public_job(job))


def test_cli_required_key_missing_stops_before_process(router,tmp_path,workspace):
    t,_=add(router,command_tool(),tmp_path)
    script=tmp_path/'never';marker=workspace/'should-not-exist'
    script.write_text(f'#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n');script.chmod(0o700)
    bind_cli(router.state,'acmecli',str(script))
    job=router.run(t['id'],{},workspace,grants=['execute_code'])
    assert job['status']=='failed' and job['data']['error']['code']=='missing_credential' and not marker.exists()


@pytest.mark.integration
def test_generated_cli_runs_real_ffprobe_and_reuses_key(router,tmp_path,workspace):
    probe=shutil.which('ffprobe');assert probe, 'Install ffprobe for this selected integration test'
    shutil.copy(Path(__file__).parent/'fixtures/tone.wav',workspace/'tone.wav')
    tool=ex.new_template('acme.probe','cli',executable='ffprobe');tool['paid']=False
    tool['schema']={'type':'object','properties':{'file':{'type':'string'}},'required':['file'],'additionalProperties':False}
    tool['command']={'argv':['-v','error','-show_format','-of','json','-i',{'file':'file'}],'output':'json'}
    tool,_=add(router,tool,tmp_path);bind_cli(router.state,'ffprobe',probe)
    ex.pack(tool,tmp_path/'cli',router.catalog)
    inputs=tmp_path/'input.json';inputs.write_text('{"file":"tone.wav"}')
    argv=[sys.executable,'-I',str(tmp_path/'cli/tool.py'),'--atm',shutil.which('atm'),'--home',str(router.state.home),'--workspace',str(workspace),'--input',str(inputs),'--request-key','same-task','--allow-code']
    one=subprocess.run(argv,capture_output=True,text=True,timeout=30);assert one.returncode==0,one.stdout
    two=subprocess.run(argv,capture_output=True,text=True,timeout=30);assert two.returncode==0,two.stdout
    assert json.loads(one.stdout)['id']==json.loads(two.stdout)['id']
    assert json.loads(one.stdout)['status']=='completed'
    changed={**tool,'title':'Changed'};router.state.set_setting('custom_tools',[changed])
    no=subprocess.run(argv,capture_output=True,text=True,timeout=30)
    assert no.returncode==2 and json.loads(no.stdout)['error']['code']=='definition_changed'


def test_custom_credentials_survive_cross_process_and_no_env(tmp_path):
    home=tmp_path/'home';env={**os.environ,'ATM_VAULT_PASSWORD':'fixture-long-password','ONCE_KEY':'FAKE-once-value'}
    def run(*args,environment=env):
        p=subprocess.run([sys.executable,'-m','agent_tool_maker','--home',str(home),*args],env=environment,capture_output=True,text=True,timeout=30)
        assert p.returncode==0,p.stdout
        return json.loads(p.stdout)
    run('vault','init','--backend','passphrase');run('credentials','declare','unknown.service','--apply');run('connect','unknown.service','--env','ONCE_KEY')
    fresh={k:v for k,v in env.items() if k not in {'ATM_VAULT_PASSWORD','ONCE_KEY'}}
    assert run('connect','unknown.service',environment=fresh)['status']=='already_configured'
    report=run('credentials','list',environment=fresh)
    assert any(c['provider']=='unknown.service' and c['configured'] for c in report['connections'])
    assert 'FAKE-once-value' not in canonical(report)


@pytest.mark.parametrize('field,value',[
 ('request',{'origin':'https://example.com','path':['bad']}),
 ('request',{'origin':'https://example.com','path':'/','method':[]}),
 ('schema',[]),('adapter',{}),('permissions',[{}])])
def test_malformed_model_manifests_fail_with_safe_error(field,value):
    t=ex.new_template('acme.status','api');t[field]=value
    with pytest.raises(RouterError):validate_manifest(t)


@pytest.mark.parametrize('doc',[
 {'openapi':'3.0.0','paths':[]},{'openapi':'3.0.0','paths':{'/':None}},
 {'openapi':'3.0.0','servers':{},'paths':{'/':{'get':{'operationId':'x'}}}},
 {'openapi':'3.0.0','servers':[None],'paths':{'/':{'get':{'operationId':'x'}}}},
])
def test_malformed_openapi_is_rejected_without_guessing(doc):
    with pytest.raises(RouterError):ex.import_openapi(doc,'x','acme.api')


def test_generated_cli_needs_no_atm_python_import_and_no_implicit_install(router,tmp_path,workspace):
    tool=ex.new_template('acme.empty','cli',executable='ffprobe')
    ex.pack(tool,tmp_path/'bundle',router.catalog)
    env={**os.environ,'PATH':str(tmp_path/'empty-bin')}
    p=subprocess.run([sys.executable,'-I',str(tmp_path/'bundle/tool.py'),'--input','-',
                      '--workspace',str(workspace),'--dry-run'],input='{}',env=env,
                     capture_output=True,text=True,timeout=10)
    assert p.returncode==2 and json.loads(p.stdout)['error']['code']=='atm_not_installed'
    assert not router.state.jobs()


def test_unknown_named_key_syncs_without_adapter_or_destination_declaration(tmp_path):
    from agent_tool_maker.engine import Router
    from agent_tool_maker.storage import State
    from agent_tool_maker.vault import Vault
    from agent_tool_maker.sync import Sync
    from agent_tool_maker.management import connections,known_credentials
    nodes=[];routers=[]
    try:
        for name in ['one','two']:
            vault=Vault(State(tmp_path/name),password='fixture-sync-only-password')
            vault.init('passphrase');node=Sync(vault);node.initialize(name);nodes.append(node)
            routers.append(Router(vault.state.home,vault=vault))
        a,b=nodes;ra,rb=routers
        ex.declare_credential(ra,'unknown.production',apply=True)
        connect_value(ra,'unknown.production','FAKE-UNKNOWN-SYNC-ONLY')
        a.trust(b.identity(),b.identity()['id'],send=['unknown.production'],apply=True)
        b.trust(a.identity(),a.identity()['id'],receive=['unknown.production'],apply=True)
        packet=a.export_packet(b.identity()['id'])
        assert 'FAKE-UNKNOWN-SYNC-ONLY' not in canonical(packet)
        b.import_packet(packet,apply=True)
        assert b.vault.get('unknown.production')=='FAKE-UNKNOWN-SYNC-ONLY'
        assert 'unknown.production' in known_credentials(rb)
        assert not rb.state.setting('credential_registry')
        assert any(row['provider']=='unknown.production' for row in connections(rb)['connections'])
    finally:
        for router in routers:router.close()

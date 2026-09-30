import copy,json,shutil
from pathlib import Path
import httpx,pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.errors import RouterError
from agent_tool_maker.maker import validate_manifest,read_manifest,digest,install,scaffold,execute_workflow,remove
from agent_tool_maker.network import Network
from agent_tool_maker.storage import canonical


def test_scaffold_validate_install_real_tool(router,tmp_path,workspace):
    p=tmp_path/'resize.json'
    r=scaffold(router.catalog,'my.resize','imagemagick.resize',p)
    assert not r['installed']
    tool=validate_manifest(read_manifest(p),router.catalog)
    assert tool['permissions']==['execute_code']
    with pytest.raises(RouterError):install(router.state,router.catalog,p,'wrong-hash')
    result=install(router.state,router.catalog,p,digest(tool));assert result['installed']=='my.resize'
    router.catalog=Catalog(router.state)
    with pytest.raises(RouterError):router.run('my.resize',tool['example'],workspace)
    remove(router.state,'my.resize')
    assert 'my.resize' not in Catalog(router.state).tools

@pytest.mark.parametrize('patch',[
 {'request':{'origin':'http://api.example.com','path':'/v1','auth':'none'}},
 {'request':{'origin':'https://api.example.com','path':'//evil.example/path','auth':'none'}},
 {'request':{'origin':'https://api.example.com','path':'/v1','auth':'none','headers':{'Authorization':'secret'}}},
 {'request':{'origin':'https://api.example.com','path':'/v1','auth':'none','local':True}},
 {'schema':{'type':'object','properties':{'a':{'$ref':'file:///etc/passwd'}}}},
 {'schema':{'type':'object','properties':{'a':{'$ref':'https://evil.example/schema'}}}},
 {'permissions':['root']},
 {'adapter':'python_eval'},
 {'unknown_config':'anything'},
])
def test_bad_manifests_rejected(router,patch):
    tool={'id':'custom.api','provider':'custom','title':'Custom','capabilities':['inspect'],'adapter':'rest',
          'schema':{'type':'object','properties':{},'additionalProperties':False},'request':{'origin':'https://api.example.com','path':'/v1','auth':'none'}}
    tool.update(patch)
    with pytest.raises(RouterError):validate_manifest(tool,router.catalog)

def test_custom_post_cannot_hide_write_permission(router):
    t={'id':'custom.post','provider':'custom','title':'Post','capabilities':['inspect'],'adapter':'rest',
       'schema':{'type':'object','properties':{}},'request':{'origin':'https://api.example.com','path':'/v1','method':'POST','auth':'none','body':{}}}
    assert validate_manifest(t)['permissions']==['external_write']

def recipe():
    return {'id':'workflow.media','provider':'local','title':'Local media delivery','capabilities':['image_edit'],
            'adapter':'workflow','schema':{'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False},
            'steps':[{'name':'resize','tool':'imagemagick.resize','inputs':{'path':'$input.path','geometry':'8x8'}},
                     {'name':'webp','tool':'imagemagick.webp','inputs':{'path':'$steps.resize.data.artifacts.0.path','quality':75}}]}

@pytest.mark.integration
def test_real_workflow_resume_no_duplicate_children(router,tmp_path,workspace):
    binary=shutil.which('magick')
    if not binary:pytest.skip('ImageMagick unavailable')
    bind_cli(router.state,'magick',binary)
    shutil.copyfile(Path(__file__).parent/'fixtures/image.png',workspace/'image.png')
    t=validate_manifest(recipe(),router.catalog);p=tmp_path/'workflow.json';p.write_text(canonical(t))
    install(router.state,router.catalog,p,digest(t));router.catalog=Catalog(router.state)
    job=router.run(t['id'],{'path':'image.png'},workspace,request_key='media-release')
    assert job['status']=='completed',job
    assert len(job['data']['children'])==2
    from PIL import Image
    with Image.open(job['data']['artifacts'][2]['path']) as im:assert im.format=='WEBP'
    second=router.run(t['id'],{'path':'image.png'},workspace,request_key='media-release')
    assert second['id']==job['id'];assert len(router.state.jobs())==3

def test_workflow_future_reference_and_nesting_blocked(router):
    t=recipe();t['steps'][0]['inputs']['path']='$steps.webp.data.artifacts.0.path'
    with pytest.raises(RouterError):validate_manifest(t,router.catalog)
    t=recipe();router.catalog.tools['nested']={'adapter':'workflow'};t['steps'][0]['tool']='nested'
    with pytest.raises(RouterError):validate_manifest(t,router.catalog)

def test_workflow_aggregates_child_permissions_and_cost(router):
    t=recipe();t['steps']=[{'name':'post','tool':'buffer.schedule','inputs':{'channel_id':'channel','text':'hello'}}]
    normalized=validate_manifest(t,router.catalog)
    assert normalized['paid'] and 'external_write' in normalized['permissions']

def test_workflow_pause_for_browser_and_resume(router,tmp_path,workspace,assets):
    t=recipe();t['steps']=[{'name':'manual','tool':'tripo.web','inputs':{'task':'make a fixture'}}]
    t=validate_manifest(t,router.catalog);p=tmp_path/'wf.json';p.write_text(canonical(t))
    install(router.state,router.catalog,p,digest(t));router.catalog=Catalog(router.state)
    j=router.run(t['id'],{'path':'unused'},workspace,allow_paid=True,request_key='browser-wf')
    assert j['status']=='waiting';child=j['data']['children'][0]['job_id']
    f=workspace/'model.glb';f.write_bytes(assets['model.glb'])
    router.complete_browser(child,[str(f)],router.catalog.get('tripo.web')['url'])
    final=router.refresh(j['id']);assert final['status']=='completed',final
    assert len(router.state.jobs())==2

def test_definition_change_conflicts_with_request_key(router,workspace):
    t=router.catalog.tools['slack.send'];router.vault.put('slack','FAKE_TOKEN')
    router.net.client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'ok':True})))
    j=router.run('slack.send',t['example'],workspace,grants=['external_write'],request_key='once')
    assert j['status']=='completed'
    t['request']['path']='/api/other'
    with pytest.raises(RouterError) as err:router.run('slack.send',t['example'],workspace,grants=['external_write'],request_key='once')
    assert err.value.code=='idempotency_conflict'

def test_human_handoff_requires_real_file(router,workspace):
    j=router.run('fiverr.handoff',{'task':'Request an approved quote'},workspace)
    assert j['status']=='requires_human'
    with pytest.raises(RouterError):router.complete_browser(j['id'],[str(workspace/'missing')],'https://www.fiverr.com/')
    p=workspace/'quote.md';p.write_text('Test fixture quotation, not a real purchase.')
    done=router.complete_browser(j['id'],[str(p)],'https://www.fiverr.com/')
    assert done['status']=='completed'
    assert done['data']['verification']=='file_exists_and_hash'

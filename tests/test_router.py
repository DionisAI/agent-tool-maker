from concurrent.futures import ThreadPoolExecutor
import json
import httpx
import pytest
from agent_tool_maker.catalog import add_browser_tool
from agent_tool_maker.errors import RouterError
from agent_tool_maker.engine import safe_endpoint
from agent_tool_maker.storage import State

PAYLOADS=[('fal.generate',{'endpoint':'fal-ai/flux/schnell','arguments':{'prompt':'a cube'}}),
 ('tripo.text_to_3d',{'prompt':'a robot'}),('higgsfield.generate',{'endpoint':'higgsfield-ai/soul/v2/standard','arguments':{'prompt':'a lake'}}),
 ('elevenlabs.tts',{'text':'hello','voice_id':'voice-id'}),('exa.search',{'query':'documentation'}),('firecrawl.scrape',{'url':'https://example.com'})]

@pytest.mark.parametrize('tool,payload',PAYLOADS)
def test_native_lifecycle(router,workspace,tool,payload):
    job=router.run(tool,payload,workspace,allow_paid=True,request_key=tool)
    if job['status']=='queued': job=router.refresh(job['id'])
    assert job['status']=='completed',job
    assert job['data']['artifacts']
    assert job['data']['cost_usd'] is None
    for artifact in job['data']['artifacts']:
        from pathlib import Path
        assert Path(artifact['path']).is_file()
        assert len(artifact['sha256'])==64
    assert 'FAKE_' not in json.dumps(router.public_job(job))

@pytest.mark.parametrize('tool,payload',PAYLOADS)
def test_paid_confirmation_before_network(router,workspace,fixture_provider,tool,payload):
    with pytest.raises(RouterError,match='spend'): router.run(tool,payload,workspace)
    assert fixture_provider.calls==[]
    assert router.state.jobs()==[]

@pytest.mark.parametrize('endpoint',['https://evil.example/x','../secret','fal-ai/../secrets','/leading','model?x=1','model#x','model%2fother','model\\x','model//x'])
def test_unsafe_endpoint(endpoint):
    with pytest.raises(RouterError): safe_endpoint(endpoint)


def test_request_key_reuses_job(router,workspace,fixture_provider):
    p={'endpoint':'fal-ai/flux/schnell','arguments':{'prompt':'same'}}
    a=router.run('fal.generate',p,workspace,allow_paid=True,request_key='one')
    b=router.run('fal.generate',p,workspace,allow_paid=True,request_key='one')
    assert a['id']==b['id']
    assert len([x for x in fixture_provider.calls if x[0]=='POST'])==1
    with pytest.raises(RouterError,match='different inputs'):
        router.run('fal.generate',{**p,'arguments':{'prompt':'different'}},workspace,allow_paid=True,request_key='one')


def test_concurrent_job_claim_is_unique(router,workspace):
    def claim(_):
        return State(router.state.home).create_job('fal.generate',{'x':1},workspace,'concurrent')
    with ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(claim,range(16)))
    assert sum(new for job,new in results)==1
    assert len({job['id'] for job,new in results})==1


@pytest.mark.parametrize('body',[b'{not json',b'['*200000],ids=['invalid','nested'])
def test_nested_submission_json_is_unknown_like_invalid_json(router,workspace,fixture_provider,body):
    def handler(request):
        fixture_provider.calls.append((request.method,str(request.url)))
        return httpx.Response(200,content=body)
    router.net.client.close();router.net.client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
    p={'endpoint':'fal-ai/flux/schnell','arguments':{'prompt':'deep'}}
    job=router.run('fal.generate',p,workspace,allow_paid=True,request_key='deep')
    assert job['status']=='submission_unknown' and job['data']['error']['code']=='upstream_schema'
    assert job['data']['error']['outcome_uncertain'] is True
    again=router.run('fal.generate',p,workspace,allow_paid=True,request_key='deep')
    assert again['id']==job['id'] and len(fixture_provider.calls)==1


@pytest.mark.parametrize('status,result',[(b'{not json',None),(b'['*200000,None),(None,b'{"images":'+b'['*5000+b']'*5000+b'}')],
                         ids=['invalid','nested','parsed'])
def test_nested_status_json_keeps_the_job_without_resubmitting(router,workspace,fixture_provider,status,result):
    job=router.run('fal.generate',{'endpoint':'fal-ai/flux/schnell','arguments':{'prompt':'poll'}},workspace,allow_paid=True,request_key='poll')
    assert job['status']=='queued'
    def handler(request):
        polling=request.url.path.endswith('/status')
        if polling and status or not polling and result: return httpx.Response(200,content=status if polling else result)
        return fixture_provider(request)
    router.net.client.close();router.net.client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
    polled=router.refresh(job['id'])
    assert polled['status']=='queued' and polled['data']['last_error']['code']=='upstream_schema'
    assert len([x for x in fixture_provider.calls if x[0]=='POST'])==1


def test_restart_can_poll_without_resubmitting(router,workspace,fixture_provider):
    from agent_tool_maker.engine import Router
    a=router.run('tripo.text_to_3d',{'prompt':'cube'},workspace,allow_paid=True,request_key='resume')
    second=Router(router.state.home,network=router.net,vault=router.vault)
    b=second.refresh(a['id'])
    assert b['status']=='completed'
    assert len([x for x in fixture_provider.calls if x[0]=='POST'])==1


def test_route_is_deterministic_and_no_network(router,fixture_provider):
    r=router.route('生成 Tripo 3D 模型',capability='3d',allow_browser=True)
    assert r['recommended']=='tripo.text_to_3d'
    assert r==router.route('生成 Tripo 3D 模型',capability='3d',allow_browser=True)
    assert fixture_provider.calls==[]


def test_browser_opt_in_and_missing_key(router):
    router.vault.delete('tripo');router.vault.delete('fal')
    assert router.route('Tripo 模型',capability='3d')['recommended'] is None
    assert router.route('Tripo 模型',capability='3d',allow_browser=True)['recommended']=='tripo.web'


def test_browser_preference(router):
    assert router.route('Tripo 3D',allow_browser=True,prefer='browser')['recommended']=='tripo.web'


def test_unknown_capability_has_no_fake_recommendation(router):
    assert router.route('quantum-gravity-xyz')['recommended'] is None

@pytest.mark.parametrize('tool,payload',[('elevenlabs.tts',{'text':'hello'}),('tripo.text_to_3d',{'prompt':''}),
 ('exa.search',{'query':'q','numResults':1000}),('fal.generate',{'endpoint':'x','arguments':{},'headers':{'x':'bad'}})])
def test_invalid_input_rejected_before_execution(router,workspace,fixture_provider,tool,payload):
    with pytest.raises(RouterError): router.run(tool,payload,workspace,allow_paid=True)
    assert not fixture_provider.calls


def test_legacy_catalog_stub_is_not_silently_executed(router,workspace):
    # The ambiguous v0.1 stub is removed; explicit inspect/render actions replace it.
    with pytest.raises(RouterError) as error: router.run('blender.cli',{},workspace)
    assert error.value.code == 'unknown_tool'
    assert router.catalog.get('blender.inspect')['adapter'] == 'command'


def test_custom_browser_is_data_not_code(router):
    new=add_browser_tool(router.state,'mytool.web','Custom tool','https://example.com/','image')
    from agent_tool_maker.catalog import Catalog
    assert Catalog(router.state).get('mytool.web')['implementation']=='browser'
    with pytest.raises(RouterError): add_browser_tool(router.state,'mytool.web','Again','https://example.com/','image')
    with pytest.raises(RouterError): add_browser_tool(router.state,'bad.web','Bad','javascript:alert(1)','image')

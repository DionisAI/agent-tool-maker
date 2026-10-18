import json,sys,threading
from pathlib import Path
import httpx,pytest
from agent_tool_maker.mcp_bridge import bind_server
from agent_tool_maker.errors import RouterError

INIT={'protocolVersion':'2025-06-18','serverInfo':{'name':'fixture','version':'1'},'capabilities':{'tools':{}}}
TOOLS=[{'name':'increment','description':'Fixture counter','inputSchema':{'type':'object','properties':{'amount':{'type':'integer'}},'required':['amount'],'additionalProperties':False}},
       {'name':'read','inputSchema':{'type':'object','properties':{},'additionalProperties':False}}]

def stdio_config(tmp_path):
    p=tmp_path/'mcp-server'
    p.write_text(f'''#!{sys.executable}
import sys,json,os
assert 'ATM_VAULT_PASSWORD' not in os.environ
counter=0
for line in sys.stdin:
 q=json.loads(line)
 if 'id' not in q:continue
 method=q.get('method')
 if method=='initialize':result={INIT!r}
 elif method=='tools/list':result={{'tools':{TOOLS!r}}}
 elif method=='tools/call':
  if q['params']['name']=='increment':counter+=q['params']['arguments']['amount']
  result={{'content':[{{'type':'text','text':str(counter)}}]}}
 else:result={{}}
 print(json.dumps({{'jsonrpc':'2.0','id':q['id'],'result':result}}),flush=True)
''');p.chmod(0o700)
    return {'transport':'stdio','command':str(p),'args':[],'allow_tools':['increment','read'],'timeout':5}

@pytest.mark.integration
def test_actual_stdio_discovery_and_stateful_batch(router,workspace,tmp_path):
    bind_server(router.state,'playwright',stdio_config(tmp_path))
    j=router.run('playwright.mcp_tools',{},workspace)
    assert j['status']=='completed',j
    assert len(j['data']['result']['tools'])==2
    args={'calls':[{'name':'increment','arguments':{'amount':3}},{'name':'read','arguments':{}}]}
    j=router.run('playwright.mcp_batch',args,workspace,allow_paid=True,grants=['external_write','execute_code'])
    assert j['status']=='completed',j
    assert [x['result']['content'][0]['text'] for x in j['data']['result']['results']]==['3','3']

@pytest.mark.integration
def test_mcp_refuses_nonallowlisted_tool_before_any_call(router,workspace,tmp_path):
    cfg=stdio_config(tmp_path);cfg['allow_tools']=['increment'];bind_server(router.state,'playwright',cfg)
    j=router.run('playwright.mcp_batch',{'calls':[{'name':'increment','arguments':{'amount':1}},{'name':'read','arguments':{}}]},workspace,allow_paid=True,grants=['external_write','execute_code'])
    assert j['status']=='failed' and j['data']['error']['code']=='mcp_tool_not_approved'
    assert 'mcp_started' not in j['data']

@pytest.mark.integration
def test_mcp_full_batch_schema_validation_before_first_call(router,workspace,tmp_path):
    bind_server(router.state,'playwright',stdio_config(tmp_path))
    j=router.run('playwright.mcp_batch',{'calls':[{'name':'increment','arguments':{'amount':1}},{'name':'increment','arguments':{'amount':'bad'}}]},workspace,allow_paid=True,grants=['external_write','execute_code'])
    assert j['status']=='failed' and j['data']['error']['code']=='invalid_input'
    assert 'mcp_started' not in j['data']

@pytest.mark.integration
@pytest.mark.parametrize('line',['{not json','['*200000],ids=['invalid','nested'])
def test_stdio_nested_json_is_interrupted_like_invalid_json(router,workspace,tmp_path,monkeypatch,line):
    cfg=stdio_config(tmp_path);p=Path(cfg['command'])
    p.write_text(p.read_text().replace(' print(json.dumps(',f" if method=='tools/call':print({line!r},flush=True);continue\n print(json.dumps(",1))
    bind_server(router.state,'playwright',cfg);hooked=[]
    monkeypatch.setattr(threading,'excepthook',lambda args:hooked.append(args.exc_type))
    kwargs={'request_key':'deep','allow_paid':True,'grants':['external_write','execute_code']}
    j=router.run('playwright.mcp_batch',{'calls':[{'name':'read','arguments':{}}]},workspace,**kwargs)
    assert j['status']=='submission_unknown' and j['data']['error']['code']=='mcp_interrupted' and j['data']['error']['outcome_uncertain'] is True
    assert hooked==[] and router.run('playwright.mcp_batch',{'calls':[{'name':'read','arguments':{}}]},workspace,**kwargs)['id']==j['id']

@pytest.mark.parametrize('sse',[False,True])
def test_streamable_http_json_sse_and_session_headers(router,workspace,sse):
    calls=[]
    bind_server(router.state,'figma',{'transport':'http','url':'https://mcp.example.com/mcp','allow_tools':['read']})
    def handler(req):
        if req.method=='DELETE':return httpx.Response(204)
        q=json.loads(req.content);calls.append(q)
        if q.get('method')=='initialize':value=INIT
        else:
            assert req.headers['mcp-session-id']=='fixture-session'
            assert req.headers['mcp-protocol-version']=='2025-06-18'
            if q.get('method')=='notifications/initialized':return httpx.Response(202)
            value={'tools':TOOLS} if q['method']=='tools/list' else {'content':[{'type':'text','text':'ok'}]}
        payload={'jsonrpc':'2.0','id':q['id'],'result':value}
        if sse:return httpx.Response(200,headers={'Content-Type':'text/event-stream','Mcp-Session-Id':'fixture-session'},content=('data: '+json.dumps(payload)+'\n\n').encode())
        return httpx.Response(200,headers={'Mcp-Session-Id':'fixture-session'},json=payload)
    router.net.client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
    j=router.run('figma.mcp_batch',{'calls':[{'name':'read','arguments':{}}]},workspace,allow_paid=True,grants=['external_write','execute_code'])
    assert j['status']=='completed',j
    assert [c['method'] for c in calls]==['initialize','notifications/initialized','tools/list','tools/call']

@pytest.mark.parametrize('cfg',[
 {'transport':'http','url':'http://evil.example/mcp'},
 {'transport':'http','url':'https://api.example.com/mcp?token=secret'},
 {'transport':'http','url':'http://192.168.1.5/mcp','allow_local':True},
 {'transport':'stdio','command':'/nonexistent'},
 {'transport':'http','url':'https://api.example.com','headers':{'Authorization':'SECRET'}},
])
def test_invalid_mcp_binding_rejected(router,cfg):
    with pytest.raises(RouterError):bind_server(router.state,'figma',cfg)

@pytest.mark.parametrize('sse',[False,True])
@pytest.mark.parametrize('raw',['{not json','['*200000],ids=['invalid','nested'])
def test_streamable_http_nested_json_is_interrupted_like_invalid_json(router,workspace,raw,sse):
    calls=[]
    bind_server(router.state,'figma',{'transport':'http','url':'https://mcp.example.com/mcp','allow_tools':['read']})
    def handler(req):
        if req.method=='DELETE':return httpx.Response(204)
        q=json.loads(req.content);calls.append(q['method'])
        if q['method']=='notifications/initialized':return httpx.Response(202)
        body=raw if q['method']=='tools/call' else json.dumps({'jsonrpc':'2.0','id':q['id'],'result':INIT if q['method']=='initialize' else {'tools':TOOLS}})
        if sse:return httpx.Response(200,headers={'Content-Type':'text/event-stream'},content=('data: '+body+'\n\n').encode())
        return httpx.Response(200,headers={'Content-Type':'application/json'},content=body.encode())
    router.net.client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
    kwargs={'request_key':'deep','allow_paid':True,'grants':['external_write','execute_code']}
    j=router.run('figma.mcp_batch',{'calls':[{'name':'read','arguments':{}}]},workspace,**kwargs)
    assert j['status']=='submission_unknown' and j['data']['error']['code']=='mcp_interrupted' and j['data']['error']['outcome_uncertain'] is True
    assert router.run('figma.mcp_batch',{'calls':[{'name':'read','arguments':{}}]},workspace,**kwargs)['id']==j['id'] and calls.count('tools/call')==1

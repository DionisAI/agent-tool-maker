import json,sys
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

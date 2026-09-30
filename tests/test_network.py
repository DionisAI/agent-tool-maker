import httpx
import pytest
from agent_tool_maker.network import checked_url,public_address,Network
from agent_tool_maker.demo import fixture_resolver,FixtureProvider
from agent_tool_maker.errors import RouterError

@pytest.mark.parametrize('url',['http://example.com','file:///etc/passwd','https://user:password@example.com','https://example.com:8443','https://example.com/#x','javascript:alert(1)'])
def test_unsafe_urls(url):
    with pytest.raises(RouterError): checked_url(url)


def test_foreign_origin():
    with pytest.raises(RouterError): checked_url('https://evil.example/x',{'api.elevenlabs.io'})

@pytest.mark.parametrize('ip',['127.0.0.1','10.0.0.1','169.254.169.254','192.168.1.1','::1','fc00::1','0.0.0.0'])
def test_private_dns_rejected(ip):
    with pytest.raises(RouterError): public_address('https://assets.example.test/a',lambda *a,**k:[(2,1,6,'',(ip,443))])


def test_no_secret_on_artifact_download(router,workspace):
    seen=[];fixture=FixtureProvider()
    def handler(r):
        seen.append(r)
        return fixture(r)
    router.net=Network(httpx.MockTransport(handler),fixture_resolver)
    job=router.run('fal.generate',{'endpoint':'fal-ai/flux/schnell','arguments':{'prompt':'x'}},workspace,allow_paid=True)
    assert router.refresh(job['id'])['status']=='completed'
    for r in seen:
        if r.url.host=='assets.example.test':
            assert 'authorization' not in r.headers
            assert 'xi-api-key' not in r.headers
            assert 'cookie' not in r.headers


def test_api_redirect_not_followed(router,workspace):
    seen=[]
    def handler(r):
        seen.append(r)
        return httpx.Response(302,headers={'location':'https://evil.example/steal'})
    router.net=Network(httpx.MockTransport(handler))
    j=router.run('tripo.text_to_3d',{'prompt':'x'},workspace,allow_paid=True)
    assert j['status']=='failed' and len(seen)==1


def test_ambiguous_submission_not_retried(router,workspace):
    seen=[]
    def handler(r):
        seen.append(r);raise httpx.ReadTimeout('secret upstream body')
    router.net=Network(httpx.MockTransport(handler))
    first=router.run('tripo.text_to_3d',{'prompt':'x'},workspace,allow_paid=True,request_key='ambiguous')
    second=router.run('tripo.text_to_3d',{'prompt':'x'},workspace,allow_paid=True,request_key='ambiguous')
    assert first['status']=='submission_unknown'
    assert second['id']==first['id'] and len(seen)==1
    assert 'secret upstream body' not in str(first)


def test_poll_error_retains_existing_task(router,workspace):
    j=router.run('tripo.text_to_3d',{'prompt':'x'},workspace,allow_paid=True)
    router.net=Network(httpx.MockTransport(lambda r:httpx.Response(503)))
    result=router.refresh(j['id'])
    assert result['status']=='queued' and result['data']['last_error']


def test_fal_completed_with_error_is_failure(router,workspace):
    j=router.run('fal.generate',{'endpoint':'fal-ai/flux/schnell','arguments':{}},workspace,allow_paid=True)
    router.net=Network(httpx.MockTransport(lambda r:httpx.Response(200,json={'status':'COMPLETED','error':'broken'})))
    assert router.refresh(j['id'])['status']=='failed'


def test_auth_error_does_not_print_body(router,workspace):
    router.net=Network(httpx.MockTransport(lambda r:httpx.Response(401,text='FAKE_tripo SECRET RESPONSE')))
    j=router.run('tripo.text_to_3d',{'prompt':'x'},workspace,allow_paid=True)
    assert 'SECRET RESPONSE' not in str(j) and 'FAKE_tripo' not in str(j)


def test_download_redirect_private_blocked(assets):
    def resolver(host,*a,**k):
        return fixture_resolver() if host=='public.test' else [(2,1,6,'',('127.0.0.1',443))]
    n=Network(httpx.MockTransport(lambda r:httpx.Response(302,headers={'location':'https://internal.test/secret'})),resolver)
    with pytest.raises(RouterError,match='private'): n.download('https://public.test/file')
    n.close()

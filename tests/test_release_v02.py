import copy,json,shutil,subprocess,os
from pathlib import Path
import httpx,pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli import main
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.errors import RouterError
from agent_tool_maker.maker import validate_manifest,install,digest
from agent_tool_maker.vault import Vault
from agent_tool_maker.storage import canonical
ROOT=Path(__file__).resolve().parents[1]

def test_66_research_items_have_explicit_implemented_scope_and_gap():
    r=json.loads((ROOT/'src/agent_tool_maker/data/roadmap.json').read_text())
    assert r['scope_count']==len(r['records'])==66
    catalog=Catalog().tools
    assert r['action_count']==len(catalog)==157
    assert len({x['id'] for x in r['records']})==66
    for x in r['records']:
        assert x['remaining_work'] and x['action_ids'] and x['sources']
        assert not x['native_vendor_live_tested']
        for aid in x['action_ids']:assert aid in catalog

def test_legacy_vault_metadata_still_decrypts(router):
    original=router.state.setting('vault');original.pop('service')
    router.state.set_setting('vault',original)
    v=Vault(router.state,password='unit-test-passphrase-long')
    assert v.get('elevenlabs')=='FAKE_elevenlabs'

def test_new_cli_commands_and_skill(tmp_path,capsys):
    base=['--home',str(tmp_path/'state')]
    for command in [['init'],['stats'],['roadmap'],['describe','wrangler.deploy'],['skill','export','--destination',str(tmp_path/'skills')]]:
        assert main(base+command)==0
        data=json.loads(capsys.readouterr().out);assert data
    text=(tmp_path/'skills/agent-tool-maker/SKILL.md').read_text()
    assert 'make validate' in text and 'make install' in text and 'submission_unknown' in text
    assert 'Agent Tool Router' not in text

def test_custom_api_cannot_send_credentials_to_private_host(router,tmp_path,workspace):
    t={'id':'custom.private','provider':'custom','title':'Bad private destination','adapter':'rest','capabilities':['inspect'],
       'schema':{'type':'object','properties':{},'additionalProperties':False},
       'request':{'origin':'https://127.0.0.1','path':'/','auth':'bearer'},'credential':'custom'}
    p=tmp_path/'custom.json';p.write_text(canonical(t))
    with pytest.raises(RouterError) as refused:install(router.state,router.catalog,p,digest(t))
    assert refused.value.code=='bad_manifest'
    # A definition installed before origin review existed must still never reach the private host.
    legacy=validate_manifest({**t,'request':{**t['request'],'origin':'https://api.example.com'}},router.catalog);legacy['request']['origin']='https://127.0.0.1'
    router.state.set_setting('custom_tools',[legacy])
    router.catalog=Catalog(router.state);router.vault.put('custom','NEVER_SEND_THIS');seen=[]
    router.net.client=httpx.Client(transport=httpx.MockTransport(lambda req:seen.append(req)))
    j=router.run('custom.private',{},workspace)
    assert j['status']=='failed' and not seen

@pytest.mark.parametrize('data',[{'status':'error','message':'sensitive'}, {'status_code':20000,'tasks':[{'status_code':40001}]}])
def test_nested_vendor_application_failures(router,workspace,data):
    router.vault.put('dataforseo','fixture:password')
    router.net.client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=data)))
    j=router.run('dataforseo.search_volume',router.catalog.get('dataforseo.search_volume')['example'],workspace,allow_paid=True)
    assert j['status']=='submission_unknown'

@pytest.mark.integration
@pytest.mark.parametrize('tool', ['ffmpeg.trim','ffmpeg.thumbnail'])
def test_real_added_ffmpeg_actions(router,workspace,tool):
    exe=shutil.which('ffmpeg')
    if not exe:pytest.skip('FFmpeg unavailable')
    bind_cli(router.state,'ffmpeg',exe)
    # Real local synthetic video, not an externally generated asset.
    subprocess.run([exe,'-nostdin','-loglevel','error','-f','lavfi','-i','color=c=blue:s=64x64:d=1','-c:v','mpeg4','-y',str(workspace/'video.mp4')],check=True,timeout=15)
    data={'path':'video.mp4','start':0,'duration':.5} if tool.endswith('trim') else {'path':'video.mp4','at':0}
    j=router.run(tool,data,workspace)
    assert j['status']=='completed',j
    p=Path(j['data']['artifacts'][0]['path']);assert p.stat().st_size>0
    if tool.endswith('thumbnail'):
        from PIL import Image
        with Image.open(p) as im:assert im.size==(64,64)
    else:
        raw=subprocess.check_output([shutil.which('ffprobe'),'-v','error','-show_entries','format=duration','-of','json',str(p)],timeout=15)
        assert 0<float(json.loads(raw)['format']['duration'])<1

@pytest.mark.browser
def test_roadmap_real_browser_search_and_status_filter(tmp_path):
    from playwright.sync_api import sync_playwright
    exe=os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not exe:pytest.skip('Chromium unavailable')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=exe,headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1400,'height':1000});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.set_content((ROOT/'docs/ROADMAP.html').read_text())
        assert page.locator('tbody tr').count()==66
        page.locator('#q').fill('Cloudflare')
        assert page.locator('tbody tr:visible').count()>=2
        page.locator('#q').fill('');page.locator('#filter').select_option('handoff_only')
        assert page.locator('tbody tr:visible').count()==9
        page.locator('#filter').select_option('');page.locator('#q').fill('')
        page.screenshot(path=str(tmp_path/'roadmap.png'),full_page=False)
        assert not errors
        browser.close()

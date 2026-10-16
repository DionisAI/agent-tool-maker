"""Intercepted native fixture for the full image-delivery path, never live XYQ."""
import io,json,subprocess,sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'))
from test_xyq_web_results import setup as setup_result,MEDIA,THREAD,RESOURCE

def prepare(page,scenario='normal'):
    setup_result(page)
    out=io.BytesIO();Image.new('RGB',(81,108),'blue').save(out,format='PNG')
    page.route(MEDIA,lambda route:route.fulfill(status=200,content_type='image/png',body=out.getvalue(),headers={'Content-Disposition':'attachment; filename="fixture.png"'}))
    page.locator('#download').evaluate('(e,url)=>e.addEventListener("click",()=>{location.href=url})',MEDIA)
    if scenario=='covered':page.evaluate("document.body.insertAdjacentHTML('beforeend','<div style=\"position:fixed;inset:0;z-index:99\"></div>')")
    if scenario=='disabled':page.locator('#download').evaluate('e=>e.disabled=true')

def rpc(page,config,download_root,scenario='normal'):
    proc=subprocess.Popen(['node',str(ROOT/'tests/fixtures/xyq_download_rpc.mjs'),json.dumps(config)],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    waiting=None;clicks=0
    def reply(call,**data):proc.stdin.write(json.dumps({'id':call['id'],**data})+'\n');proc.stdin.flush()
    try:
        for line in proc.stdout:
            r=json.loads(line)
            if r['type']=='done':proc.wait(timeout=5);assert proc.returncode==0,proc.stderr.read();return r,clicks
            if r['method']=='evaluate':
                assert any(r['source'].startswith('function '+name+'(') for name in ('readConversationResultsDOM','readDownloadInputDOM'))
                reply(r,value=page.evaluate(r['source'],r['arg']))
            elif r['method']=='waitForDownload':
                assert r['pattern']=='fixture.png' and r['timeout']==20000 and waiting is None;waiting=r
            elif r['method']=='nativeClick':
                clicks+=1;assert waiting is not None
                ledger=Path(config['workspace'])/'.atm/xyq-result-downloads';assert (ledger/'active.lock').is_file()
                record=json.loads(next(p for p in ledger.glob('*.json') if not p.name.endswith('.delivery.json')).read_bytes());assert record['status']=='download_dispatch_claimed'
                with page.expect_download(timeout=8000) as event:page.mouse.click(r['x'],r['y'])
                download=event.value;destination=download_root/'fixture.png';assert not destination.exists();download.save_as(str(destination))
                reply(r,**({'error':'fixture_lost_native_ack'} if scenario=='lost_ack' else {'value':None}))
                reply(waiting,value={'downloaded':True,'state':'complete','filename':str(destination),'url':'blob:https://xyq.jianying.com/FIXTURE' if scenario=='blob' else download.url});waiting=None
            else:raise AssertionError('Unknown fixture method')
        raise AssertionError('No terminal native result')
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

def bridge_main(download_root,chromium,scenario='normal'):
    from playwright.sync_api import sync_playwright
    argv=sys.argv[1:];assert argv[:3]==['__opencli_shim','xyq-web','result-download-bound'];settings=json.loads(argv[argv.index('--settings')+1]);workspace=argv[argv.index('--workspace')+1]
    assert settings['thread_id']==THREAD and settings['result_id']==RESOURCE
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=chromium,headless=True)
        try:
            page=browser.new_page(viewport={'width':1280,'height':900});prepare(page,scenario)
            result,clicks=rpc(page,{'operation':'download','settings':settings,'workspace':workspace,'adapter_pin':argv[argv.index('--pin')+1]},Path(download_root),scenario)
            (Path(workspace)/'fixture-native-click-count').write_text(str(clicks))
            if 'error' in result:print(json.dumps({'error':result['error']}));return 2
            print(json.dumps(result['result']));return 0
        finally:browser.close()

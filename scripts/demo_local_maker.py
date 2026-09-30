"""Explicit local demo: install a reviewed sample workflow, execute real ImageMagick.
No network, accounts, paid services or automatic external publishing are used.
"""
import argparse,base64,html,json,shutil
from pathlib import Path
from agent_tool_maker.engine import Router
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.demo import fixture_assets
from agent_tool_maker.maker import validate_manifest,install,digest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    out=args.out.resolve()
    if out.exists() and any(out.iterdir()):raise SystemExit('Use a new empty output directory.')
    binary=shutil.which('magick')
    if not binary:raise SystemExit('ImageMagick 7 (magick) must be installed by the user first.')
    out.mkdir(parents=True,exist_ok=True)
    (out/'image.png').write_bytes(fixture_assets()['image.png'])
    recipe={'id':'workflow.web_assets','provider':'local','title':'Make web assets','capabilities':['image_edit'],'adapter':'workflow',
            'schema':{'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False},
            'steps':[{'name':'resize','tool':'imagemagick.resize','inputs':{'path':'$input.path','geometry':'64x64'}},
                     {'name':'webp','tool':'imagemagick.webp','inputs':{'path':'$steps.resize.data.artifacts.0.path','quality':80}}]}
    router=Router(out/'.demo-state')
    try:
        bind_cli(router.state,'magick',binary)
        normalized=validate_manifest(recipe,router.catalog);manifest=out/'approved-demo-workflow.json';manifest.write_text(json.dumps(normalized,indent=2))
        # Executing this demo is explicit approval of this fixed, local-only recipe.
        installed=install(router.state,router.catalog,manifest,digest(normalized));router.catalog=Catalog(router.state)
        job=router.run(recipe['id'],{'path':'image.png'},out,request_key='local-demo-once')
        assert job['status']=='completed',job
        again=router.run(recipe['id'],{'path':'image.png'},out,request_key='local-demo-once')
        assert again['id']==job['id'] and len(router.state.jobs())==3
        paths=[a['path'] for a in job['data']['artifacts'] if a['extension'] in {'.png','.webp'}]
        imgs=['<article><h2>Original fixture</h2><img src="data:image/png;base64,'+base64.b64encode((out/'image.png').read_bytes()).decode()+'"></article>']
        for path in paths:
            f=Path(path);mime='image/webp' if f.suffix=='.webp' else 'image/png'
            imgs.append('<article><h2>'+html.escape(f.name)+'</h2><img src="data:'+mime+';base64,'+base64.b64encode(f.read_bytes()).decode()+'"></article>')
        receipt={'mode':'real_local_ImageMagick_with_synthetic_input','created_tool':installed['installed'],
                 'manifest_sha256':installed['sha256'],'workflow_status':job['status'],'children':job['data']['children'],
                 'duplicate_request_did_not_resubmit':True,'local_job_count':3,'network_calls':0,'live_vendor_calls':0,
                 'real_money_spent':0,'artifacts':job['data']['artifacts']}
        (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
        report='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ATM · 本地 Maker 演示</title><style>body{font:16px/1.7 system-ui;background:#f3f6f8;color:#173245;margin:0}main{max-width:1050px;margin:auto;padding:50px 24px}h1{font-size:44px;line-height:1.2}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px}article{background:#fff;padding:24px;border:1px solid #dce5ec;border-radius:14px}img{width:100%;height:200px;object-fit:contain;image-rendering:auto}aside{background:#e0f3ea;padding:22px;border-radius:10px;margin:22px 0}pre{white-space:pre-wrap;word-break:break-word;background:#142a35;color:#dcece9;padding:22px;border-radius:12px}.small{color:#637383}</style><main><p class="small">AGENT TOOL MAKER · v0.2 · ACTUAL LOCAL EXECUTION</p><h1>制作一个工具，再用它交付资产。</h1><p>同一个测试图片经过真实 ImageMagick 的缩图和 WebP 转换。并非商业模型生图，也没有外部付费调用。</p><aside><b>已执行：</b>工作流定义校验 → 安装 → 两个子任务 → 文件输出 → 重复 request-key 检查。再次调用仍只有一个父任务与两个子任务。</aside><section>__IMAGES__</section><h2>可检查的结果</h2><pre>__RECEIPT__</pre></main></html>'''
        concise={k:receipt[k] for k in ['mode','created_tool','manifest_sha256','workflow_status','duplicate_request_did_not_resubmit','local_job_count','network_calls','real_money_spent']}
        (out/'index.html').write_text(report.replace('__IMAGES__',''.join(imgs)).replace('__RECEIPT__',html.escape(json.dumps(concise,ensure_ascii=False,indent=2))))
        print(json.dumps({'index':str(out/'index.html'),'receipt':str(out/'receipt.json'),'status':'completed'},indent=2))
    finally:router.close()
if __name__=='__main__':main()

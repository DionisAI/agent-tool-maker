"""Generate a coverage map from the original 66-provider scope and installed actions."""
from pathlib import Path
import json,html,collections
from agent_tool_maker.catalog import Catalog
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'src/agent_tool_maker/data';DOCS=ROOT/'docs'
research=json.loads((DATA/'research.json').read_text());tools=list(Catalog().tools.values())
local_real={'ffmpeg.probe','ffmpeg.audio_to_mp3','ffmpeg.trim','ffmpeg.thumbnail','imagemagick.resize','imagemagick.webp','pandoc.to_markdown','pandoc.to_docx'}
remaining={
 'exa':'真实搜索配额与结果来源验收；高级搜索、分页和资料更新策略。',
 'firecrawl':'真实网站抓取、登录/反自动化边界、分页和作业恢复；保留资料来源。',
 'opencli':'更多站点动作按安装版本逐项生成适配器；真实登录、站点返回和发布操作验收。',
 'gws':'细粒度 OAuth 引导与续期、文档编辑和邮件发送；当前只有三个有限读取动作。',
 'apify':'Actor 级输出和费用约束、运行轮询到结果的复用工作流；当前分别提供提交、状态与数据页。',
 'dataforseo':'地域/语言与付费账户验收；扩展其他关键词接口与异步任务。',
 'google_trends':'官方 API alpha 准入与账号验收；本版只产出浏览器任务单。',
 'youtube_data':'OAuth 登录/刷新和上传流程；分页、权限与配额测试。',
 'notion':'托管 MCP OAuth、工作区真实读写；版本特定文档结构验收。',
 'linear':'托管 MCP OAuth、真实团队/权限回读和完整分页。',
 'tally':'公共 webhook 接收器、签名校验、去重与响应持久化；当前只交接配置工作。',
 'typeform':'真实账户创建/回读、webhook 收件与表单展示验收。',
 'pandoc':'跨平台与复杂版式验收。DOCX 动作采用固定无过滤器命令并要求 execute_code，不宣称 Pandoc 沙箱隔离。',
 'upwork':'当前 OpenCLI 仅搜索/读取；官方 API 准入、报价/授标/付款均未自动实现。',
 'freelancer':'真实 API 权限及分页；选人、授标、里程碑与付款的分别审批。',
 'fiverr':'未依赖未经核实的通用 API；目前只生成并跟踪人工任务与文件交付。',
 'figma':'托管 MCP 认证与版本协商、真实文件写入和可编辑结构验收。',
 'fal':'模型级 schema/价格同步、真实付费请求、下载与费用对账。',
 'elevenlabs':'真实音色权限、音频质量、用量与账单验收。',
 'higgsfield':'真实 API/网页两个计费路径独立验收；不自动跨账号或跨余额回退。',
 'tripo':'真实模型任务、材质/拓扑与网页端 GLB 性能验收。',
 'xyq':'在安装官方 CLI 并登录的设备上验证真实生图/生视频；不搬运原始网页登录凭证。',
 'comfyui':'已安装模型/节点的真实队列验收；模型资源和节点代码并不由 ATM 提供或沙箱化。',
 'pexels':'真实 API 查询、分页与素材许可/来源留存；本版不自动下载所有检索结果。',
 'ffmpeg':'增补字幕、拼接、混音等经过独立测试的动作；音视频内容质量另行判断。',
 'imagemagick':'更多固定编辑操作、资源配额、跨平台与异常图片测试。',
 'remotion':'安装对应版本与运行真实项目；模板、字体和许可由项目维护，不自动安装运行陌生代码。',
 'photopea':'浏览器内脚本桥接与 PSD 图层验收；本版交接，不自动执行用户脚本。',
 'whisper_cpp':'模型安装与真实语音转写、字幕时间轴/语言质量验收。',
 'blender':'安装 Blender 后验证两个打包脚本；模型优化、动画、材质及 GPU 渲染矩阵。',
 'gltf_transform':'实际 CLI 与模型检查/优化结果；不把 GLB 体积变小当成视觉无损证明。',
 'marvelous_designer':'需要有许可且已安装的桌面软件和匹配版本 Python API；原生脚本自动执行、工程输出、试穿/打样未实现。',
 'clo':'需要已许可桌面环境；自动导出工程、BOM/纸样及实物打样验收。',
 'freecad':'安装并验证 FreeCAD Python/控制台，参数化脚本、FCStd 与制造文件导出；本版桌面交接。',
 'kicad':'安装匹配 KiCad 后用真实板卡进行 DRC/Gerber 验收；实板安全与电路效果另行评审。',
 'github_cli':'真实 gh 登录与指定仓库权限、CI 回查；暂不提供自动 merge 或任意 shell。',
 'docker':'真实 Docker 守护进程与受控构建；不把 Docker socket 当作安全沙箱。',
 'playwright':'真实应用端到端测试与账号授权；MCP 仅协议桥，不假设自带浏览器登录。',
 'chrome_devtools':'连接已批准的调试浏览器，发现真实工具并加入白名单后验收；未内置浏览器实例管理。',
 'cloudflare_wrangler':'真实账号预览/生产部署、费用、HTTP 与业务回读；数据存储需独立回滚方案。',
 'cloudflared':'当前只列出现有命名 Tunnel；长驻进程监督、启动/停止/健康检查和共享 URL 生命周期尚未实现。',
 'cloudflare_dns':'真实受限域名 token 的记录创建/传播回查；未实现域名购买或全账户 DNS 任意修改。',
 'vercel':'账号与项目实测、部署 URL 验收、日志/回滚；生产和预览权限分开。',
 'supabase':'生产迁移恢复演练、真实 Function 回查；读取动作不导出服务密钥。',
 'expo_eas':'当前提交构建与查看构建，不包含应用商店提交/签名自动管理；提交不等于构建或上架完成。',
 'godot':'真实引擎、导出模板和可运行游戏验收。',
 'itch_butler':'实际上传渠道和可见性验证；上传命令完成不等于发布内容获人工认可。',
 'buffer':'真实连接频道、排期与已发布状态回读；CLI schema 漂移和失败后的对账。',
 'postiz':'当前读取集成和帖子；媒体上传、平台特有发布参数、排期写操作仍在计划。',
 'tiktok_posting':'需要合规应用授权/审核及公开可见性条件；本版只交接，不自动上传发布。',
 'wordpress':'真实站点草稿/读取；主题插件与数据库高风险维护未开放。',
 'ghost':'真实站点草稿回读、图片上传与公开发布的独立授权。',
 'google_ads':'开发者 token/OAuth 准入、报表与广告草稿；本版不运行广告或变更预算。',
 'stripe':'仅测试 Key 的 Checkout 创建；webhook 验签和交付、真实收款/退款全部需额外实现和验收。',
 'shopify_cli':'本版列出主题；主题构建/上传与应用发布需要真实店铺授权验收。',
 'shopify_admin':'本版产品读取与 DRAFT 创建；库存、公开上架、订单履约与退款分开实现。',
 'printful':'仅目录和未确认订单草稿；禁止自动确认生产/付款，实物履约单独验收。',
 'resend':'已验证发信域、明确收件人及真实邮件到达；退信、退订/收件事件未实现。',
 'hubspot':'当前只读取联系人；真实 CRM 写入、分页与团队工作流验收。',
 'slack':'真实工作区/频道最小权限与消息回读；不自动收集任意历史。',
 'telegram':'真实 Bot/chat 授权及消息回读；入站 webhook 和回调审批身份尚未实现。',
 'posthog':'实际埋点覆盖与查询验收、托管 MCP OAuth；查询成功不代表数据完整或分析正确。',
 'sentry':'真实项目错误、MCP 工具兼容、修复后复测；不会自动关闭 Issue 或宣称错误消失。',
 'search_console':'当前只列站点；搜索表现查询、分页和数据窗口检查尚未实现。',
 'youtube_analytics':'真实频道 OAuth 与报告权限、覆盖窗口及分页；不提供竞品内部数据。',
 'n8n':'已有工作流读取/激活；签名入站接收和长流程调度依赖实际 n8n 部署，不是 ATM 的后台承诺。',
}
records=[]
for r in research['records']:
 ts=[t for t in tools if t['provider']==r['id']]
 native=[t['id'] for t in ts if t['implementation']=='native'];bridge=[t['id'] for t in ts if t['implementation']=='bridge'];hand=[t['id'] for t in ts if t['adapter'] in {'browser','desktop','human'}]
 status='native_partial' if native else 'mcp_bridge' if bridge else 'handoff_only' if hand else 'planned'
 records.append({'id':r['id'],'name':r['name'],'stage':r['stage'],'status':status,'priority':r['priority_suggestion'],
  'action_ids':[t['id'] for t in ts],'native_actions':native,'mcp_bridge_actions':bridge,'handoff_actions':hand,
  'implemented_scope':[t['title'] for t in ts],'remaining_work':remaining[r['id']],
  'next_acceptance_gate':'安装和授权真实依赖后，以明确的小额或只读任务验收结果与权限；保存版本及证据。',
  'native_vendor_live_tested':False,'local_real_test_actions':[t['id'] for t in ts if t['id'] in local_real],
  'sources':r['source_urls']})
future=[
 {'id':'oauth','phase':'0.3 · 实际账号验收','name':'OAuth 登录和刷新','gate':'不复制明文令牌到 Agent 对话；撤销、失效和刷新失败均可复现。'},
 {'id':'live-matrix','phase':'0.3 · 实际账号验收','name':'跨平台 CLI / SaaS 实测矩阵','gate':'先 Cloudflare、OpenCLI、Buffer、Figma；记录 OS、版本、权限和消费，不以模拟代替生产。'},
 {'id':'webhook','phase':'0.3 · 事件与长任务','name':'Webhook 收件、签名校验、幂等与重放','gate':'Tally/Stripe/Resend 的重复或伪造事件不能引发重复发布/交付。'},
 {'id':'supervisor','phase':'0.3 · 事件与长任务','name':'长驻进程与挂起工作流管理','gate':'Tunnel/MCP 进程启动、停止、恢复和崩溃回收可观测。'},
 {'id':'desktop','phase':'0.4 · 垂直工具包','name':'Marvelous Designer / CLO / FreeCAD','gate':'许可软件 + 版本匹配脚本 + 可编辑工程和导出文件真实验收；实物另外确认。'},
 {'id':'social','phase':'0.4 · 垂直工具包','name':'社交发布与外包采购','gate':'账号/素材/时间或合同/金额有独立批准；超时先对账，不盲目重发/付款。'},
 {'id':'isolation','phase':'后续 · 强权限边界','name':'受限执行侧车与可信批准界面','gate':'不能由同一不可信 Agent 自己给自己升权；明确操作系统威胁模型。'},
 {'id':'wallet','phase':'后续 · 可选托管平台','name':'统一余额、Crypto、报价和预算预留','gate':'合法供给、并发预留、最大成本、退款和对账先于商业开放；BYOK 永久可用。'},
]
labels={'native_partial':'已实现有限动作','mcp_bridge':'MCP 协议桥接','handoff_only':'交接入口，待外部执行','planned':'未实现'}
summary=dict(collections.Counter(r['status'] for r in records))
road={'project':'Agent Tool Maker','version':'0.2.0','date':'2026-09-29','scope_count':66,'action_count':len(tools),'scope_summary':summary,
 'status_definitions':labels,'evidence_boundary':'目录覆盖不是供应商全功能实现。CLI/API 协议测试与真实账号/桌面验收分开记录；所有云端生产账号 live_tested=false。',
 'records':records,'platform_roadmap':future}
(DATA/'roadmap.json').write_text(json.dumps(road,ensure_ascii=False,indent=2)+'\n')
(DOCS/'ROADMAP.json').write_text(json.dumps(road,ensure_ascii=False,indent=2)+'\n')
md=['# Agent Tool Maker · v0.2 路线图','',road['evidence_boundary'],'',f'原调研 **66** 项全部映射：{summary}。仓库包含 **{len(tools)} 个动作入口**；动作数不是平台数。','',
 '## 本版 / 下一阶段 / 后续','', '| 阶段 | 待做能力 | 验收门槛 |','|---|---|---|']
for f in future:md.append(f"| {f['phase']} | {f['name']} | {f['gate']} |")
md+=['','## 66 项逐项对应','']
for stage in dict.fromkeys(r['stage'] for r in records):
 md+=['### '+stage,'','| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |','|---|---|---|']
 for r in records:
  if r['stage']!=stage:continue
  md.append('| '+r['name']+' | '+labels[r['status']]+'<br>'+', '.join('`'+a+'`' for a in r['action_ids'])+' | '+r['remaining_work']+' |')
 md.append('')
md+=['## 路线图不是承诺','', '所有阶段以验收门槛而非日期排序。网页版、桌面和人工任务单不会自动操作网页/软件或雇人；提供真实文件后，只记录文件级验收和宿主声明。生产账号、平台审核、许可软件与应用商店审批不能由模拟测试替代。','',
 '验收证据见 `TEST_REPORT.md`、`../reports/pytest.json`；具体动作、参数、权限和官方来源见 `TOOL_CATALOG.md` 与 `atm describe`。']
(DOCS/'ROADMAP.md').write_text('\n'.join(md)+'\n')
# Full finite-action catalog with mechanically checkable rows and schemas/examples in package.
cat=['# ATM v0.2 · 可发现动作目录','',f'共 {len(tools)} 个入口。native = 执行适配器已实现；bridge = 通用 MCP 协议入口；handoff/browser = 任务交接，不能当作自动执行。',
 '','任何动作的账号、CLI、MCP 服务器或桌面应用仍需用户配置。`atm describe ID` 是输入 schema、例子和权限的可执行来源。','',
 '| ID | 适配器 / 实现 | 声明权限 | 可能计费 | 本版动作 | 来源 |','|---|---|---|---|---|']
for t in tools:
 links=' / '.join(f'[文档{i+1}]({u})' for i,u in enumerate(t.get('sources',[])))
 cat.append(f"| `{t['id']}` | {t['adapter']} / {t['implementation']} | {', '.join(t.get('permissions',[])) or '按已配置权限读取/本地操作'} | {'是/未知价格' if t.get('paid') else '无额外计费标记，不等于服务免费'} | {t['title']} | {links} |")
(DOCS/'TOOL_CATALOG.md').write_text('\n'.join(cat)+'\n')
# Finite input examples; no auth material included.
e=ROOT/'examples/actions';e.mkdir(exist_ok=True)
for t in tools:
 if 'example' in t:(e/(t['id']+'.json')).write_text(json.dumps(t['example'],ensure_ascii=False,indent=2)+'\n')
# Self-contained visual roadmap, no external libraries or network.
esc=html.escape
cards=''.join(f'<article class="phase"><span>{esc(f["phase"])}</span><h3>{esc(f["name"])}</h3><p>{esc(f["gate"])}</p></article>' for f in future)
rows=''.join('<tr data-status="'+r['status']+'"><td><small>'+esc(r['stage'])+'</small><strong>'+esc(r['name'])+'</strong></td><td><span class="badge '+r['status']+'">'+esc(labels[r['status']])+'</span><p class="ids">'+esc(', '.join(r['action_ids']))+'</p></td><td>'+esc(r['remaining_work'])+'</td></tr>' for r in records)
html_doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ATM 0.2 · 能力路线图</title>
<style>:root{color-scheme:light;--ink:#182635;--muted:#617183;--line:#dbe3ea;--accent:#156b62}*{box-sizing:border-box}body{margin:0;background:#f5f7fa;color:var(--ink);font:16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}header{background:#152a35;color:#fff;padding:60px max(5vw,24px) 48px}main{max-width:1400px;padding:28px;margin:auto}h1{font-size:clamp(36px,5vw,65px);line-height:1.1;margin:12px 0}header p{max-width:900px;color:#cbdce5}h2{margin:38px 0 18px}.eyebrow{letter-spacing:.15em;font-size:13px;text-transform:uppercase}.metrics{display:flex;gap:18px;flex-wrap:wrap;margin-top:30px}.metric{min-width:135px;border-left:2px solid #65c7b2;padding:0 20px}.metric b{display:block;font-size:32px}.metric span{font-size:13px;color:#d4e1e8}.notice{background:#fff3da;border-left:4px solid #cf9830;padding:18px 22px;border-radius:8px}.timeline{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.phase{background:white;border:1px solid var(--line);border-top:4px solid var(--accent);border-radius:12px;padding:23px}.phase>span{color:var(--accent);font-size:13px;font-weight:700}.phase h3{margin:8px 0}.phase p{color:var(--muted);font-size:14px}.controls{display:flex;gap:12px;flex-wrap:wrap;position:sticky;top:0;background:#f5f7fa;padding:15px 0;z-index:3}input,select{padding:12px 16px;border:1px solid var(--line);border-radius:8px;font:inherit;background:white}input{flex:1;min-width:220px}.tablewrap{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:12px}table{width:100%;border-collapse:collapse;min-width:830px}th,td{text-align:left;vertical-align:top;padding:18px;border-bottom:1px solid var(--line)}th{background:#eaf0f4;font-size:14px}td:first-child{width:21%}td:nth-child(2){width:38%}small{display:block;color:var(--muted);font-size:12px}strong{display:block}.ids{font:12px/1.8 ui-monospace,monospace;word-break:break-word;color:#536477;margin-bottom:0}.badge{display:inline-block;border-radius:20px;background:#ebeff3;padding:4px 10px;font-size:12px;font-weight:600}.native_partial{background:#dff3ec;color:#155d47}.mcp_bridge{background:#e3eafa;color:#354f85}.handoff_only{background:#fff0d5;color:#825617}.foot{color:var(--muted);margin:20px 0 40px;font-size:14px}a{color:var(--accent)}@media print{header{padding:30px}.controls{display:none}.phase{break-inside:avoid}table{font-size:11px}td,th{padding:8px}}</style>
<header><div class="eyebrow">Local-first · Open source · MIT · 2026-09-29</div><h1>Agent Tool Maker</h1><p>Agent 不只使用工具，也能制作工具。0.2 版把具体动作、通用协议桥接、外部交接和下一阶段验收分开记录。</p><div class="metrics"><div class="metric"><b>157</b><span>可发现动作入口</span></div><div class="metric"><b>66</b><span>原调研项逐项映射</span></div><div class="metric"><b>120</b><span>原生执行动作</span></div><div class="metric"><b>14 + 23</b><span>MCP 入口 + 外部交接</span></div></div></header><main>
<div class="notice"><b>状态不是效果保证。</b>原生执行、模拟协议测试和真实供应商验收不是同一回事。没有用私人账号发布、消费或部署；桌面/浏览器/人工交接不会因写出任务单就标记完成。</div><h2>从当前版本走向完整工作流</h2><section class="timeline">__CARDS__</section><h2>66 项能力与验收缺口</h2><div class="controls"><input id="q" placeholder="搜索工具、能力或待办，例如 Cloudflare / 服装 / OAuth"><select id="filter"><option value="">全部状态</option><option value="native_partial">已实现有限动作</option><option value="mcp_bridge">MCP 协议桥接</option><option value="handoff_only">只有交接入口</option></select><span id="count">66 / 66</span></div><div class="tablewrap"><table><thead><tr><th>工具 / 业务阶段</th><th>本版状态与具体动作</th><th>尚未实现或待实测</th></tr></thead><tbody>__ROWS__</tbody></table></div><p class="foot">阶段排序按依赖与验收门槛，不是上线日期承诺。详细测试证据见下载包中的 docs/TEST_REPORT.md 与 reports/pytest.json；完整 schema、参数和权限可通过 atm describe 查询。</p></main><script>const q=document.querySelector('#q'),f=document.querySelector('#filter'),rs=[...document.querySelectorAll('tbody tr')];function apply(){let n=0;for(const r of rs){const ok=(!f.value||r.dataset.status===f.value)&&r.textContent.toLowerCase().includes(q.value.trim().toLowerCase());r.hidden=!ok;if(ok)n++;}document.querySelector('#count').textContent=n+' / '+rs.length;}q.addEventListener('input',apply);f.addEventListener('change',apply);</script></html>'''.replace('__CARDS__',cards).replace('__ROWS__',rows)
(DOCS/'ROADMAP.html').write_text(html_doc)
print(json.dumps({'actions':len(tools),'scope':len(records),'statuses':summary},ensure_ascii=False))

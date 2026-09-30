"""Create reports and source archive only after successful local validation and wheel smoke."""
from pathlib import Path
import json,collections,xml.etree.ElementTree as ET,hashlib,zipfile,shutil,datetime
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
result=json.loads((R/'pytest.json').read_text());run=json.loads((R/'validation-run.json').read_text());smoke=json.loads((R/'release-smoke.json').read_text())
assert (R/'test-exit-code.txt').read_text().strip()=='0'
assert run['exit_code']==0 and result['summary'].get('failed',0)==0 and smoke['result']=='passed'
counts=collections.Counter(t['nodeid'].split('::')[0] for t in result['tests'])
coverage=ET.parse(R/'coverage.xml').getroot();rate=100*float(coverage.attrib['line-rate'])
env=json.loads((R/'tested-environment.json').read_text())
s=result['summary'];passed=s['passed'];skipped=s.get('skipped',0);total=s['total']
report=f'''# Agent Tool Maker v0.2.0 · 测试报告

日期：2026-09-29。**{passed} 项通过，0 失败，{skipped} 跳过；总计 {total} 项。** 本次 pytest 耗时 {result['duration']:.2f} 秒。行覆盖率 **{rate:.2f}%**（{coverage.attrib['lines-covered']} / {coverage.attrib['lines-valid']}）。

实际环境：Python **{env['python']}**，Linux。这个结论针对当前交付代码的本地测试，不是所有商业服务的生产成功率，也不声称绝对无 bug。

## 按测试文件统计

| 文件 | 用例数 |
|---|---:|
'''
for k,n in sorted(counts.items()):report+=f'| `{k}` | {n} |\n'
report+='''
## 实际运行的内容

**真实本地程序**：FFmpeg / FFprobe 检查和转码；新增视频裁剪及缩略图，回读实际视频时长/图片尺寸；ImageMagick 缩图和 WebP；Pandoc HTML→Markdown 和 Markdown→DOCX。另跑了真实“缩图→WebP”的组合工具，重复请求仍只有一个父任务与两个子任务。

**真实子进程协议测试**：所有 66 个新增 CLI 动作调用一个测试程序，实际经过 argv 构造、工作目录、最小环境、产物导入、超时和入口哈希检查。它们不是 66 个已安装供应商 CLI 的真实验收。旧小云雀也使用协议替身，不是付费账号生成。

**HTTP 合同测试**：保留旧六家原生媒体/搜索接口测试，并逐项测试 44 个新增 REST 动作。使用 `httpx.MockTransport`；路由、Vault、schema、状态机、任务去重、结果保存均是真代码，只有远端响应模拟。覆盖错误状态、200 内业务错误、嵌套任务错误、Stripe live Key 拒绝、受限目的地址和凭证不外传。模板自身和模拟协议不能证明供应商当前接受每一个字段。

**Maker 与组合**：定义校验、摘要不符拒绝、显式安装、隐含权限、非法 schema/外部引用拒绝、前向引用和嵌套拒绝、暂停/恢复、定义变更冲突与子任务去重。

**MCP**：实际启动本地协议服务器替身，测试 initialize、发现、工具 schema、整批白名单预校验、共享会话状态和进程回收。HTTP JSON/SSE 使用模拟 transport。没有声称 Figma/Notion/Linear/Playwright/DevTools/PostHog/Sentry 七家生产 MCP 全部实测。

**Chromium**：真实浏览器渲染合成下载页、原有离线媒体演示及新版计划图，验证真实下载/文件交回、图像显示、66 条路线图筛选与无页面脚本错误。生产网站登录、按钮和付费行为未测试。

**兼容与存储**：旧 vault metadata 省略 service 时仍能解密旧兼容格式；保留原 AES-GCM/scrypt、篡改/错误口令、请求认领并发等回归。原生 OS keyring 用受控替身，不是 macOS/Windows/Linux 凭证库的系统集成证明。

## 构建与安装

构建 wheel：`agent_tool_maker_local-0.2.0-py3-none-any.whl`。在源目录之外的新虚拟环境安装，确认导入位置在该环境的 site-packages，而非源码。实际运行 `atm` / `atr` 版本、初始化、stats、roadmap、Skill 导出、Maker 起草/验证/安装/describe 与离线媒体 demo。

安装测试**复用了当前环境已经安装的第三方依赖**；初次仅设置 system-site-packages 时遗漏父虚拟环境依赖，已明确加入依赖目录后重新验收。它不是从空白联网机器重新解析依赖的证明。包没有发到 PyPI 或 GitHub，CI 配置未在线运行。

## 这次发现并处理的问题

旧 `blender.cli` 是占位而非执行器。新版移除它并提供明确 inspect/render，修正回归断言，防止静默升级旧工具权限。

实际 Pandoc 3.1.11.1 在 sandbox 下读取 DOCX 默认数据失败。没有将失败调用偷偷重试为不受限模式：DOCX 被明确建模为要求 `execute_code` 的固定、无过滤器转换；Markdown 转换仍使用 sandbox。这个调整及其边界写入 SECURITY。

新增自建 API 的目的地址检查，并对私网 IP 字面量直接拒绝；阻止被测试 DNS 替身误解为公共地址后继续发送凭证。仍不声称解决 DNS rebinding 或恶意同用户进程。

## 不能从这些测试推导出的结论

没有商业供应商生产调用，没有私有账号发布/部署，没有真实花费；没有真实衣服桌面软件、外包采购或物理样品验收。没有 OAuth 登录/自动刷新、统一支付、硬预算、远程电脑托管、长驻调度和强同用户隔离。

`completed` 只等于声明的动作验收级别：HTTP JSON、CLI 退出、有限格式/文件哈希或宿主文件声明。需要另行确认排期已经发布、构建已经完成、网站业务可用、付款已经交付和衣服适合生产。

## 可复现证据

`reports/pytest.json`、`junit.xml`、`coverage.xml`、`test-output.txt`、`validation-run.json`、`release-smoke.json`、`tested-environment.json`、`local-maker-demo.json`。`reports/development/initial-full-run.txt` 保留修复前的失败记录，不是最终验收结果。

```bash
python -m pip install -e '.[secure,test,browser-test]'
# 真实本地程序测试需要 ffmpeg/ffprobe、ImageMagick 7、Pandoc、Chromium。
pytest -q
# 完整 JSON/覆盖率报告另需 pytest-json-report：
python scripts/run_validation.py
```

缺依赖时集成测试会显式 skip；不要拿有 skip 的另一台机器结果复述为本次全部通过。覆盖率不合并所有 CLI 子进程的内部 Python 行；它不是按供应商功能覆盖率计算。
'''
(ROOT/'docs/TEST_REPORT.md').write_text(report)
# Include the actual, self-contained local demo, but do not ship state databases or transient credentials.
local=Path('/mnt/data/atm-local-demo')
shutil.copyfile(local/'index.html',ROOT/'examples/local-maker-demo.html')
shutil.copyfile(local/'receipt.json',R/'local-maker-demo.json')
shutil.copyfile(local/'index.html',Path('/mnt/data/agent-tool-maker-demo-v0.2.0.html'))
summary={'project':'Agent Tool Maker','version':'0.2.0','actions':157,'native_actions':120,'mcp_entries':14,'handoffs':23,
         'research_items':66,'passed':passed,'failed':0,'skipped':skipped,'total':total,'coverage_percent':round(rate,2),
         'test_seconds':result['duration'],'wheel_smoke':'passed','production_vendor_calls':0,'paid_spend':0}
(R/'release-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
excluded={'.pytest_cache','__pycache__','.git','.venv','build','htmlcov'}
def collect():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and not any(q in excluded or q.endswith('.egg-info') for q in p.relative_to(ROOT).parts) and p.name not in {'.coverage','MANIFEST.sha256.json'} and not p.name.endswith(('.pyc','.sqlite3','.sqlite3-wal','.sqlite3-shm')))
files=collect();manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(ROOT/'MANIFEST.sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=Path('/mnt/data/agent-tool-maker-v0.2.0.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files+[ROOT/'MANIFEST.sha256.json']:z.write(p,'agent-tool-maker/'+p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,sha in manifest.items():assert hashlib.sha256(z.read('agent-tool-maker/'+name)).hexdigest()==sha
wheel=next((ROOT/'dist').glob('*.whl'))
Path('/mnt/data/agent-tool-maker-v0.2.0.sha256').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in [archive,wheel])+'\n')
print(json.dumps({**summary,'archive':str(archive),'archive_bytes':archive.stat().st_size,'packaged_files':len(files)+1},ensure_ascii=False,indent=2))

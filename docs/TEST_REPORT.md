# Agent Tool Maker v0.2.0 · 测试报告

日期：2026-09-29。**303 项通过，0 失败，0 跳过；总计 303 项。** 本次 pytest 耗时 362.94 秒。行覆盖率 **87.68%**（1501 / 1712）。

实际环境：Python **3.13.5**，Linux。这个结论针对当前交付代码的本地测试，不是所有商业服务的生产成功率，也不声称绝对无 bug。

## 按测试文件统计

| 文件 | 用例数 |
|---|---:|
| `tests/test_artifacts_browser.py` | 23 |
| `tests/test_browser_integration.py` | 2 |
| `tests/test_cli_process.py` | 7 |
| `tests/test_maker_workflows.py` | 17 |
| `tests/test_mcp_bridge.py` | 10 |
| `tests/test_network.py` | 21 |
| `tests/test_release_v02.py` | 9 |
| `tests/test_router.py` | 34 |
| `tests/test_v02_actions.py` | 165 |
| `tests/test_vault.py` | 15 |

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

2026-10-20：所有者可在管理台（设置 › 高级 › 网络）打开 Fake-IP 选项，接受域名解析到普通 IPv4 `198.18.0.0/15`
的应答；默认关闭，关闭时行为不变。打开时，同组的其他应答必须是普通公网单播地址：字面量、映射/兼容/转换 IPv6、
内含非公网 IPv4 的 NAT64、组播、保留地址和其他非公网地址都让整组应答被拒绝；每个下载跳转都重新检查并重新读取设置。
打开后真实目的地址由本机代理负责。测试只用替身解析器和 MockTransport（`tests/test_fake_ip_tunnel.py`、
`tests/test_fake_ip_browser.py`、`tests/fake_ip.test.mjs`），没有连接任何真实 OAuth 主机。

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

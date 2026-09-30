# ATM v0.4.0 · CLI + 本地网页管理台

## 默认客户端

本版默认支持 **Claude Code** 与 **Codex 的本地客户端**。它们通过用户级 Skill 调用
同一个 ATM CLI、同一状态目录、同一加密凭证库；不是在这里再次代理 Claude/OpenAI
模型推理，也不是安装客户端或登录服务的替代品。网页聊天/云沙箱不自动连接本机。

```bash
atm setup                         # 默认预览 Claude Code + Codex
atm setup --apply                 # 应用已审阅的非秘密配置
atm setup --agent claude --apply   # 只选择 Claude Code
atm setup --no-agents --cli ffprobe --apply  # 仅绑定已安装的工具
atm agents list
atm agents unregister codex        # 预览，不删除
atm agents unregister codex --apply # 移走本工具登记且未被修改的 Skill，保留备份
```

用户级路径：Claude Code 使用 `~/.claude/skills/agent-tool-maker/SKILL.md`（尊重
`CLAUDE_CONFIG_DIR`），Codex 使用 `~/.agents/skills/agent-tool-maker/SKILL.md`。
两者注册绝对 ATM 入口与固定状态目录。系统客户端策略可能禁用自定义 Skills；
注册成功不等于真实宿主已加载，仍须开新会话验收。

## 启动网页

```bash
atm ui                   # 随机本机端口，自动打开浏览器
atm ui --port 8765        # 选择固定本机端口
atm ui --no-browser      # 不自动打开；供人类在自己的终端手动连接
```

只绑定 `127.0.0.1`，没有 `--host 0.0.0.0`。Ctrl-C 停止服务。前端随 wheel 打包，无
Node 构建步骤、CDN、追踪脚本或云账号。CLI 不依赖网页服务，网页关闭后配置仍保留。

自动打开时，管理会话码通过 URL fragment 传给页面并立即从地址栏移除；不发到 HTTP
URL、不存在 localStorage/sessionStorage。无浏览器模式输出私有 token 文件的路径：
人类在自己的终端读取后，填入登录页。不要把该文件内容或带 fragment 的入口发到
Agent 对话/issue/日志。页面刷新或“锁定界面”清除页面中的会话码，重新连接即可。
服务重启后更换会话码；8 小时到期后重启。正常退出删除文件；强杀可能留下已失效文件。

## 已实现的管理界面

| 页面 | 功能 | 与 CLI 的关系 |
|---|---|---|
| 总览 | 真实目录/启用数、已保存连接、最近任务计数 | 来自同一 SQLite，不用展示假统计 |
| Agent 客户端 | 查看 Claude/Codex、预览并应用注册、移除登记入口 | 共用 onboarding；只动 ATM 自有入口 |
| 工具目录 | 搜索、类型/启用筛选、查看 schema、启用或停用具体动作 | `atm tools list/enable/disable` 使用同一开关 |
| CLI 入口 | 检测程序并预览首次绑定；变化显示为需审查 | 改动后重新绑定仍用 `atm cli bind` 审核 |
| 连接与凭证 | 初始化空库，新增/显式替换/移除 Key，可选有效期 | 原有 Vault 格式；已有 Key 默认不覆盖 |
| 账户检查 | 预览并明确同意已有四类固定账户探针 | 共用 `atm verify`；不会退回生成测试 |
| 任务记录 | 最近 50 条真实摘要、状态、产物数、已知/未知费用 | 不向 Web 返回输入、原始响应或签名 URL |

**停用是全局 ATM 执行开关，不是每个 Agent 独立的访问控制。**它阻止经 ATM 发起
的新动作及工作流后续新步骤；不撤销上游已提交任务，也不阻止用户绕过 ATM 直接用工具。
所有旧工具的权限/付费确认规则继续适用。网页没有任意 Shell、工具运行、自动部署、
任务重提或 `jobs --refresh` 接口。

```bash
atm tools list fal
atm tools disable fal.generate          # 预览
atm tools disable fal.generate --apply   # 网页与两个客户端立即读到同一状态
atm tools enable fal.generate --apply
atm cli list
atm connections list
```

origin 与 MCP 白名单编辑、Maker 设计/安装、复杂任务执行仍使用现有 CLI。它们不是
“已经全部可在网页管理”的功能；后续增加表单时同样先预览、再明确批准。

## 凭证输入与解锁

浏览器只允许把人类输入的密钥写入加密库，没有回读密钥的接口。保存成功、失败或关闭
对话框都会清空输入控件；服务只在当前请求中使用口令/解锁结果，不缓存为全局会话。
口令模式需在保存/移除/检查连接时提供库口令；不需要重复提供所有供应商 Key。
原生 keyring 可能弹系统授权，未配置安全后端不会退回明文。

这是 **loopback HTTP**，不是 TLS 云服务。不应通过 Tunnel/反向代理/容器端口映射对外
暴露，不适用于共享远程控制、团队多租户或抵抗本机同权限恶意进程。Python/浏览器内存
不提供可验证的安全擦除保证；系统内存、浏览器扩展和进程调试属于剩余边界。

## HTTP 防护与接口约束

每个 API 读写要求每进程随机 bearer；Host 必须与实际 `127.0.0.1:port` 完全一致。
出现 Origin 时必须同源，写请求必须提供精确 Origin；拒绝跨站 Fetch Metadata、重复
安全头、查询字符串凭证、表单请求与超过 64 KiB 的 JSON。不启用 CORS。
静态 shell 不包含本地路径、账号或 token；CSP 禁止外部脚本、inline script、frame。
动态文案使用 textContent，不使用供应商 HTML。响应 no-store，访问日志不打印内容。

Web 管理是一个有凭证的本机入口，**不是独立的人类批准可信边界**：拥有同一系统用户
权限的 Agent 可能访问进程/文件。保持宿主的权限与批准策略；不要以网页按钮取代它。

## 验收

默认 tests/ 包含真实 loopback HTTP 测试，以及 Chromium DOM + 测试传输桥接的 UI
组件检查。桥接测试不证明原生浏览器网络策略或 CSP；它与 HTTP 安全测试是两个层级。

```bash
python -m pytest -q
python -m pytest -q acceptance/test_console_navigation.py
```

第二条是独立的真实浏览器 localhost 导航验收，在 CI 中强制执行。受管理的浏览器可能
明确禁止 localhost；不要修改策略来使测试通过，应报告环境限制并在允许环境验收。

真实客户端最后验收：两个全新会话分别发现同一 ATM Skill，从不同项目运行已绑定的
FFprobe；不重建库、不重新索取已存 Key。Keychain 锁屏/重启、真实账户权限、客户端
配置策略、OAuth 刷新并不因网页交互通过就自动得到验证。

官方客户端路径与本地服务安全参考（2026-09-30 查阅）：
- https://developers.openai.com/codex/skills
- https://code.claude.com/docs/en/skills
- https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-9h52-p55h-vw2f

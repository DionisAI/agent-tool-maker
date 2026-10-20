# v0.7 补充：与 CLI 共用解锁

总览新增“凭证使用会话”：解锁30分钟、固定倒计时、刷新状态、立即锁定。
网页完成一次验证后，获准的 CLI / Claude / Codex 新进程可复用。同一会话中的添加、轮换、删除连接不重复索要密码。
网页开出的会话由管理台服务托管，关闭管理台进程会结束会话；仅关标签页不等于进程停止。独立 `atm unlock` 前台服务不因关闭管理台而停止。
重复解锁不续期。已进入 session 模式而会话过期时，凭证表单先要求解锁，不应重复索要已有Key。

Owner管理权限与Agent注入权限分开。此页没有通用exec、原文Key导出、任意Shell或exec授权计划自动批准接口。账户verify和其他旧管理操作仍不是统一会话覆盖范围。

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

只在本机回环监听，页面地址是 `http://localhost:port`，没有 `--host 0.0.0.0`。浏览器解析 `localhost`
时先试 `[::1]`，所以管理台同时占住 `127.0.0.1:port` 与 `[::1]:port`（仅 IPv6，`IPV6_V6ONLY`），两处由同一
进程、同一会话码和状态应答，Host 仍须是 `localhost:port`；别的本机程序无法抢先占住 `[::1]` 拿到页面或启动码。
随机端口时若 `[::1]` 的同号端口已被占用，就换一个两边都空闲的端口；`--port` 指定的端口任一侧被占用时以
`port_in_use` 退出。本机没有 IPv6 回环时只监听 IPv4（浏览器也连不到 `[::1]`）。Ctrl-C 同时关闭两处监听。
Agent 打开的本地授权窗口（`atm start`）使用同样的双监听。
前端随 wheel 打包，无 Node 构建步骤、CDN、追踪脚本或云账号。CLI 不依赖网页服务，网页关闭后配置仍保留。

再次运行 `atm ui` 会先找同一 ATM home 里已运行的管理台：home 须属于本用户且组/其他用户不可写；只认本用户、
0600、单一硬链接、非符号链接的 `ui-session-<port>.token`。对每个候选端口先发随机挑战（`X-ATM-Challenge`，
不带会话码），对方须返回用会话码计算的 HMAC 证明；答不出的监听者永远收不到会话码。证明通过后才带会话码读取
`/api/console`，核对服务、版本（须与本次 `atm ui` 相同）、home 与剩余有效期（大于 0 且不超过 8 小时）。
整个探测共用约 2 秒时限，应答不超过几 KiB；慢速或超大应答都按“不是本管理台”处理。剩余至少 15 分钟时打开该
管理台（`--no-browser` 时不打开），输出同样字段加 `"reused": true`，不含会话码，不启动第二个服务；不足
15 分钟时新建一个，并在 note 中说明。新启动时为 `"reused": false`。端口无人监听时删除这个残留文件；其他程序
应答、已过期（401）、版本不同或属于另一个 home 时不复用也不删除，照常新建。`--port` 指定其他端口时照常新建。

自动打开时，地址里只有一次性启动码 `#launch=<code>`（随机 32 字节，60 秒内有效，只能用一次，不打印、不写日志），
不是会话码。页面立即把它从地址栏和这条历史记录中移除，再向同源的 `/api/console/redeem` POST（须精确的 Origin
与 Host，不带 bearer）换回会话码，所以地址栏、浏览器历史和保存的标签页地址里都没有会话码（sessionStorage
见下段）。复用已运行的管理台时，`atm ui` 在挑战证明通过后用会话码向它申请一个新的启动码。页面仍接受旧入口里
的 `#token=`（已打开或已收藏的链接），但 `atm ui` 不再生成它。

页面只把会话码存在当前标签页的 sessionStorage（`atm-console-token`，按精确 `localhost:port` 隔离），刷新后
保持连接；当前页面（`atm-console-section`）也保留，浏览器后退/前进在页面间切换。不用 localStorage（超出标签页
寿命）或 Cookie（各 localhost 端口共享）。同源脚本与浏览器扩展可读取它，CSP 只允许本服务脚本。新开的空白标签页、
重开浏览器需重新连接或再运行 `atm ui`；但“复制标签页”、重新打开刚关闭的标签页或浏览器恢复上次会话时，
sessionStorage 连同会话码一起恢复，直到收到 401、点“锁定界面”或会话到期。刷新时如已有会话码，先显示页面标题
占位，不闪出登录页。收到 401 或点“锁定界面”时清除会话码、页面数据、打开的对话框和主区域，登录页常驻一行原因：
会话已过期、管理台已重启/会话已失效，或启动链接已用过/已过期（都提示在终端再次运行 `atm ui`）；手动粘贴
会话码仍可用。浏览器禁用存储时退回仅页面内存。
无浏览器模式输出私有 token 文件的路径：人类在自己的终端读取后，填入登录页。不要把该文件内容或
带 fragment 的入口发到 Agent 对话/issue/日志。服务重启后更换会话码；8 小时到期后重启。
正常退出删除文件；强杀留下的失效文件在下次 `atm ui` 发现端口无人监听时删除。

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

每个 API 读写要求每进程随机 bearer；Host 必须与实际 `localhost:port` 完全一致。只有两个入口不带 bearer：
`atm ui` 的挑战只返回 HMAC 证明（不含 home、版本或有效期），启动码兑换须精确 Origin 与 Host 且一次有效。
会话到期后，带正确会话码的请求得到 401 `session_expired`；未知会话码仍是 401 `unauthorized`。
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


## v0.5 新页面

设备与同步：初始化独立身份、导出公钥卡片、按发送/接收列表配对、导入/导出密文、冲突版本选择和本地撤销。
Agent授权：预览/创建具有工具与工作目录范围的能力凭据、查看有效期、撤销。原始Key及能力token都不从查询接口回读。
Owner的解锁服务和目录watch由本机终端启动；不通过网页执行Shell或暴露远程服务。高级Linux跨UID授权走CLI。
完整说明见 MULTI_DEVICE.md。已有同步盘不是系统自动部署，界面上的配置存在也不是供应商账户验收。


## v0.6 — 扩展工坊

新增“扩展工坊”页，与 CLI 使用同一份声明式工具定义、独立凭证注册表和版本更新规则。
可创建不在内置目录里的凭证名称（不含 Key），并粘贴 JSON 工具定义，先验证输入结构、
目的地址、凭证引用、权限和新旧摘要，再明确批准安装或更新。不同版本并发变化会拒绝过时决定；内置动作不可覆盖。

工坊只显示浏览器会话的名称、origin、有效期，不显示或导出 Cookie。
实际网页登录仍由 Owner 在自己的终端运行 `atm web login TOOL`；模型起草、CLI 打包也走 CLI，
没有把网页变成任意 Shell、自动执行模型输出或直接访问未知网站的入口。

v0.6 工坊通过真实 Chromium DOM 与本地 HTTP 组件测试；当前受管浏览器不允许原生导航，
未修改该策略。新增网页配方的原生导航验收已作为单独 CI 文件提供，但本版未上传，
不能把 v0.4 的 CI 结果当作 v0.6 通过。更多例子见 [扩展指南](EXTENSIBILITY.md)。

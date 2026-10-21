# ATM OAuth 登录与自动续期

## 用户体验

告诉 Agent：**“打开 ATM，连接 Higgsfield 订阅并保持登录。”**
Agent 打开本机管理页；在「服务 → Higgsfield → ATM 登录 · Higgsfield MCP」中，
你勾选「保持登录」并打开官方登录窗口，自己完成登录/授权。密码和令牌不进入聊天。
授权请求仅包含 `openid email offline_access`，绑定 `https://mcp.higgsfield.ai/mcp`。

这是一条**新的 ATM OAuth 连接**，与官方 `higgsfield` CLI 的登录相互独立。
既有 `higgsfield.subscription.*` CLI 工具仍使用 CLI 自己的登录；它们不会自动改用此连接。
开发者 API 的 `KEY_ID:KEY_SECRET`、计费余额与此连接分开。

## 持久性与范围

- access/refresh token、客户端信息、短期 PKCE 状态使用现有 vault 主密钥 AES-256-GCM
  加密，放在独立 `oauth_connections` 表；不进入 Key 列表、Key 同步、`.env` 或项目默认授权。
- **系统 keyring 模式**：明确选择保持登录后，在 macOS 安装本用户 launchd 服务，
  每 60 秒检查，到期前 90 秒尝试一次真正的 refresh-token 换新。机器休眠时不运行；
  登录 macOS 后启动，错过到期的连接可在供应商仍接受 refresh token 时续期。
- **口令模式**：不保存口令、不配置永久解锁；在本地窗口或私有终端明确解锁后按需续期。
  本版本的无人值守后台续期仅支持原生 keyring。Linux 可使用 `atm oauth watch`，
  不自动安装系统服务。
- 项目的 **30 分钟 Key 授权不延长**。`atm lock` 仍结束项目 Key 的新调用；
  不等于注销供应商登录或停止已明确批准的 OAuth 后台续期。
- 「停止自动续期」关闭新刷新准入，不删除连接、供应商授权或服务文件；
  已在途的一次刷新可能完成。重新登录需要明确勾选替换既有 ATM OAuth 连接；登录仍有效（含正在续期、
  自动续期没有运行）时，这条连接方式上也有「重新登录」，用于换账号、重新授权或重装续期服务。
- 供应商撤销授权、不给 refresh token、要求验证码或登录、keyring 被锁定时，状态会说明原因。
  保存状态不构成永久有效保证。

## Agent/管理员接口

`atm oauth status higgsfield` 仅返回状态、有效期、续期开关和后台服务的最近安装状态。
`atm oauth login higgsfield --keep-login` 打开一轮官方 PKCE 登录，等待人类授权最多 5 分钟。
重复请求复用 pending，既有连接默认保留；明确更新用 `--replace`。
`atm oauth refresh higgsfield` 在内部续期，不输出令牌。
`atm oauth keep-login higgsfield --apply` / `--disable --apply` 管理后台续期开关。
`atm oauth watch --once` 是服务的有限单次检查；`watch` 是前台监督进程。
pending/refreshing CLI 返回 3，需要登录/未知结果返回 2，成功返回 0。

MCP HTTP 绑定可使用：

```json
{"transport":"http","url":"https://mcp.higgsfield.ai/mcp","oauth":"higgsfield","allow_tools":[]}
```

先发现工具，再批准确切工具名和实际调用权限/费用。空 allowlist 不允许业务调用。
令牌只在 HTTP 适配器内部作为 Bearer 发给确切资源；不导出给 CLI，不代替 API Key。
每次请求前检查有效期，401 不重放 `tools/call`；付费或有副作用任务沿用原有不确定结果合同。
严格 broker 的既有 MCP 限制不变；OAuth 管理不是项目 `atm use` 的新增权限。

## 故障与追溯

刷新前提交 SQLite 独占 claim，成功后原子保存新的 access token 和轮换的 refresh token。
并发请求不重复消费同一 refresh token。刷新响应省略新 refresh token 时保留旧值（RFC 6749）。
`invalid_grant` → `needs_login`；传输中断、未知服务端失败、成功响应形状异常或保存中断 →
`refresh_unknown`（活动 claim 过期后也归此状态），不盲重试旧 refresh token。
同一登录 authorization code 只换一次；state/issuer 不匹配、Host/path 不匹配、重复查询字段不换 token。
回调日志、provider body/error_description、授权 URL、令牌均不显示给 Agent。
事件仅记录 `oauth.connected/refreshed/needs_login/refresh_unknown`，不记录身份或秘密。
服务 stdout 为限定状态，日志 0600；不存在供应商账单/生成心跳。
`oauth_dns_policy` 表示本机将官方域名解析为 private/reserved 地址；请求在发出前停止。
错误码不变。原因只是代理 Fake-IP 应答（`198.18.0.0/15`，Shadowrocket、Clash、Surge
的 Fake-IP 模式会把每个域名都解析到这里）时，错误另带 `"hint": "fake_ip_tunnel"`，
连接状态保存 `last_error_hint`；管理台据此用中文说明原因，并提供“允许通过本机代理连接…”。

**Fake-IP 选项（默认关闭，只能由所有者在管理台“设置 › 高级 › 网络”里打开）**：打开后，
官方域名解析到普通 IPv4 `198.18.0.0/15` 也被接受，登录、后台续期、MCP 交换、下载等
都在每次检查时读取这个设置，不需要重启。其余规则不变：HTTPS 证书校验、固定的
issuer/resource/端点、`checked_url`，以及本机、局域网、链路本地、CGNAT、ULA、组播等
非公网应答一律拒绝；IP 字面量（任何数字写法）、IPv4 映射/兼容的 IPv6 形式，以及
混有任何其他非公网地址的应答也照样拒绝。

如实说明代价：Fake-IP 应答不携带真实目的地址，ATM 在这台电脑上无法再核对连接
的去向，这一检查交给本机代理负责。这是所有者明确选择的放宽，Agent 和 CLI 都不能
打开它（没有对应命令）。不需要放宽的做法是在代理里让这些域名返回真实 IP（Clash
`fake-ip-filter`；Surge / Shadowrocket `always-real-ip`）。ATM 仍不自动修改代理、DNS
或全局网络设置，也不读取系统代理（`trust_env=False`），打开后也不会自动重试登录。

## 验收边界

隔离测试覆盖假 OAuth、PKCE/resource/issuer、加密与旧 Key 保留、轮换/到期/并发/未知结果、
真实子进程重启、真实本机 HTTP 回调、MCP Bearer 与不重放、launchd 配置和网页契约。
真实账户是否接受动态客户端注册、是否实际签发 offline refresh token，以及实际续期，
需人类完成本机授权后单独验证；协议测试成功不等于真实供应商验收。

官方依据：[Higgsfield protected-resource metadata](https://mcp.higgsfield.ai/.well-known/oauth-protected-resource)、
[Clerk authorization-server metadata](https://clerk.higgsfield.ai/.well-known/oauth-authorization-server)、
[MCP authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)、
[RFC 6749 refresh](https://www.rfc-editor.org/rfc/rfc6749#section-6)。

### 本机验收记录：2026-10-02

- 独立分支 `feat/oauth-refresh-20261002`；基线 SHA `449e07bd43468960fa5ed613725149c43e027c38`。
  保留此前锁定修复/订阅 CLI 接入工作；尚未提交、推送或合并。
- 最终非浏览器套件 **769 passed, 2 skipped, 11 deselected**；两项 skip 为未安装 pandoc。
  已安装版本 OAuth 专项 **40 passed**，含真实回环 HTTP、真实子进程、模拟供应商和 launchd。
  独立审阅发现的登录覆盖/服务安装竞态已修复并新增复现回归。
- 现有本机安装已更新；完整包及 RECORD 均保留可恢复备份，不移动/reset vault。
  Claude/Codex 两份 Skill 均备份更新。运行包内容摘要：
  `4f38922ab9d60e5e14a58fa6dfd4b0e4c0ef9589bd9ca2d427c298c4ca085bd0`。
- 原生 Chrome 私有入口实测显示 OAuth 卡片、`oauth_dns_policy` 与「待连接 / 服务就绪」。
  页面刷新会清掉其内存会话码，应从私有 CLI 入口重开；未把会话码放进聊天或读取文件。
- **真实连接仍待验收**：系统 DNS 将 `mcp.higgsfield.ai` / `clerk.higgsfield.ai` 分别解析为
  `198.18.0.144` / `198.18.0.138`。预检在发请求前停止，状态为 `needs_login`，
  尚未注册 OAuth 客户端、取得 access/refresh token 或安装真实后台服务。代理、DNS、
  HTTPS/地址检查保持原样；未生成内容、扣订阅额度或读取官方 CLI 凭证。
  （2026-10-20 起可由所有者打开上文的 Fake-IP 选项；默认仍拒绝。）
- 诊断/测试/安装备份收据：`/private/tmp/atm-oauth-refresh.0FxmUB/`；原生界面截图
  `oauth-console.png`。真实注册、授权、轮换及真实 launchd 运行需要网络路径解决后验证。

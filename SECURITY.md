# ATM v0.8 default workflow

The new local window combines a fixed unlock lease with selected-Key, exact-project,
same-UID **trusted code** consent. It intentionally allows edits/new commands inside
that project; it is not the older exact-command permit and is not a malicious-code sandbox.
See [one-window threat model](docs/QUICK_START_SECURITY.md). Strict grants remain strict.
No raw-secret read endpoint, password-in-chat flow, or public Web listener is added.

# v0.7 security review scope

Read [the current self-review](docs/SECURITY_REVIEW_V07.md) before using the new `exec` interface.
This release adds a separate credential-first session; generic execution is SAME-UID ONLY and is not a sandbox.
It does not turn the existing registered-tool Broker's cross-UID support into safe arbitrary-code execution.
Selected secrets enter the approved child environment. Deliberate file/network/transformed-output exfiltration is not prevented.
New generic exec uses bounded memory pipes and persists only job metadata; historical registered CLI adapters below may still use temporary output files.
Fixed lease/lock/revocation prevents NEW admissions, not existing plaintext copies. A private Owner session capability is distinct from Agent capabilities.

The following historical security documentation remains applicable to the optional tool layer; its earlier statement that the broker has no administration RPC describes the old registered-tool Broker. The new session service adds tightly authenticated OWNER-ONLY key CRUD, no raw retrieval and no Agent administration.

# 安全边界 / ATM 0.2

ATM 是个人开发者的本地工具执行器，不是隔离任意恶意 Agent 的操作系统安全产品。本次没有独立安全审计。以下是实现与边界，不是“不会泄露”的保证。

## 已实现

凭证 AES-256-GCM 静态加密，名称作为认证附加数据，口令模式使用 scrypt。新 vault 可把主密钥放入受支持的系统 keyring；不自动降级到明文。没有 `get-secret` CLI。旧库密文兼容且 keyring service 显式迁移读取。

API 密钥在执行层按操作注入，不放进提示词、命令参数或正常日志。下载请求不继承 API 授权。普通 API 只允许固定/明确配置的 HTTPS origin、不跟随跳转、清空跨请求 cookies，不盲目自动重试。ComfyUI 与本地 MCP 的 loopback HTTP 是明确配置例外。

CLI 不经过 shell，不接受任意额外参数字符串。绑定入口 SHA-256 有变化必须重绑；子进程默认最小环境，凭证只通过已声明映射注入，执行控制类环境变量不能覆盖。超时结束进程组，返回不确定状态。

新工具 manifest 是有界 JSON，无 eval、外部 `$ref`、Python 插件自动加载或自动包安装。安装摘要绑定规范化定义，自定义命令隐含代码权限，非 GET 请求隐含写权限。工作流拒绝前向引用/嵌套；本地请求键防重复认领。

外部写、生产变化、项目代码、可能收费分开标記。Stripe Checkout 入口只接受 test-mode key；Printful 下单只创建未确认草稿；Shopify 只创建 DRAFT，不自动生产和公开上架。

路径类参数必须位于 workspace；输出文件哈希分块计算，单个工程产物上限 1 GiB，产物列表有数量界限。普通输入格式与媒体完整性验证属于有限文件检查，不是恶意解析器输入的完全防护。

## 没有提供的保证

**同权限进程仍可能读取内存、改程序或操纵授权。** CLI 参数、MCP allowlist、manifest 摘要是调用者声明，不是人类身份认证。Agent 若有任意 Shell 与库文件权限，就可能绕过 wrapper；需要 OS 沙箱/独立执行侧车/可信确认窗口才能提高该边界。Skill 也不是安全边界。

系统 keyring 实际调用可能允许同一 OS 用户读取主密钥；原生 macOS/Windows/Linux keyring 未在本次环境端到端实测。跨目录移动 keyring 库也未自动实现。口令环境变量属于用户选择的无人值守折中，不能视为独立秘密管理服务。

入口哈希不锁定 Node/Python 依赖或动态库。CLI 读取自己的 HOME 配置并复用已有登录；恶意/被替换的依赖、PATH 工具、已批准项目脚本可能访问宿主。Docker socket 不是安全沙箱；Blender `--disable-autoexec` 不是完整文件隔离。

Pandoc Markdown 动作使用其 `--sandbox`。部分 Pandoc 发行版的 DOCX 默认数据在 sandbox 中不可读，因此 DOCX 动作**显式要求 execute_code，使用固定无过滤器命令而不宣称有 Pandoc sandbox**；仅对可信本地文档运行。它没有偷偷将受限制模式重试为不受限制模式，而是独立声明的动作策略。

动态和用户自建 HTTPS origin 做公共地址检查，但尚未把 DNS 解析结果固定到 TLS socket，DNS rebinding 仍是边界。MCP HTTP 同样不声称彻底消除 rebinding。CLI 临时输出文件在程序退出前无磁盘配额，只有返回大小/任务超时限制。Windows 完整 ACL 和进程组行为未实测。

凭证表与独立 OAuth 连接表加密，job 参数、响应正文、网页来源链接和工作文件可能包含隐私。脱敏是尽力防意外回显，并不能识别服务端生成的所有敏感数据。尤其 OpenCLI 登录态、signed URL、客户和项目资料不应写到公开日志或共享仓库。

MCP 支持可选的固定 Higgsfield OAuth PKCE 登录/刷新，详见 docs/OAUTH_REFRESH.md；不含 sampling、elicitation、legacy SSE、恢复流。OAuth endpoint/issuer/resource 固定，回调检查 state/issuer/Host，刷新轮换先持久化 claim，未知结果不自动重试。后台续期须明确启用且使用原生 keyring，不延长项目 Key 授权，不读取或改写官方 CLI 登录文件。服务器内容与返回文本是不可信输入，不构成新权限或操作指令。异步网络失败后“未知”不能当成“失败没花钱”。

交接 provenance 是宿主声明 + origin 检查 + 文件哈希，不是供应商签名。3D 可加载、服装能导出、API 返回成功，不代表内容被用户接受、样衣合身或合同/付款正确。

## 发布前仍需完成

独立 Tripo 浏览器见 [服务器契约](docs/TRIPO_SERVER.md)：仅同 UID Unix 工具桥接，
原权限/预算/防重发保留；profile 不同步。临时 VNC 只经 SSH 转发的 loopback 使用，
信任服务器本地用户；不是多租户隔离。停机保留 profile，登录过期需人工重新认证。

见 `docs/ROADMAP.md` 的真实供应商/OS 矩阵、OAuth、受限执行、可信批准、webhook 验签和硬预算门槛。发现问题请在用户选择的私有渠道报告；此包尚未提供真实托管披露邮箱或已发布 GitHub security advisory 地址，不要给虚构地址发送秘密。


## v0.5 additions

Read [sync-v1 security contract](docs/SYNC_PROTOCOL_V1.md) for exact cryptographic composition and limits.
Device-specific X25519/HKDF/AES-GCM packets with pinned Ed25519 signatures protect transport content,
not compromised endpoints. Local vaults and identities remain independent. No forward secrecy against a
later stolen recipient private key, no Byzantine-writer consensus, no full-database rollback protection,
and no guarantee of availability from an untrusted relay. Revocation cannot retract existing plaintext copies.

The scoped Broker unlocks once per bounded lease. It has no raw-secret, administration or arbitrary-shell
RPC. Client profiles contain plaintext bearer capability tokens in0600 files; they are sensitive and must
never enter source control or shared sync directories. Default same-UID mode is a convenience interface,
not malicious same-user isolation. Optional Linux group sockets check SO_PEERCRED clientUID, but an
approved CLI executes with Broker privileges; execute_code is not a sandbox. Avoid running Broker as root.
Memory clearing drops Python references and is not a secure-zeroization/swap/core-dump guarantee.

MCP/workflows/handoffs are unavailable in restricted Broker mode until recursive authorization exists.
Provider-side expiry/OAuth refresh and billing limits are not bypassed or guaranteed by session reuse.

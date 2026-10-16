# 网页与 CLI 登录态迁移研究

日期：2026-10-06。状态：**文档研究及隔离实验完成；真实供应商跨设备迁移待验证。**

## 结论

**部分登录态能迁移。决定因素是认证机制、状态是否完整和服务器策略，而非单纯“换了设备”。**
技术上可复制的登录态本身属于凭证。迁移将账户能力交给接收机器；这不是普通配置同步。
本次只查询公开资料、检查现有实现并测试假账号，现有 vault、真实登录及 ATM 同步契约保持原样。

## 哪些状态可能迁移

| 状态 | 可移植性与限制 |
|---|---|
| 普通会话 Cookie、bearer token | 服务器接受该凭证且状态完整时，另一浏览器可能复用；过期、撤销和风险验证仍由服务器决定 |
| localStorage / IndexedDB 中的认证数据 | 可作为应用状态的一部分转移，但快照范围必须覆盖应用实际依赖；默认快照和完整应用状态不是同义词 |
| sessionStorage 等额外状态 | 常见快照未必涵盖；缺失可以造成应用显示退出，哪怕 Cookie 已恢复 |
| 整个 Chrome profile 目录 | 包含广泛隐私数据，且磁盘加密依赖 OS、用户或应用身份；跨 OS/机器直接复制不是可靠方案 |
| 设备绑定会话 / proof-of-possession | 持续使用或续期依赖原设备密钥；复制短期 Cookie 不等于获得其续期能力 |
| CLI OAuth 会话 | 要看客户端身份、密钥存储、refresh 机制和供应商契约；网页登录成功不等于 CLI 持有同一份认证数据 |
| Passkey | 常规浏览器认证状态快照不是 1Password 或硬件 Passkey 私钥备份；Passkey 同步由凭证管理器单独处理 |

依据：[Playwright 认证指南](https://playwright.dev/python/docs/auth)说明认证状态可以复用，并警告其包含可用于冒用账户的敏感信息；
[storage_state API](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-storage-state)区分快照选项。
本表对迁移成败的判断是机制分析，不是对任何具体站点的成功承诺。

### 两种“设备绑定”应区分

1. **磁盘存储绑定**：原始 profile 的加密数据在接收机器上解密受限。
   [Google 的 Chrome 存储说明](https://security.googleblog.com/2024/07/improving-security-of-chrome-cookies-on.html)
   说明 macOS 使用 Keychain，并以 Windows App-Bound Encryption 为例说明机器绑定与 roaming profile 的冲突。
   这不证明所有网站的服务端会话都绑定设备。
2. **服务端会话绑定**：服务器要求密钥持有证明。
   [Google DBSC 说明](https://blog.google/security/protecting-cookies-with-device-bound-session-credentials/)
   使用硬件保护密钥续期短时 Cookie；复制 Cookie 可能短时有效，但缺少该密钥便缺少后续续期能力。
   启用情况需逐站点确认，本次没有测试原生 DBSC，也没有推定 Tripo/Higgsfield 已启用。

## 隔离实验：16 项通过

使用已安装 Playwright 1.63.0、原生 Chrome、真实 localhost HTTP 和假账号。
两个独立持久浏览器进程/profile，以及一个临时上下文，全部运行在**同一台 Mac**。
实验验证状态复用与失效机制，不是两台物理机器或 Mac → Linux 的验收。

| 检查 | 预期并观察到的 HTTP 状态 |
|---|---|
| 来源 Cookie 登录 | 200 |
| 来源设备证明 | 200 |
| Cookie 在另一独立浏览器复用 | 200 |
| localStorage 在另一独立浏览器复用 | 200 |
| 默认快照缺 IndexedDB | 401 |
| 默认快照缺 sessionStorage | 401 |
| Cookie 已复用，但私钥不匹配 | 401 |
| 原生快照显式包含 IndexedDB | 200 |
| 包含 IndexedDB 的快照仍缺 sessionStorage | 401 |
| 来源首次刷新 | 200 |
| 接收端复用已轮换 refresh token | 401 |
| 检测复用后，来源 refresh family 失效 | 401 |
| 服务端撤销后来源请求 | 401 |
| 服务端撤销后接收端请求 | 401 |
| 过期后来源请求 | 401 |
| 过期后接收端请求 | 401 |

预期的 401 是失败路径断言通过，不是登录成功。
设备证明采用内存中 `extractable=false` 的 WebCrypto ECDSA 密钥和服务端签名验证，
**不是 TPM/DBSC 或跨 OS 密钥存储测试**。轮换、复用检测和撤销采用夹具自定义策略，
不是 Tripo/Higgsfield 行为证据。

未访问生产账号、未读取真实认证文件；假状态快照仅在内存处理，没有写出快照 JSON。
隔离浏览器目录自然持久化假账号数据。应用请求限定为夹具 origin，外部应用请求计数为 0；
该计数不是浏览器全部后台/OS 网络活动审计。

临时证据（不是产品安装文件）：

- 脚本：`/private/tmp/atm-session-research-20261006/probe.py`
- 回执：`/private/tmp/atm-session-research-20261006/receipt.json`，`passed=16`、`failed=0`
- 日志：`/private/tmp/atm-session-research-20261006/probe.log`
- 脚本 SHA256：`9eef22a7a60d6b9b59fba4efa2e330a9d1186d7544f08d55d49f7cba72e9ce7d`

## 安全与可靠性风险

1. **会话等同凭证**：有效 bearer 会话的接收者可能直接使用既有会话，省去密码/MFA 的初始登录步骤。
   实际权限取决于站点和二次验证；可能覆盖私人素材及订阅额度，而不是某个小范围 API 权限。
2. **扩大信任面**：服务器管理员/root、同用户程序、日志、备份、镜像、调试端点和交接组件都应纳入威胁模型。
   传输加密解决的是链路泄漏，接收端解密后的账户能力仍存在。
3. **两台机器刷新冲突**：某些 OAuth 实现轮换 refresh token，并在旧 token 重用时撤销该授权族。
   同时维护同一份复制会话可能导致双方掉线。依据：[RFC 9700 §4.14](https://www.rfc-editor.org/rfc/rfc9700.html#section-4.14)。
   这是条件风险，不是这两个供应商当前策略的确认。
4. **初次成功不等于持久成功**：后续刷新、浏览器重启、服务重启、过期和撤销需独立验证。
5. **ATM 锁定不是上游退出**：已有 CLI/浏览器会话由供应商及其客户端维护。
   ATM 的调用权限、固定 lease 和付费门槛约束 ATM 路径；同用户程序直接使用客户端属于另一边界。
6. **平台契约独立于技术成败**：应核对账户共享、自动化和订阅使用条款。
   [Tripo 当前条款](https://www.tripo3d.ai/terms)涉及凭证保管与自动化限制，未承诺 Cookie 可迁移；
   本研究不将个人服务器使用和向他人分享账号视为同一情形。

## 对当前 ATM 的判断

已检查 `sync.py`、`studio_runtime.py`、`oauth.py` 及对应文档：

- [多设备同步](MULTI_DEVICE.md)：同步选定服务凭证，浏览器 Cookie/profile、CLI 登录、主密钥及 Agent grant 留在各自设备。
- [Tripo 独立服务器](TRIPO_SERVER.md)：已实现服务器自己的持久浏览器后端及临时人类登录入口；
  日常执行不依赖本机中继。真实 Linux、SSH 断开/重启以及真实 Tripo 服务器登录仍待验收。
- [Higgsfield 订阅 CLI](HIGGSFIELD_SUBSCRIPTION.md)：CLI 自行持有认证。
  [官方 CLI](https://github.com/higgsfield-ai/cli)提供 `auth login` 并说明会话失效后重新登录；
  未发现官方承诺的跨设备网页登录快照导入契约。
- [ATM OAuth 刷新](OAUTH_REFRESH.md)：独立加密连接及刷新路径，既不是 CLI 会话镜像，也不是 vault Key 同步。

**目前真实 Tripo 和 Higgsfield 登录迁移的状态都是待验证；公开资料加夹具结果不足以宣称已成功。**

## 产品路线建议（提案，尚未实现）

默认采用**远端独立授权/独立浏览器 profile**。支持 OAuth 的 CLI 可研究由本机浏览器完成人类确认、
向远端 CLI 交付新授权的官方流程；具体 callback、端口转发或 device flow 以各 CLI 契约为准。
它和复制本机已有会话是两条路线。

若后续增加迁移，定义为**按站点、按接收设备显式批准的一次性交接**，与常规 Key 同步分开：

- 只覆盖明确的服务 origin 和必要身份提供方；排除整个日常 Chrome profile。
- 人核对双方设备身份及实际账户；认证数据避开聊天、Agent 原始输出与日志。
- 审阅采集/接收组件，端到端加密、独立接收 profile、受限文件权限、明确交接包有效期。
- 先只读验证账户，再验证刷新、重启、过期、撤销和双端冲突；上传、生成和扣费仍分别确认。
- 交接包 TTL/清理只管理包的生命周期；上游会话撤销必须通过供应商机制落实。
- 遇到设备证明要求时走新的供应商登录流程，浏览器安全策略及 sandbox 保持原样。

现成参考：[Cookey 上游](https://github.com/Lakr233/Cookey)描述手机登录、加密中继和 Playwright 状态交接。
这是“登录态交接”路线的实例，**本次仅研究其公开说明，未安装、未做代码安全审计，也未验证其与 Tripo/Higgsfield 的兼容性**。

## 后续真实验收门

真实迁移需另行明确具体站点、账号范围、接收机器及凭证交接授权。
成功标准是接收端账户身份一致、只读操作成功、刷新/重启独立运行、过期和撤销明确生效，
并记录源端是否受影响；“页面看起来登录了”只算初步观察。

本轮只新增研究文档，未修改运行时、同步协议或安装，也未迁移任何真实登录。

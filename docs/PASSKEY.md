# 本机 1Password / Passkey 解锁

## 使用体验

Agent 从已审阅源码准备可选 `passkey` 依赖和 `atm ui`，由启动终端打开带私有
会话的 **localhost** 网页。在“连接与凭证”点“绑定 1Password / Passkey”：

1. 先初始化或验证现有密码/keyring；主密码只填本地表单。
2. 在浏览器的保存提示中选 1Password，由本人确认。
3. 再次验证该 Passkey，并取得 PRF 输出；成功后才保存本机绑定。

之后 `atm start` 的原窗口可选“用 Passkey 解锁并继续”；管理台也可用 Passkey
解锁固定 30 分钟。密码入口一直保留，项目/Key 范围仍需明确确认。
浏览器/凭证管理器需支持 **WebAuthn PRF**。只有签名而没有 PRF 时，ATM 报
`passkey_prf_missing`，不会把“通过身份验证”误当作“解密成功”。浏览器创建的
凭证可能已留在 1Password，但 ATM 绑定尚未写入；由本人在 1Password 核对。

可选安装是审阅过的本仓库 `.[secure,passkey]`，不是同名 PyPI `atm`。
功能开发和临时目录测试并不自动升级现有安装；升级遵守原 vault 保留及依赖审阅流程。
初次依赖批准仅覆盖临时测试目录；随后用户明确请求“安装升级”，本机安装结果见下。

## 密钥与验证合同

- 首次绑定必须使用原恢复密码/系统 keyring，已有项目解锁状态不代替恢复验证。
- 同一现有 master key 用 PRF(32 bytes) -> HKDF-SHA256 -> AES-256-GCM 包装。
  随机 PRF salt 和 vault/credential 绑定纳入派生/AAD。原 secrets 密文和 vault
  配置原样保留，兼容旧私有加密标记 `ATR-v1`；没有整库重加密或重置。
- 使用 Duo Labs `py_webauthn` 验证注册/认证签名、RP hash、UP、UV、计数器；
  本版只注册 ES256，并要求 resident credential。同步型 Passkey 的零计数器
  按 WebAuthn 库规则处理，非零计数器回退则失败。
- localhost RP；服务仍只监听 127.0.0.1，精确校验 Host、Origin、同源请求、
  私有 bearer 和有界严格 JSON。每次单用 challenge 绑定本窗口和操作意图；
  项目窗口还绑定 request ID + scope digest。其他端口的响应不跨窗口复用。
- 每个窗口只保留一个 ceremony，最多三分钟；绑定第二阶段继承首阶段截止时间。
  取消、失败完成尝试、关闭、锁定或计时器到期丢弃临时引用；不宣称内存擦除。
- PRF 输出、密码和 master key 仅瞬时驻留浏览器/本机请求/服务内存，不落盘、
  不回读到 API 响应、日志或聊天。公开状态只包含名称、ID、时间及停用状态。
- 本地验证记录最多 16 条（含停用记录）；包装主密钥与公钥仅放本机私有状态库。
  停用标记保留记录，不移除 1Password 项目、不自动终止已启动的会话。
- 验证结果以事务 CAS 更新签名计数器，注册/停用并发变化导致明确失败。
  解包后再验证原 vault check；错误 PRF/密钥不会启动会话或发放项目权限。
- 解锁仍固定 1800 秒，不因重复验证/调用续期；普通凭证授权及旧严格模式不放宽。

## 同步与 headless

ATM 不同步本机 Passkey 绑定、包装主密钥、浏览器登录或会话。
1Password 自身可能同步 Passkey，但这不创建另一台 ATM 的主密钥/绑定。
远端用它自己的恢复密码/keyring 登录，纯 headless 保持私有终端流程。
本版仅本机 localhost；未新增远程 HTTPS RP、Service Account 或无人值守解锁。
Tripo/Higgsfield 登录和订阅额度仍是各工具的独立状态。

## 验收边界

`tests/test_passkeys.py` 明确区分 mock verifier 与真实维护库的签名/PRF 包装测试，
并检查原密文、旧标记、密码恢复、重放、过期、取消、错误来源、CAS、本地 HTTP、
范围和真实 `atm use` 子进程。`tests/passkeys.test.mjs` 检查浏览器 helper 的
buffer 转换、PRF 缺失、取消及凭证不进入持久存储的传输结构。
`tests/test_passkeys_browser.py` 用原生 Chrome + CDP 虚拟 authenticator、真实
localhost 导航/CSP/HTTP/WebAuthn PRF；它不是 1Password 扩展验收。
真实 1Password 保存/验证需本人在本机窗口完成；具体浏览器/扩展 PRF 支持另验。

2026-10-05 功能开发阶段验收（隔离假状态，当时尚未升级本机安装）：

| 检查 | 结果 |
|---|---|
| 新增协议、存储、真实维护库、HTTP/子进程和原生 PRF | 50 通过；5 个 mock 签名变体明确跳过，真实签名变体已执行 |
| 全量非浏览器串行回归 | 908 通过；7 跳过（上述 5 + 缺少 Pandoc 2），19 浏览器用例另行验收 |
| 构建 wheel 的浏览器串行复测 | 原生 PRF 正/反向 2 通过；既有 HTTP 桥接 UI 组件 1 通过 |
| Node helper / 既有 Tripo 合同 | 243 通过，其中新 helper 6 项 |
| wheel 回读 | 79 个代码/资源与源码逐字节相同；包含 passkey extra；唯一命令仍为 atm |
| 真实 1Password 扩展 / 原生 keyring | 尚待本人确认，不等同于虚拟认证器验证 |

早期及并行运行的 HTTP/浏览器传输超时记录保留；首轮全量在失败后中止，
不计为通过。独立串行重测通过，未放宽断言、授权或浏览器策略。另修复了
管理台锁定后立即重开时自有 listener 仍在关闭的竞态，等待关闭最多两秒，
不延长租期，也不自动重发命令。测试耗时/并发环境与逻辑根因保持分开。
临时回执：`/private/tmp/atm-passkey-acceptance-20261005.json`。生产 vault、真实
Keys、1Password 数据和付费供应商均不参与自动测试。

### 本机安装升级（2026-10-05）

用户明确请求后，实际 `~/.local/bin/atm` 已升级到含 Passkey 的本地 0.8.0
构建，安装 `webauthn==3.0.1`，保留既有依赖版本、Playwright 和同一个运行路径。
Claude Code / Codex 两份用户 Skill 已备份更新，原 ATM home 和便捷模式保持原样。
安装切换期间原 `state.sqlite3` 的 inode/大小/修改时间逐项相同；未搬移、重置或
读取生产凭证、认证文件，也未自动续期或扩大授权。

这次复测先明确报出隔离目录过长导致的 `socket_path_too_long`，用新短目录验证；
随后捕获管理台并行读取的 `ERR_CONNECTION_RESET`。页面同时读取十个元数据端点，
Python 3.13 默认 TCP 待接收队列仅五。新增十连接先排队再接受的测试在旧版直接
复现连接重置；仅把 Console 队列设为有界 32 后通过，不改变 Origin/Host/bearer、
租期或任何权限。临时诊断插件不计正式验收，失败回执全部保留。

最终重新构建的 wheel：87 通过、5 个原 mock 签名变体跳过；Node helper 6 通过。
切换后**实际安装**再验收原生 PRF 正反向、连接突发、真实子进程、密码恢复共
7 项，全通过；79 个安装代码/资源与源码逐字节相同。真实 1Password 扩展及原生
keyring 仍待本人在窗口确认，虚拟 authenticator 不替代它们。

旧运行环境先完整备份，再通过 `/usr/bin/trash` 可恢复移走；旧 Skills 各留
`SKILL.md.bak-*`。长期安装包、验收和安装回执保存在
`~/.local/pipx/upgrade-backups/20261005-passkey/`；本次过程回执在
`/private/tmp/atm-upgrade-20261005/`。已启动实际安装的私有 localhost 管理台，
公开静态资源与安装一致，未认证数据请求仍为 401；Agent 没有读取私有 token。
管理窗口存续与安装持久化是两回事：窗口关闭/到期后由 `atm ui` 新开，原 vault
及用户 Skill 保留。1Password 保存/验证由本人完成，未记录成绑定成功。

### 1Password 保存后 PRF 报错与弹窗 null（2026-10-05）

本人截图显示凭证已保存，但后续 PRF 验证报 `passkey_prf_missing`，弹窗还显示
`null`。代码及隔离测试确认两处缺陷：

- helper 仅检查 `first.byteLength`，把普通 32 字节数组误判为缺失。
  [1Password 官方社区 FS-5593 记录](https://www.1password.community/developers-69/browser-extension-webauthn-prf-extension-not-spec-compliant-24672)
  报告过这一返回类型，员工确认已登记；它与截图一致，但未读取本人 PRF，
  具体设备上的原因仍待本人修复后复验。现在兼容 ArrayBuffer、带偏移的
  ArrayBufferView 及普通数组；数组必须恰好 32 项且每项为 0–255 整数，拒绝
  稀疏、字符串、溢出和伪装对象，不补零、不截断、不强制转换。真正缺失仍报
  `passkey_prf_missing`，格式错误另报 `passkey_prf_invalid`，未绕过真实库验证。
- `openModal` 把 keyring 模式下缺省的密码节点 `null` 直接交给 DOM，产生可见
  字符串；现在与既有节点 helper 一致，过滤缺省节点，保留正常密码入口。

Node 红测 15 项失败，修复后 23 项全通过；原生 Chrome + 内存假 keyring 的
弹窗红测明确复现 `null`。修复后协议/HTTP/UI 共 90 通过、5 个原 mock 签名
变体跳过，其中原生 Chrome 保留真实签名/PRF，仅模拟扩展把 PRF 转成普通数组，
验证绑定、解锁、项目子进程和原密码恢复。这不是实际 1Password 扩展验收。
未删除或导出本人已保存的 1Password 项目，不把“保存凭证”记成“ATM 已绑定”。

本机仅更新两处有差异的前端资源及包记录；79 个安装代码/资源与新 wheel/源码
一致。旧资源经 `/usr/bin/trash` 可恢复替换，并在
`~/.local/pipx/upgrade-backups/20261005-prf-array-fix/` 留下原文件和新 wheel。
既有依赖、vault、Skills、授权及旧窗口会话保持原样；重新绑定需本人在新开的
私有管理窗口确认，原保存项先保留。过程/红绿测试回执位于
`/private/tmp/atm-prf-fix-20261005/`。切换后的实际安装又完成 5 项原生/UI 验收，
全部通过；真实 1Password 绑定仍待本人复验。

## 来源

- [1Password 官方 Passkey 使用说明](https://support.1password.com/save-use-passkeys/)
- [W3C WebAuthn PRF 扩展](https://www.w3.org/TR/webauthn-3/#prf-extension)
- [Duo Labs 官方验证库](https://github.com/duo-labs/py_webauthn)
- [webauthn 3.0.1 发布页](https://pypi.org/project/webauthn/3.0.1/)

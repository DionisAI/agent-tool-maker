# v0.7 — 保留数据，换默认入口

从 v0.6 更新程序不重建或移动 vault、设备身份、同步版本和已存连接。停止旧的 foreground Broker / Web 服务后安装新版本；新版本使用 `atm unlock`，默认固定30分钟。

旧 tool grant 不自动获得通用 exec 权限；Owner 使用 `access permit-exec` 增补明确命令规则。已存的有效 Claude/Codex profile 可以添加规则而不轮换 bearer；过期、撤销或来自另一状态库的 profile 明确拒绝。
新注册选择 `atm setup --broker`，审查后 `--replace-skills --apply` 备份更新；不建议 Agent 把客户端 profile 读入对话。

启用统一 session 后，Key 增删改在无活动会话时失败，不自动退回逐条密码输入。Owner 重新 `unlock` 即可，原 Key 并未丢失。
`session-owner.json` 是当前机器的本地管理 capability，不是供应商Key，也不是要分发给Agent的文件。不得同步/提交它。
本版没有强制禁用旧的直接执行路径，故不是抵抗同用户恶意程序的完整安全边界。既有 sync/watch/verify 仍各自管理解锁；详见凭证优先指南。

# v0.2 → v0.3（本轮）

原地使用同一个状态目录，无需迁移或重新加密。不要移动原生keyring关联的库目录。
将ATM更新为v0.3.0后运行setup预览；旧Skill不同会提示冲突，审阅后--replace-skills替换并备份。
connect重复调用现为no-op；轮换凭证必须显式--replace。原skill export相同内容重复执行成功。
新metadata只有配置时间与可选有效期，旧Key保留unknown有效期；无需再次输入才能升级。
默认doctor不解锁，不调用供应商；--check-unlock与verify --allow-network是分别授权的动作。
详情见SETUP_ONCE.md。OAuth refresh仍未实现。

---

# ATR v0.1 → ATM v0.2

包名改为 `agent-tool-maker-local`，Python 模块为 `agent_tool_maker`，主命令为 `atm`。保留 `atr` console-script 别名，但不保留 `import agent_tool_router`。

## 推荐迁移方式：原地读取旧状态，不自动搬家

先备份旧 SQLite 和项目文件，再安装新版。在 macOS/Linux 的默认旧路径示例：

```bash
atm --home ~/.local/share/agent-tool-router doctor
atm --home ~/.local/share/agent-tool-router vault status
```

也可以设置 `ATM_HOME` 指向原目录。优先级是 `--home` → `ATM_HOME` → `ATR_HOME` → 新默认目录。`atr` 别名使用同一规则，不会自动猜测哪个目录是用户正在用的库。

原有 AES-GCM 密文和 AAD 不改。新 vault metadata 记录 keyring service；没有 service 的旧 metadata 从 `agent-tool-router-local` 获取主密钥。**系统 keyring account 包含状态目录的绝对路径哈希**，因此不能直接移动目录后声称一定能解锁。自动搬迁/密钥再包装未实现。

口令模式同时接受 `ATM_VAULT_PASSWORD` 与旧 `ATR_VAULT_PASSWORD`，前者优先。原生系统 keyring 的跨系统迁移未实测；保存好自己的凭证/恢复方式，不要遇到解锁失败就重建覆盖。

旧 API 任务的请求指纹规则保留。新声明式动作加入定义摘要，防止代码改变后用同一请求键隐式调用另一个端点。旧 `blender.cli` 仅目录占位已删除，改为明确的 `blender.inspect` / `blender.render`，不会静默赋予原占位项执行能力。

项目新产物目录为 `.atm/`，不会自动移动原 `.atr/` 文件；旧 job 保存的绝对路径仍需要对应文件存在。用户自定义浏览器数据保留，新自定义工具保存在独立 `custom_tools` 设置。

安装两个版本可能争用 `atr` 命令，建议在独立虚拟环境安装新版本，再导出新版 Skill。默认新库不会自动导入旧项目凭证。没有把网站会员额度转换成 API 余额。


## v0.4 → v0.5

Update the installed program without reinitializing its vault. Sync is opt-in. Each new machine initializes
its own vault+identity and receives only explicitly paired credentials; do not copy an active SQLite vault
to create a second online device. After enabling sync, do not write the state with older ATM versions.

Direct Skills remain compatible. To use limited reusable sessions, create local access grants, preview
`atm setup --broker` and explicitly approve backed-up replacement. This is not enabled silently.
Existing grants pin executable/definition/origin, so review and re-grant when those change. Supplier-Key
rotation alone does not require another agent grant. No source-code deploy, cloud sync or provider rotation
is triggered by upgrading the Python package.

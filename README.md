# ATM — Agent Tool Maker

**把 API Key 配一次，以后交给 Agent。**

ATM 在本机加密保存 Key，供 **Claude Code / Codex** 使用。
Agent 需要 Key 时打开一个本地窗口；你输入一次主密码，接下来 **30 分钟**内，
它能在你允许的项目和 Key 范围内继续工作，不需要逐条批准命令，也不往项目写 `.env`。

## 我怎么开始？

在有本机执行权限的 Claude Code 或 Codex 中，把这个仓库交给它，然后说：

> 安装这个仓库的 ATM，读取根目录 SKILL.md，并为我注册用户级 Skill。
> 保留已有凭证库。以后当前项目需要 API Key 时先查 ATM，自动打开本地授权窗口；
> 不要让我手工敲配置命令，不要在聊天里问密码或 Key。

Agent 负责安装和非秘密配置。**你只处理本地窗口：**

1. **第一次使用：**设置主密码，并填入还没有保存的 Key。
2. **以后使用：**确认窗口中的项目和 Key，输入一次密码，点击“解锁并继续”。
3. **接着做事：**同一授权范围内的新进程、新会话直接复用。30 分钟固定到期，也可以提前锁定。

已经解锁但要增加另一个项目或 Key 时，只确认新增范围，不再输入密码。
第一次没有 Key、Key 过期或同步冲突需要分别处理；解锁不会替你注册供应商账号。

## 实际体验

**你：**“给这个项目加一段 ElevenLabs 旁白。”  
**Agent：**检查 ATM → 自动打开本地窗口。  
**你：**输入 ATM 主密码，点“解锁并继续”。  
**Agent：**使用保存的 Key，继续完成任务。Key 不显示在聊天中。

**你：**“改一下脚本，再生成一版。”  
**Agent：**在同一授权范围和期限内继续，不再让你配置或批准每条命令。

ATM 把选定 Key 临时提供给实际运行的程序。Python 等程序仍可以使用
`os.environ["ELEVENLABS_API_KEY"]`，无需改成 ATM 插件。

## 查看、添加或修改 Key

告诉 Agent：**“打开 ATM 管理界面。”**

它执行 `atm ui`。你在本地网页中管理 Key、工具和多设备同步。
已有 Key 不重复索取；添加新 Key 与更换旧 Key 分开，不静默覆盖。

## 安全范围

默认便捷模式面向**自己的机器、同一个系统用户和可信项目**。
授权只覆盖窗口列出的 Key、确切项目和当前解锁期；新增 Key 不会自动获得权限。
项目代码能接触这些 Key，也可能联网、消费或主动泄露它们，**这不是恶意代码沙箱**。

密码不进入 Agent 对话；存储加密；30 分钟到期不自动延长。
锁定阻止新调用，但不能收回已经交给程序的 Key。
需要逐命令固定程序摘要的场景，保留[严格模式](docs/SECRETS_FIRST.md)。

## 常见问题

**Higgsfield 想用已有订阅额度，而不是 API Key？** 官方 CLI 浏览器登录及[订阅只读工具](docs/HIGGSFIELD_SUBSCRIPTION.md)查询额度、模型与报价；订阅与 API 分开计费，生成另行确认。
CLI 自己管理登录；[ATM OAuth 自动续期](docs/OAUTH_REFRESH.md)另建独立连接，明确启用后保持登录，不延长项目的 30 分钟 Key 授权。

**每个新 session 都要重配吗？** 不用。安装与 Key 持久保存；当前项目授权仍有效就直接复用。
授权到期才需要重新解锁。切换新的项目或增加 Key 需要确认范围。

**多台电脑或服务器呢？** Key 支持[加密同步](docs/MULTI_DEVICE.md)，每台机器独立解锁。
本地一键窗口需要桌面浏览器；纯 SSH/无显示服务器使用指南中的终端会话方式。

**有 Skill 就一定能访问本机吗？** 需要本地 Claude Code/Codex 有执行权限。
网页聊天或云端沙箱不会因为加载 Skill 就连接到你的电脑。

<details><summary>手动安装（可选；正常由 Agent 做）</summary>

Python 3.11+、macOS/Linux。先取得并审阅本仓库，在源码目录执行：

```sh
pipx install '.[secure]'
atm setup --apply
```

升级使用 `pipx install --force '.[secure]'`，再让 Agent 审阅并更新 Skill。
不要重建 vault。已有不同 Skill 会先报冲突；审阅后用 `--replace-skills` 备份替换。
包未发布到 PyPI，不要安装来源不明的同名 `atm` 包。
</details>

## 开发与高级功能

[Agent 操作说明](SKILL.md) · [架构与安全](SECURITY.md) · [工具扩展](docs/EXTENSIBILITY.md)
· [开发说明](CONTRIBUTING.md) · [v0.8 验收](docs/TEST_REPORT_V08.md)

MIT · `atm` 是唯一命令名称。运行测试不等于真实供应商、原生 keyring 或全部客户端已经验收。

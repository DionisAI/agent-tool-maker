# v0.4 补充

默认客户端为 Claude Code、Codex：`atm setup` 预览，`atm setup --apply` 应用。
仅绑定 CLI 使用 `--no-agents`。`atm ui` 打开同一套状态的本地网页管理台，参见
[WEB_CONSOLE.md](WEB_CONSOLE.md)。原有凭证不必迁移，不删除/重建库。

# 一次配置，后续会话复用 — ATM v0.4.0

## 承诺与边界

同一机器、同一系统用户、同一持久状态目录下，配置不随项目或会话结束消失。
每种本地 Agent 注册一次入口；新机器、不同系统用户、云沙箱不是自动共享。
本版本不保证永久免登录：Key 会被撤销，CLI 会升级，OAuth token 会过期。
本版本能诊断已声明的凭证有效期，但没有 OAuth 登录或自动刷新服务。
原生 keyring 可能弹操作系统确认；口令模式仍需每个新进程的合法解锁方式。

## 1. Agent 准备长期安装

经用户允许后，从这个仓库的源码目录安装到独立用户环境：

```sh
pipx install '.[secure]'
pipx ensurepath
```

pipx 不存在时，先使用用户允许的包管理方式安装。不要下载来历不明的同名 atm 包。
不要把供应商 Key 写进安装命令。已有 ATM 先检查版本，不要无条件重新安装。
更新已有 pipx 安装可在已审阅的源码根目录运行 `pipx install --force '.[secure]'`。
新终端检查 `command -v atm`；宿主不继承 shell PATH 时可使用绝对路径。
Git clone 不包含 dist/，wheel 需自行构建或使用版本交付包。

## 2. Agent 规划并应用非秘密配置

只选用户实际使用的客户端和已安装的程序：

```sh
atm setup --agent codex --agent claude --cli ffprobe --cli magick
# 审查路径和动作后：
atm setup --agent codex --agent claude --cli ffprobe --cli magick --apply
```

默认不创建 Skill、不绑定程序、不读取任何秘密、不访问供应商；ATM 状态目录可能初始化。
--apply 只写选定的注册和绑定，既不安装软件，也不登录供应商或初始化/重置密钥库。
缺软件会报告 missing_program/needs_dependencies；安装并审阅对应软件后重跑原命令。
apply 有缺少软件时返回退出码2，已经可执行的非秘密配置可能已保存；重跑会收敛。

相同配置再次执行为 unchanged，不改 Skill 文件时间、不覆盖凭证。不同 Skill 默认冲突；
明确批准 --replace-skills 后先保留备份。绑定过的 CLI 文件发生变化时不自动接受新文件，
应在确认软件更新可信后运行 `atm cli bind NAME /absolute/path`。不跟随用户目录中的符号链接写 Skill。
磁盘与 SQLite 之间不是一个事务，磁盘故障后检查结果并重跑。

默认注册位置：
- Codex：~/.agents/skills/agent-tool-maker/SKILL.md
- Claude Code：~/.claude/skills/agent-tool-maker/SKILL.md；CLAUDE_CONFIG_DIR 会覆盖 .claude 根目录。

生成文件包含当前安装的绝对命令路径和 --home。主 Agent 无需每个项目重新激活开发 venv。
可用 --atm-executable 显式选择另一已安装入口。注册文件落盘不等于宿主已加载；需重启新会话验收。
`atm skill export --destination DIR` 仍可用，但仅导出文件，不代表用户级注册。

## 3. 人只处理秘密和授权

```sh
atm vault status
# 仅尚未初始化时：
atm vault init --backend keyring
atm connect elevenlabs
atm connect fal
atm connect tripo
```

通过自己的私密终端或 `atm ui` 已认证的本地连接表单输入，不向 Agent 对话粘贴 Key。已保存的 connect 默认保留原值且不再提示；
更新某一个 Key 才用 `atm connect PROVIDER --replace`。不需要配置所有157个动作。
需要有效期时可加 `--expires-at 2026-10-01T12:00:00Z`，未知时不要编造。
重新连接会清除旧有效期；未指定时回到 unknown，不把未知当作永不过期。
CLI 默认复用官方登录；命令环境中的可选 vault 覆盖没有配置，不代表官方登录不存在。
站点 origin 和 MCP allowlist 可以由 Agent 准备，但须批准正确账号、域名和权限再保存。

## 4. 检查与最小恢复

```sh
atm doctor --tool elevenlabs.tts --tool ffmpeg.probe
atm doctor --tool elevenlabs.tts --check-unlock
atm doctor --tool ffmpeg.probe --strict
```

默认不解密 Key、不联网、不提示输入。检测绑定文件缺失/变化、可执行权限、凭证名称和已声明有效期。
--check-unlock 仅显式测试主密钥解锁，不调用供应商；可能需要人批准原生 keyring。
--strict 对选定工具的本地阻塞返回2，不把全部未使用服务配置完才允许使用。

| 状态 | 含义与处理 |
|---|---|
| missing_credential | 仅这个连接还没有 Key，私密输入一次 |
| needs_unlock | Key 仍在，先解锁现有库，不重建连接 |
| keyring_unavailable / keyring_key_missing | 检查当前操作系统登录和原始库目录，禁止盲目重置 |
| executable_changed / executable_unpinned | 审查更新后重新绑定，不自动接受新代码 |
| credential_expired | 只更新该连接；自动刷新尚未实现 |
| configured_not_verified | 本地结构可用，但尚未证明服务权限与额度 |
| registered_not_host_verified | Skill 已写入，真实宿主加载仍需验收 |

`route/search/describe` 保留轻量配置发现，不等同于这个本地预检；执行前仍应 doctor 目标动作。

## 5. 主动连接验证

```sh
atm verify elevenlabs
# 明确允许这次读取后：
atm verify elevenlabs --allow-network
```

仅支持已审阅的固定GET账户接口：ElevenLabs、Tripo、Cloudflare用户API Token、GitHub API Token。
不是所有服务都支持。fal/Higgsfield 等返回 unsupported_probe，不自动做收费生成。
GitHub探针使用单独保存的github凭证，不读取/复制gh自己的登录Token；使用gh不要求额外配置它。
Cloudflare账户级token与用户token不同，此探针不涵盖所有类型。
正常输出只保存状态、时间和HTTP状态，不保存原始账户资料、余额或鉴权头。
403可能是这个端点的scope不足，不证明生成/部署动作一定失败；额度与速率限制仍可能适用。
不跟随带鉴权的重定向，不自动重试。Key变更后旧验证标记stale_credential，超过一天标记stale_time。
即使刚验证成功，也只是历史证据，不把它等同于所有功能/未来调用保证。

## 6. 真正验收“新会话不再配置”

开发测试用独立venv、临时HOME和假Key，不触碰用户真实库：

```sh
python -m pip install -e '.[secure,test,browser-test]'
python -m playwright install chromium
python -m pytest -q
```

真实本地套件需要ffmpeg/ffprobe、ImageMagick7的magick、Pandoc；浏览器通过ATM_CHROMIUM指定安装路径。
本地账户验收：配置一次FFprobe，在项目A检查音频；关闭终端，项目B再检查，不重复bind。
用真实供应商时，先同意一项很小的测试，再跨两个进程调用并核对返回文件和账单；不要自动跑全目录。

分别开全新的Claude Code和Codex会话：
> 使用Agent Tool Maker，报告版本和持久状态目录，不重装、不索要已有Key。
> 用已配置的FFprobe检查这个项目的音频，遇到阻塞只报告最小修复动作。

检查：能够发现Skill和绝对入口；两个进程使用同一状态目录；不会重连已保存Key；
实际本地动作完成；密钥和解锁口令没有出现在聊天、进程参数、仓库或报告中。
原生keyring在锁屏/重启后的提示行为、真实宿主与供应商账户必须在用户机器验收。
单元模拟、文件落盘和协议替身不能替代上述步骤。

## 官方接口核查来源（2026-09-30）

- https://developers.openai.com/codex/skills/
- https://code.claude.com/docs/en/skills
- https://elevenlabs.io/docs/api-reference/user/get
- https://developers.tripo3d.ai/en/docs/account
- https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/verify/
- https://docs.github.com/en/rest/users/users#get-the-authenticated-user
- https://pipx.pypa.io/stable/reference/cli.html

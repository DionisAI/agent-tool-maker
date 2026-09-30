# ATM v0.7 — 凭证优先：替代明文 .env，而不改原有程序

适用范围：本机 Linux / macOS 的本地 CLI。真实验收平台见测试报告；Windows、实际客户端加载、真实系统凭证库以及两台公网机器不因此视为通过。

核心路径：**保存一次 Key → 一次明确的程序使用授权 → Owner 解锁 30 分钟 → 不同 Agent / 新进程复用。**
工具目录、manifest、MCP、网页配方均不是使用一个 Key 的前置条件。v0.6 的这些能力仍保留为可选上层。

## 1. 升级，不重建库

从本源码目录进行用户级安装（已安装 pipx 时）：

```sh
pipx install --force '.[secure]'
atm --version
atm vault status
```

应为 `0.7.0`。这是安装本地源码，不是假定 PyPI 上已发布同名包。
已有 vault / CLI 绑定 / 同步身份均保留；不要为升级或解锁失败重新初始化。
程序安装与持久凭证目录分离。已有 `--home` / `ATM_HOME` / `ATR_HOME` 继续使用同一目录。

尚无库才初始化（两种方式选一种）：

```sh
atm vault init --backend passphrase
# 或在系统原生凭证库可用时：atm vault init --backend keyring
```

本指南优先演示密码方式。密码只由人输入本地终端或已认证的本地管理台，不发给主 Agent，不写入配置或进程参数。

## 2. 解锁一次：CLI 或网页二选一

Owner 在专用终端启动：

```sh
atm unlock --ttl 30m
```

这是**显式的前台服务**，请保留该 Owner 终端，Agent 在其他终端运行。没有静默安装开机任务或 daemon。
完成一次密码验证后只在服务内存持有解密所需的主密钥；不会在磁盘保存密码。此命令默认 30 分钟，允许显式 `1s`–`24h`。

也可以运行 `atm ui`，在总览选择“解锁 30 分钟”。网页解锁使用同一个 socket 和同一会话。
网页创建的会话随管理台进程退出而结束；独立 Owner 终端创建的会话不依赖管理台。
关闭浏览器标签页不等于关闭管理台进程；要提前锁定使用按钮或 `atm lock`。

```sh
atm session status
atm lock
```

这是**固定租期，不是闲置超时**。新访问、刷新页面、重跑 `unlock` 都不自动续期。已有会话时 `unlock` 返回 `unchanged`，即便传入更长 TTL 也不延长。
到期或 lock 拒绝新凭证调用，不自动撤销已经交付给子进程的 Key；已获准的有界任务可以继续完成。

一旦本状态库启用了统一 session，`connect` / `vault remove` / 网页 Key 增删改会复用它。会话停止后不退回直接密码输入；只请求重新解锁，不重新索要已有 Key。
首次启用前的老式直接模式仍可使用。旧 `atm run`、OAuth/probe/sync 的其他管理流程没有全部改成统一会话；**新程序请使用 `atm exec`，Agent 入口用 `setup --broker`。**

## 3. Key 独立于工具目录

Owner 可在未解锁时查元数据：

```sh
atm keys list
atm keys find FAL_KEY
```

不存在才补充；新名称先声明，已知内置名称不用声明：

```sh
atm credentials declare acme.production --label "Acme production" --apply
atm connect acme.production
atm connect fal
```

`connect` 在本地隐蔽输入。已保存时直接返回已有状态；明确轮换用 `--replace`。

```sh
atm connect fal --replace
atm vault remove fal
```

删除仅删除本地活动值 / 建立同步 tombstone，不代表供应商端吊销，备份仍可能保存密文。
值支持原 vault 的有限单行字符串；不是任意私钥文件。返回结果不含原文。

可建立**非秘密的发现别名**：

```sh
atm keys alias FAL_KEY --credential fal --apply
atm keys alias ACME_KEY --credential acme.production --credential acme.development --apply
atm keys find ACME_KEY
```

第二个查找会明确显示歧义，不自动选开发或生产账号。替换不同的既有别名必须检查返回的旧版本摘要并提供 `--expected`。
别名只帮助发现，不替代执行时的精确 `atm://slot.name`；别名重新指向别处不能偷偷改变旧调用授权。
别名目前留在本机，不随 API Key 自动同步。

## 4. 原程序不变，不创建 manifest

已有 `app.py` 可以继续：

```python
import os
api_key = os.environ["FAL_KEY"]
# 把 api_key 交给原有 SDK；不要打印、写 .env 或加入命令参数。
```

人必须明确允许这个程序使用哪个 Key。这个**使用授权不是再次输入密码，也不是创建工具插件**。

假设你位于实际项目根目录，用项目实际 Python 环境预览：

```sh
atm access permit-exec --agent claude \
  --env FAL_KEY=atm://fal --workspace "$PWD" -- python app.py
```

计划包含命令、工作目录、精确凭证映射、固定文件 SHA-256、运行限制和批准摘要。只读计划不会读取 Key 或运行程序。
审阅后替换下面占位摘要，再应用**相同参数**：

```sh
atm access permit-exec --agent claude \
  --env FAL_KEY=atm://fal --workspace "$PWD" \
  --apply --approve REVIEWED_PLAN_SHA256 -- python app.py
```

Codex 独立做一次 `--agent codex` 的预览和批准。两者计划摘要不同，不能复用 Claude 的摘要。
所有 ATM 参数要放在 `--` 之前，后面的参数只属于目标程序。

新 profile 默认有效 7 天，可通过 `--ttl-hours` 调整（最大30天）；添加新的已批准规则不会延长旧 profile 的有效期，也不改其 bearer。
已有过期/撤销的 profile 不静默覆盖：明确撤销，用 `--out` 创建新的私有文件后再注册对应入口。
最多32个命令规则。`--timeout` 默认60秒，范围1–300秒。额外依赖可用 `--pin-file` 固定，最多64个项目文件。

## 5. Claude / Codex 在新 session 使用

注册一次受限客户端 Skill：

```sh
atm setup --broker
# 审阅对已有 Skill 的更新后，备份替换：
atm setup --broker --replace-skills --apply
```

Agent 的正常路径：

```sh
atm --client claude keys find FAL_KEY
atm --client claude session status
atm --client claude exec --env FAL_KEY=atm://fal \
  --workspace /absolute/project --request-key task-001 -- python app.py
```

Codex 只需替换 `--client codex`。状态结果列出已批准的 `exec_permits`，Agent 不需要读取包含 bearer 的 profile 文件来猜命令。
客户端自己的环境里没有供应商 Key 或主口令也能运行。
实际执行由本机 Owner 服务完成，工作目录必须与批准的一致；**这是普通脚本兼容入口，不是把程序注册进 catalog。**

不写 `--client` 的 `atm exec` 使用单独批准的 `local` profile，不继承 Owner 的无限权限。先以 `--agent local` 预览/批准同一规则后：

```sh
atm exec --env FAL_KEY=atm://fal --workspace /absolute/project -- python app.py
```

也可使用显式 `--client-profile /private/client.json`。不能同时使用 `--client` 与 `--client-profile`。

运行前可 `--dry-run`；它检验精确权限、文件和凭证状态，不解密 Key、不启动程序。
任务键用于防止响应丢失后重复执行。同一键不会重跑，旧输出不持久保存；需要新业务任务才用新键。

```sh
atm --client claude jobs get JOB_ID
```

任务保存状态、返回码与权限规则引用，不存 `stdout/stderr` 或 Key。
CLI 输出为 JSON；子进程非交互运行，stdin 关闭。此版不支持持续流式终端、REPL 或常驻服务。

## 6. 安全默认值与不可承诺的范围

- 注入只接受 `ENV=atm://精确名字`，不接受 literal Key、dotenv 自动发现或自动扫描其他项目。
- 最小新环境不会继承父进程的其他 Key、密码、代理或 Python/Node 注入变量。执行控制类变量禁止作为注入目标。
- exact argv + workspace + 可执行文件真实目标 hash + Python的pyvenv.cfg + 识别到的普通文件参数 hash；程序变了需要重新批准，不需要重新输入 Key。
- 自动 SHA 固定不覆盖所有 import、动态库和子依赖；通过脚本内部加载代码的安全性仍由批准者负责。
- 使用 `shell=False` 的结构化命令；批准 `sh -c` 或 `python -c` 本身仍等于信任所列代码，ATM 不是沙箱。
- `stdout+stderr` 合计最多256KiB，只在内存有界捕获；原文和若干常见编码会遮蔽。超时/超量时抑制全部输出，状态为不确定，不自动重试。
- 任意获准程序仍可变换输出、写文件、联网、花钱；环境变量方案不可能阻止它滥用已经取得的 Key。遮蔽不等于防泄漏保证。
- generic exec 当前**只支持 Broker 同 UID**；跨用户的一般代码执行明确拒绝，不能以 Owner 权限执行不可信 Agent 代码。旧受限 registered-tool Broker 的跨 UID 行为仍是另一条独立路线。
- lock/revoke/expiry 在接纳新任务时生效；不能收回已释放字节，不保证内存物理擦除。
- 这不是已获独立安全审计的密码管理产品。高权限生产凭证仍需上游最小权限、轮换和真正的执行隔离。

## 7. 故障处理：只修对应问题

| 状态 | 操作 |
|---|---|
| `not_found` / `missing_credential` | 检查账号/名称；只补缺的连接，不把 Key 发到聊天 |
| `ambiguous` | 明确生产或开发凭证的精确引用 |
| `session_locked` / `broker_unavailable` | Owner 解锁；不新建库、不回退 .env |
| `client_not_configured` / `exec_denied` | 预览对应程序的最小授权，不索取 Key |
| `credential_expired` | 在供应商更新该 Key，`connect --replace` |
| `sync_conflict` | 查看版本来源，明确解决；不任选一条 |
| `grant_stale` | 审查改过的脚本/执行器/授权，重新批准同一规则 |
| `connection_changed` | 接纳期间连接有更新；尚未执行，检查当前状态 |
| `unauthorized` | 授权过期/撤销或身份错误；由 Owner 处理 |
| `submission_unknown` / `exec_timeout` | 先查外部系统和原任务，不换键盲目重试 |

## 8. 验收

```sh
python scripts/demo_secrets_first.py --out ./secrets-first-receipt.json
```

使用临时密码/Key、真实 PTY、Unix socket、两个独立 CLI 进程和本地 HTTP 接口。没有工具 manifest；普通 app.py 只从环境变量取 Key。
完整30分钟租期配置实际启动，天然过期使用加速2秒测试；没有假称等待30分钟压力测试。
两个独立 vault 仍在同一机器，**不是两台真实机器验收**；真机步骤见 `MULTI_DEVICE.md`，先完成范围配对再在接收端独立授权/解锁。
不运行真实 Claude/Codex 模型、不调用付费供应商，生成的回执清楚标注这些边界。

### Python虚拟环境

可直接用项目 `.venv/bin/python app.py`。ATM保留解释器的调用路径，而不是解析符号链接后改用系统Python；同时固定其真实目标和相邻 `pyvenv.cfg`。虚拟环境中的依赖可以正常导入；配置或链接目标变化要求重新批准。site-packages的全部依赖没有自动锁定，仍按上面的信任边界处理。

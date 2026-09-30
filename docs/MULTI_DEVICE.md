# ATM v0.5 — 多设备同步与免重复认证

本版本基于 PR #2 的 `b20775c9`。**原程序不会替你部署同步服务器；新功能也不会把所有设备变成一个共享管理员。**
先部署两台本机/服务器上的 ATM，再交换公钥卡片，按服务配对，使用加密文件作为传输单元。

## 先选正确的边界

| 层级 | 本版做什么 | 不意味着什么 |
|---|---|---|
| 设备同步 | 每台设备自己的加密/签名身份；按收发服务白名单同步 Key、有效期、版本与删除记录 | 不复制本地主密钥、浏览器 Cookie、CLI 安装路径、MCP 配置、Agent 授权或任务文件 |
| 冲突 | 因果版本自动合并；不同 Key 并发写入保留冲突并暂停相关调用 | 不按机器时间抢最后写入，不拼接字符串，不自动选择“最新”Key |
| Agent 会话 | Owner 解锁一个有限期 Broker，Agent 持有受限调用凭证；新进程可继续使用 | 不提供任意取 Key 的接口；不保证恶意同用户/root 进程隔离 |
| 服务器运行 | 有限期前台 Broker / 同步 watch，可由用户自己的服务管理器监督 | 本版不安装开机服务，不存储解锁口令，不负责 OAuth 自动刷新 |

同一服务名目前对应一个凭证槽。开发/生产多账号别名尚未实现；**不要把需要区分的两套账户当成可以自动合并的一条 Key。**

## 一、两台机器的最小配置

以下命令里的机器指纹、文件路径都是你实际设备返回的值。公钥卡片不含秘密；仍必须通过已可信的渠道核对完整 64 位十六进制指纹。
`atm sync trust` 默认仅预览，`--apply` 才写入本地信任。未知设备不会自动进入信任表。

### 机器 A：已有 Key 的笔记本

```bash
atm vault status
# 只有没有库时才初始化，已有库不要重建：
# atm vault init --backend keyring

atm sync init --name laptop
atm sync identity --out ./laptop.public.json
```

启用同步会给**现有**凭证建立初始因果版本，但没有配对的接收方时不会发送任何 Key。
之后通过 `atm connect SERVICE --replace` 或网页更新的 Key 都会在同一事务中记入同步版本。

### 机器 B：新服务器

```bash
atm init
atm vault init --backend keyring
# 无受支持原生 keyring 的服务器，明确改用 passphrase；不要两种都运行：
# atm vault init --backend passphrase
atm sync init --name server
atm sync identity --out ./server.public.json
```

B 使用自己的本地主密钥。**不需要把 A 的主口令或系统 Keychain 复制到服务器。**
把两个 public.json 通过已有可信通道交换；两端对照显示的指纹。

### 配成“笔记本发，服务器收”

这比默认双向管理员更适合服务器。只同步本例中的 fal、ElevenLabs，不同步 Stripe 或其他服务。

A：

```bash
atm sync trust ./server.public.json --fingerprint SERVER_FINGERPRINT \
  --send fal --send elevenlabs
# 核对计划后执行同一命令，加 --apply
```

B：

```bash
atm sync trust ./laptop.public.json --fingerprint LAPTOP_FINGERPRINT \
  --receive fal --receive elevenlabs
# 核对计划后执行同一命令，加 --apply
```

要双向编辑，分别给双方增加相同的 `--send` 与 `--receive` 列表。修改已存在配对必须完整列出新范围，并明确 `--replace --apply`；缺省列表为空，不是“保留旧范围”或通配所有服务。

### 第一种传输：单个加密包

A：

```bash
atm sync export --to SERVER_FINGERPRINT --out ./server-001.atmsync
```

通过你已有的 SFTP/SSH、文件传输或其他渠道把 `.atmsync` 文件交给 B。即使传输介质可读取文件，其看到的也只是收发设备 ID、包大小、随机加密材料和密文；无法仅凭文件获得 Key。

B：

```bash
atm sync import ./server-001.atmsync
atm sync import ./server-001.atmsync --apply
atm connections list
```

预览会在本地解密以判断实际差异，但返回值不含 Key。应用成功后，服务器把选定凭证用**自己的**本地主密钥重新加密。`connections list` 仅说明本地连接状态，不代表供应商已验证。

### 第二种传输：一个已经同步/挂载的文件夹

```bash
atm sync exchange --directory /path/to/atm-encrypted-mailbox
atm sync exchange --directory /path/to/atm-encrypted-mailbox --apply
```

每次调用只做一个有界收发周期。目录下按接收设备指纹分区；包用唯一文件名原子发布。只有信任且 scope 匹配的包才能入库，重复包和过时版本不会重复覆盖。

**这个路径必须已经能在两台机器间传递文件。**本版没有 S3、R2、WebDAV 或 Syncthing 客户端，不会仅因为两台机器创建了同名文件夹就自动互通。可以由现有工具传送这些密文文件，但这些外部产品的实际同步行为未在本轮验收。

希望自动轮询时，由 Owner 启动：

```bash
atm sync watch --directory /path/to/atm-encrypted-mailbox \
  --interval 30 --ttl-hours 8
```

这是**前台进程**，启动时解锁一次，在租期内复用；到期、Ctrl-C 或收到被拒绝的包时停止。不会通过静默忽略错误制造“同步成功”。Broker 与 watch 是两个独立进程，口令模式各在启动时解锁一次。

文件后端要求同目录原子 hard-link 发布；不支持该原语的文件系统会报错而不降级。每台设备的 inbox 最多 512 个候选包、每包 8 MiB、最多 256 个服务；不自动做历史垃圾回收。归档应在确认各接收端已应用后操作，不能仅按文件年龄随意删。

## 二、冲突规则

| 情况 | 行为 |
|---|---|
| A 改 fal，B 改 ElevenLabs | 自动合并独立记录 |
| B 先收到 A 的版本，再修改同一 Key | B 的后继版本覆盖已知旧版本 |
| 两端离线修改成完全相同的 Key 与有效期 | 可自动使用相同记录语义，保留必要因果信息 |
| 同一 Key 不同值，或值相同但有效期不同 | 保留多个加密版本；该服务标记 `sync_conflict`，不能继续用其中某个值 |
| 一端删除、另一端同时更新 | 同样冲突，不能静默恢复或静默删除 |
| 删除以后又收到旧备份包 | 删除 tombstone 保留，旧包不能复活 Key |
| 两个人同时解决同一个冲突 | 各自保留因果关系；尚未彼此观察的不同解决结果可以再次冲突 |

这里“合并”是合并服务记录及版本图，不是合并 Key 字符串。Key、删除状态和有效期作为完整记录选择，不能把一个版本的 Key 与另一个版本的有效期拼接。

```bash
atm sync conflicts
atm sync resolve fal --choose REVISION_ID --expected HEADS_DIGEST
atm sync resolve fal --choose REVISION_ID --expected HEADS_DIGEST --apply
```

界面展示来源设备、版本、删除标记和有效期，不显示秘密值。可以据来源选择应保留的版本；两边都不确定时，先明确选择一个状态，再在供应商后台生成新 Key 并通过 `connect --replace` 更新。
`HEADS_DIGEST` 来自当前冲突列表；在你确认前又出现新版本会拒绝旧决定，要求重新查看。

在网页 **设备同步** 页也能配对、导入/导出密文、看冲突、选择版本并撤销本地配对。文件夹路径和 watch 的启动仍走 CLI。

## 三、Agent 不必每次弹密码：使用会话 Broker

同步回答“这台机器有没有 Key”；Broker 回答“这个 Agent 现在允许用什么”。二者不是同一个授权。

### Owner 第一次授权（每台机器各做一次）

```bash
mkdir -p "$HOME/projects/demo"
# 已安装且审查过 FFprobe 时，每台机器绑定一次：
atm cli bind ffprobe "$(command -v ffprobe)"
atm access grant --agent claude --tool ffmpeg.probe \
  --workspace "$HOME/projects/demo" --ttl-hours 168
atm access grant --agent claude --tool ffmpeg.probe \
  --workspace "$HOME/projects/demo" --ttl-hours 168 --apply

atm access grant --agent codex --tool ffmpeg.probe \
  --workspace "$HOME/projects/demo" --ttl-hours 168 --apply

atm setup --broker
atm setup --broker --replace-skills --apply
```

第一次请审阅 Codex 的授权计划；示例的直接 apply 不是绕过批准的理由。
`setup --broker` 为 Claude/Codex 生成只走 `atm --client NAME` 的 Skill。与已有直接模式不一样时，先预览再备份替换。

需要 fal、ElevenLabs 时，将它们的确切动作 ID 加入申请，并显式批准 `--allow-paid`。写入、生产变化、执行项目代码分别需要 `--allow-write`、`--allow-production`、`--allow-code`。**允许付费不等于美元硬上限；不存在自动保证 8 美元预算。**

申请固定 profile 路径已经存在时不覆盖：轮换先撤销旧 grant，用 `--out` 选择新的私有文件，经审阅安装到原位置。旧授权不会因为换文件就自动作废。

### Owner 每个租期解锁一次

```bash
atm broker serve --ttl-hours 8
```

这是前台服务。Owner 的库在进程内解锁一次，服务在租期内为后续请求代做鉴权；正常 Agent 新 session 不需要再填 API Key 或解锁口令。租期最长 720 小时，由 Owner 明确选择；到期/重启后必须重新启动并合法解锁，不持久保存口令。

### Agent 新会话

```bash
atm --client claude broker status
atm --client claude search audio
atm --client claude describe ffmpeg.probe

# tone.wav 与输入 JSON 应位于获准的项目内；使用自己实际文件。
atm --client claude run ffmpeg.probe --input ./probe.json \
  --workspace "$HOME/projects/demo" --request-key audio-probe-001
```

Owner 权限预先固定，Agent **不能加 `--allow-*` 自己扩大授权**，也不能调用 sync、access、setup、get-secret、Shell 等管理操作。Broker 停止、到期、被撤销或 scope 不符时明确拒绝，绝不自动退回直接打开 vault。
同一个 grant 用同一个 request key 不重复提交；不同 grant 不能读取对方任务。

本版 Broker 只支持登记好的直接 API / CLI 动作。MCP、工作流、网页/桌面/人工交接仍走原来明确批准的直接模式；它们未做完递归授权，因此不会在 Broker 中偷偷放行。

### 授权与钥匙的关系

默认 Agent grant 为 7 天，Broker 默认租期 8 小时，供应商 Key 的寿命由供应商决定。三个期限独立。新 API Key 同步到本机后，在定义和目的地址没有变化的情况下，旧的有效 Agent grant 可以继续使用，不必重新批准每次轮换。
CLI 路径/绑定摘要、动作定义或动态服务 origin 改变会使已有 grant 失效，要求 Owner 审查。权限撤销对下一次准入生效，不撤销已提交的上游工作。

`~/.config/agent-tool-maker/clients/claude.json` 是 **0600 的 bearer 能力凭据**。它不是供应商 Key，但持有它可以在有效范围内消费资源，因此不能发到聊天、入 Git 或同步给所有设备。服务端仅存令牌 hash。系统管理员/root 不在此信任边界之外。

## 四、真正的权限隔离与服务器部署

默认在同一个系统用户里运行 Claude/Codex 与 ATM，主要防止误用和避免秘密进入模型上下文。不能说“同用户恶意代码也绝对拿不到 Key”：它可能读该用户文件、修改程序或直接调用底层。

Linux 可将 Owner/Broker 与 Agent 放在不同 OS 用户里，使用已有共享组：

```bash
# 管理员先建立安全目录/现有组，Broker 用户必须属于该组。
# runtime 目录只允许 Owner 写，允许选定组穿过；不要 chmod 777。
atm broker serve --socket /run/user/OWNER_UID/atm/broker.sock \
  --socket-group atm-clients --ttl-hours 8

atm access grant --agent codex --client-uid AGENT_UID \
  --socket-group atm-clients --socket /run/user/OWNER_UID/atm/broker.sock \
  --tool ffmpeg.probe --workspace /srv/reviewed-project \
  --out ./codex-private-profile.json --apply
```

上例 runtime 祖先目录也需要正确的执行权限；`/run/user/OWNER_UID` 通常很严格，管理员应选择适合本机的目录，不要为了照抄示例放开整个 Owner home。另一个选择是专用 `/run/atm`，Owner 可写、组只可穿过。
Owner 将 profile 安全安装到目标 Agent 用户的配置位置，属主改为该用户、权限0600。ATM 不创建账户、组或 sudo 规则。
Broker 对 Linux 的 `SO_PEERCRED` 实际 UID 和 grant 绑定 UID 做比较。即使别的 UID 获得同一个 token，也不能冒用它。跨 UID 组模式当前只支持 Linux；macOS 为同用户0600 socket，Windows Broker 尚未实现。

**这仍不是任意代码执行沙箱。**Broker 的适配器在 Broker 用户身份下执行；给不可信 Agent 批准任意项目构建/脚本，会扩大它接触 Owner 资源的能力。真正的生产隔离还需要进程沙箱、受限文件挂载和网络 egress 策略；本版没有完成这些。因此建议 Broker 本身不用 root，严格限制动作并单独审查 `execute_code`。

## 五、撤销、丢机与恢复

```bash
atm access list
atm access revoke GRANT_ID --apply
atm sync revoke DEVICE_FINGERPRINT --apply
```

两项撤销均为本地管理状态。设备撤销阻止这个节点未来接收该设备的包，以及继续向它出包；不会删除它已经拿到的 Key。多个互信节点要分别撤销，离线端无法即时获知。

丢机时：撤销相关 Agent grant；从其他可信设备撤销该设备；在供应商后台撤销/轮换所有可能泄露的 API Key；只向剩余可信设备分发新版本。之前的 `.atmsync` 包也可能保留已作废的秘密，密码学不能把已交付的信息“收回”。

每台设备有独立身份，**不要复制整个 ATM 状态目录来制造第二个在线设备**。同一设备身份的副本会产生计数碰撞和回滚风险。新机器新建 vault + identity 再配对。
本版不提供主口令恢复、硬件密钥托管或完整备份回滚检测。丢失唯一解锁方式且没有其他已授权设备持有有效 Key 时，应回供应商重置；不是靠程序找回明文。

## 六、验证范围与待做工作

查看 `TEST_REPORT_V05.md`。本轮测试的是本地多份独立 vault、进程、HTTP、Unix socket 及 synthetic 浏览器；不代表真实多云服务器部署、供应商生产调用或实际 macOS Keychain 已验收。

推荐实际验收顺序：两台设备仅同步一把低权限测试 Key → 制造并解决冲突 → 新进程复用 Broker → 撤销后的拒绝 → 再决定哪些生产服务可以同步。

CLI 的官方登录态是独立授权：同步删除某把 API Key 不等于注销该 CLI 或撤销供应商端的 Key。要停止某项能力，还应撤销对应 grant 或停用工具。设备信任与 Agent grant 都不做自动跨设备并集，避免意外扩大权限。

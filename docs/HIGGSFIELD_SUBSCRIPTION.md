# Higgsfield 订阅 CLI 接入

## 契约

此路径使用官方 `higgsfield` CLI、浏览器 OAuth 和选中的账单工作区，走账号的
订阅 credits。[官方说明](https://higgsfield.ai/creator-hub/help-center/integrations/how-do-i-access-higgsfield-via-cli)
与[CLI 源站](https://github.com/higgsfield-ai/cli)是接口依据。
原有 `higgsfield.generate` 仍走开发者 API 的独立美元余额，不替换其鉴权或计费。

登录由人完成。Agent 只运行官方登录命令及元数据查询；认证文件、Cookie、
`auth token` 和插件令牌均不读取。已有 vault、严格 broker grant 保持原状。
CLI 自己持有登录态；ATM 的主密码、30 分钟 lease、`atm lock` 并不管理该登录态。
同一 OS 用户的其他程序也可能使用它，这是可信本机程序集成，不是进程隔离。

## 已定义工具

以下 JSON 位于 `examples/extensions/higgsfield-subscription-*.json`，批准安装后
才进入本机目录；四个工具都需要 `execute_code`，不要求 API credential，不创建生成任务。

| ID | 固定官方命令 | 输入 |
|---|---|---|
| `higgsfield.subscription.account` | `account status --json` | `{}` |
| `higgsfield.subscription.models` | `model list --json` | `{}` |
| `higgsfield.subscription.model` | `model get MODEL --json` | `model` |
| `higgsfield.subscription.cost` | `generate cost MODEL --prompt PROMPT --json` | `model`, `prompt` |

cost 仅估算模型**当前默认参数**的纯文字输入。官方 cost 命令遇到媒体路径会自动上传；
此定义刻意没有 file/media/任意 argv 输入。参数改变后，先重新估算，再确认扣费。
模型名遵循小写字母、数字、下划线；参数值保留现有防 flag 注入检查。
账户结果可能含邮箱；本地结果文件保留元数据，聊天只报告 plan、credits、状态。

Agent 负责核验官方发行来源及摘要、安装 CLI、验证/批准定义、绑定真实二进制。
升级后重新核验与绑定。人只处理官方登录和必要的工作区选择，不接收安装命令清单。
遇到 `No workspace selected`，先查 `workspace list --json`；仅一个本人拥有的工作区
时选择它，多工作区时先明确账单归属。登录成功不等于已选中工作区。

## 执行与验收

注册工具走现有 CLI adapter，不新增 OAuth 客户端或绕过原有权限检查。
未获 `execute_code` 权限时停止；进程失败保留错误状态。相同 request-key 复用既有
任务，不重发；新一次余额查询用新的只读 request-key，避免把缓存当作最新余额。
hash 绑定实际二进制，不绑定一个随时下载或自更新的 wrapper。登录文件不进入 ATM 同步。

### 什么会保存，以及 ATM 在这里的价值

| 状态 | 持久性与归属 |
|---|---|
| ATM 加密 Key、工具定义、CLI 路径/摘要、调用记录 | 保存在用户级 ATM 状态库，重开 Agent 或管理 UI 不清空 |
| 用户级 Codex/Claude Skills | 保存在用户目录，供新的本地 Agent 发现 |
| ATM 默认凭证解锁授权 | 固定 30 分钟，不因配置已保存而永久有效 |
| Higgsfield CLI 登录与账单工作区 | 官方 CLI 自己管理；新进程可复用仍有效的登录，不由 ATM 解锁期控制 |

[官方 CLI 故障说明](https://github.com/higgsfield-ai/cli#troubleshooting)注明 token 是短期有效的；
发生 Session expired / Not authenticated 时需要重新登录。保存登录材料不等于授权永远有效。
本轮验证了新进程/新 Agent 的复用，没有把长期有效或跨电脑登录视为已验收。

仅为了调用 Higgsfield 订阅，官方 CLI 加 Skill 已足够，ATM 不是必要登录组件。
目前 ATM 在此路线增加四个固定查询工具、程序摘要绑定与查询 job 记录；不是完整的
订阅生成管理层，也不拦截其他程序直接使用已登录的 CLI。多个供应商 API Key 的加密
保管、按项目临时提供与统一调用才是 ATM 的主要增益。

验证分为三层：

1. **协议回归**：隔离状态、假 CLI、固定 argv、无 API Key 读取、环境过滤、权限失败、
   重复 request-key、非法输入及升级摘要检查；不连接供应商。
2. **真实只读集成**：官方 CLI 登录后，由 ATM 查询账户、模型、费用估算。
3. **独立 Agent**：新本地 Codex/Claude 读取用户级 Skill，复用登录，只执行上述查询。

生成是后续单独验收门：明确模型、全部参数和费用，获得消费确认后才提交；保存上游
task ID。模糊失败先核对上游任务，避免重复消费。本轮只读通过不代表成片生成或下载通过。

## 本机验收记录

2026-10-02：官方 CLI 1.1.26，macOS ARM64 手动发行安装，原下载包保留。
发行包 SHA-256：`a0bff511a16833f32ea288e9f894ee1404326eb1414168397db8836ccdceed9b`。
实际二进制 SHA-256：`e94d147e08fa1afef5bfdcac3f98facd33ad7c567c619f2f732ba776beed2f91`。
浏览器 OAuth 命令完成；处理工作区选择后，直接 CLI 已返回 Pro 工作区 10.56 credits，
`nano_banana_2` 模型参数、纯文字默认参数费用估算 2 credits。未创建生成任务。
四个工具已按规范化摘要安装，绑定上述真实二进制；Codex 与 Claude 用户级 Skills
已备份更新，两份新 Skill SHA-256 均为
`9b1fb792eb8f9ab088ab53e51e8d1182c635a6d9a4c65429d0941922344fb837`。

协议与真实本地 CLI 回归：**67 passed**；注册/备份相关回归：**8 passed, 29 deselected**。
29 项是未选中的其他 onboarding 测试，不计为本次验收。供应商访问与这些假账号回归分开。

真实只读查询与独立新 Codex Agent 的验收结果均为 `completed`：

| 工具 | 主 Agent 的 ATM job ID | 独立 Agent 的 ATM job ID |
|---|---|---|
| account | `4ad6f0d3-8110-4be3-b1cf-25b00e187f22` | `f97cc29d-3beb-484c-8618-7fa9158c9d6b` |
| models | `0cf1477f-9682-4cbe-a390-d1998ec06510` | `1d3d29ec-f0fc-4410-91c7-aeeeb848edc7` |
| model | `8b42733b-414e-4d43-a61e-de8af68d152a` | `0b551ea5-4096-49ea-90f6-84cab02e78cd` |
| cost | `09511ba9-96b3-40fc-980f-739b8e09a19f` | `29547d6a-0a2f-4adc-ad86-64128a0ab237` |

独立 Agent 复用既有 OAuth 登录与已选工作区，未索取密码或 API Key。
模型目录返回 100 项；`nano_banana_2` 别名解析为 `nano_banana_pro`（Nano Banana Pro）。
两组账户查询均为 Pro / 10.56 credits，费用预估均为 2 credits，`paid_granted:false`。
账户首次沙箱执行得到 `local_failure` 且无 job ID；按正常 require_escalated /
auto-review 路径执行同一只读请求后成功。没有修改沙箱或 broker 策略，也没有重试已提交生成。

前述只读验收未运行生成、媒体上传、发布或付费命令；当时生成与下载为待确认的后续门。
本地证据目录：`/private/tmp/atm-higgsfield-subscription.FpG9PP`，含发行包、原 Skill
备份、pytest 日志、独立 Agent 事件与最终报告。认证材料不进入这些验收报告。
本地分支：`feat/higgsfield-subscription-cli-20261002`，基于
`449e07bd43468960fa5ed613725149c43e027c38`；源码改动未提交/发布，保留原锁定修复。

### 用户确认后的单次生成测试

2026-10-02，用户确认测试后，重新核对现有工作区与成本，直接用官方 CLI 提交一次
`nano_banana_2`：`a blue circle on a white background`，1:1、2K、batch_size=1。
这是官方 CLI 的直接调用，没有新建 ATM 生成工具或将其记作 ATM generation job。
提交前保存独占的防重发标记；随后只查询已保存的任务 ID，没有重新登录或使用 ATM vault 解锁。

- 上游任务：`e9b5bf18-68b9-44dd-a608-1c12eac8888d`，`completed`。
- 官方结果模型：`nano_banana_pro`，Nano Banana Pro。
- 预估：2 credits；账户余额由 **10.56** 到 **8.56**，观测差额 **2 credits**。
- 已下载并校验 PNG，2048×2048，5,060,722 字节；人工视觉观察为白底蓝色圆圈。
- 图片 SHA-256：`d47c89dbea4ec4de045b4397053d354bc50664afeb577d0990f657d27bc13f81`。
- 持久本地输出与回执：`.atm/higgsfield-subscription-test-20261002/test-image.png`、
  同目录 `test-receipt.json`、`submission-intent.json`、创建/完成响应。

结论：订阅生成与下载已实测通过，旧登录跨新进程有效；本次也实际证明官方 CLI
可以直接完成该任务，ATM 对此单一场景是可选封装，而非新增的供应商访问能力。

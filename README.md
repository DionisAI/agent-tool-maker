# Agent Tool Maker · ATM

**Agents don't just use tools. They make them.**

本地优先、MIT 开源的 Agent 工具管理与制作程序。一次配置自己的凭证和 CLI，供多个 Agent 共用。Agent 可以发现工具、执行已批准的动作、起草新的声明式工具，也可以把多个工具组合成可恢复的工作流。

版本 **0.2.0** · Python **3.11+** · 主命令 **`atm`** · 兼容命令 **`atr`**。

这不是另一个通用聊天 Agent，不附送供应商账号、不自动充值、不替用户购买许可证，不在后台自行发帖或部署。

## 这版交付了什么

| 范围 | 实际状态 |
|---|---|
| 工具目录 | 157 个具体动作入口，不是 157 家供应商 |
| 原生执行 | 120 个有限动作：旧版媒体适配器 + 44 个声明式 API 动作 + 66 个 CLI 动作 |
| MCP | 7 组服务的 discovery / batch 共 14 个协议桥接入口；真实服务器、认证和工具白名单需配置 |
| 网页 / 桌面 / 人工 | 23 个交接入口，不冒充自动执行 |
| 原调研范围 | 66 项全部有对应状态：56 项有有限原生动作，1 项仅 MCP 桥接，9 项仅外部交接 |
| Maker | 本地 JSON 工具定义的起草、验证、摘要批准、安装与移除 |
| 组合工具 | 1–20 步串行工作流，类型保留引用、持久化子任务、等待/恢复和请求去重 |
| 凭证 | AES-256-GCM；操作系统凭证库或明确选择的口令模式；旧 vault 兼容读取 |

**实现状态不是测试等级。** 商业 API 使用协议模拟；大多数第三方 CLI 使用真实子进程中的协议测试程序；部分本地程序确实运行。没有使用私人供应商账号进行发布、付费生成、真实部署或商业交易。具体证据见 [测试报告](docs/TEST_REPORT.md)。

- [可搜索的计划图](docs/ROADMAP.html)
- [逐项路线图](docs/ROADMAP.md) / [机器可读路线图](docs/ROADMAP.json)
- [完整动作目录](docs/TOOL_CATALOG.md)
- [威胁模型](SECURITY.md) / [架构](docs/ARCHITECTURE.md) / [升级说明](docs/MIGRATION.md)

## 安装

源码目录内：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[secure]'
atm --version
atm init
atm stats
```

或者从本交付的 wheel 安装（不是假定 PyPI 已有同名包）：

```bash
python -m pip install ./dist/agent_tool_maker_local-0.2.0-py3-none-any.whl
# 需要操作系统凭证库时，再安装可选依赖 keyring。
```

Windows 的虚拟环境激活使用 `.venv\Scripts\Activate.ps1`。本次实际测试平台为 Linux，Windows/macOS 不因此视为已验收。外部 CLI、浏览器、桌面软件和许可证不会随本包自动安装。

## 1. 一次配置，多个 Agent 共用

凭证初始化与输入在**用户自己的终端**完成，不把密钥发送进 Agent 对话：

```bash
atm vault init --backend keyring
atm connect elevenlabs
atm connect fal
atm connect tripo
```

没有受支持的原生凭证库时，显式选择口令模式：

```bash
atm vault init --backend passphrase
```

两种模式任选其一，已经初始化的库不会被上述命令重置。口令模式每次需要解锁；无人值守调用可由用户自行提供 `ATM_VAULT_PASSWORD`，它不会被传给工具子进程。这仍是操作系统环境变量，不等于强进程隔离。

已有 Key 可一次性显式导入，例如 `atm connect fal --env FAL_KEY`，随后移除不再需要的旧环境变量。Higgsfield 填 `KEY_ID:KEY_SECRET`；DataForSEO 填 `login:password`；Ghost 填 `id:hexsecret`；Google API 当前接收用户自己的 OAuth access token，**没有自动刷新实现**。

CLI 沿用自己已有的登录；只绑定明确安装的可执行文件：

```bash
atm cli bind opencli "$(command -v opencli)"
atm cli bind wrangler "$(command -v wrangler)"
atm cli bind gh "$(command -v gh)"
atm cli bind magick "$(command -v magick)"
atm doctor
```

绑定时保存入口文件 SHA-256，升级后需要复核并重新绑定。不会自动 `npx -y` 下载未知程序。Node CLI 必须安装到稳定路径；哈希只覆盖入口文件，不覆盖其整个依赖树。`doctor` 报“已配置”不等于账号已认证。

部分 API 需要明确站点 origin，**不能把 token 放在 URL**：

```bash
atm origin set shopify_admin https://YOUR-STORE.myshopify.com --approve-origin
atm origin set posthog https://us.posthog.com --approve-origin
atm origin set comfyui http://127.0.0.1:8188 --approve-origin
```

`posthog`/`ghost`/`postiz`/`n8n` 需使用自己实际的服务域名。ComfyUI 仅允许显式 loopback HTTP；公共远程服务必须 HTTPS。origin 设置是本地配置批准，不产生调用。

## 2. 交给 Agent 使用

```bash
atm skill export --destination ./skills
```

把 `skills/agent-tool-maker/` 通过宿主 Agent 支持的机制加载。启动宿主的环境必须能找到 `atm`。本机 Skill 不会自动让远端纯网页 Agent 访问你的电脑。

典型工作流：

```bash
atm search '小红书 用户需求'
atm describe opencli.xiaohongshu_search
atm run opencli.xiaohongshu_search \
  --input examples/actions/opencli.xiaohongshu_search.json \
  --workspace ./research --request-key research-001

atm route '把网页项目发布到 Cloudflare' --capability deploy
atm describe wrangler.preview
```

`examples/actions/` 为新动作提供无凭证样例。先改成本次任务参数，再运行。原生动作只覆盖 `describe` 列出的操作；CLI 的版本和站点变化应先通过其官方帮助/registry 核对。

### 不执行，只看具体计划

```bash
atm run wrangler.deploy \
  --input examples/actions/wrangler.deploy.json \
  --workspace ./my-project --dry-run
```

`--dry-run` 编译并校验计划，**不读取凭证、不启动 CLI、不发起网络调用**。路径类输入仍需真实存在；它不是业务正确性证明。

### 写操作、生产与执行代码分开确认

| 参数 | 表示的授权声明 |
|---|---|
| `--allow-write` | 对外写入：发消息、排期、创建草稿等 |
| `--allow-production` | 生产环境或数据库等高影响变化 |
| `--allow-code` | 执行项目代码、受信命令或构建流程 |
| `--allow-paid` | 可能消耗额度/资源的操作，**不是美元硬预算** |

例如，已经批准的生产发布：

```bash
atm run wrangler.deploy \
  --input examples/actions/wrangler.deploy.json \
  --workspace ./my-project --request-key release-v1 \
  --allow-write --allow-production --allow-code --allow-paid
```

这些标记是调用者提交的权限声明，**不是能区分“人类批准”和“同权限 Agent 自己加旗标”的可信安全界面**。宿主负责获得用户的真实授权，更多隔离在计划图中。

## 3. 真正制作工具

### 从已审查的声明式动作起草

```bash
atm make scaffold my.resize --from imagemagick.resize --out ./my-resize.json
# 在编辑器或由 Agent 起草修改，但此时还没有安装。
atm make validate ./my-resize.json
```

验证结果包含规范化定义的 `sha256`、实际隐含权限与计费标记。用户审阅后，把该摘要明确传给安装命令：

```bash
atm make install ./my-resize.json --approve <经审阅的sha256>
atm describe my.resize
atm run my.resize --input examples/actions/imagemagick.resize.json \
  --workspace ./assets --allow-code
```

`<...>` 是要替换的占位符，不要原样复制进 Shell。自定义 CLI 始终要求 `execute_code`；自定义非 GET API 始终要求外部写权限。不能靠在 JSON 里写“只读”来抹掉这些默认要求。

安装以 JSON 数据为单位，不加载任意 Python 插件，不 `eval`，不使用 Shell 命令字符串。既有专用媒体适配器、MCP 桥或打包脚本不能不加审查地克隆成任意代码入口；`scaffold` 会对不支持的种类明确拒绝。

```bash
atm make remove my.resize --yes
```

### 把多个工具合成为新工具

仓库提供 `examples/workflow-web-assets.json`，完成：

```text
输入图片 → imagemagick.resize → imagemagick.webp → 产物与任务记录
```

```bash
atm make validate examples/workflow-web-assets.json
atm make install examples/workflow-web-assets.json --approve <经审阅的sha256>
atm run workflow.web_assets --input examples/workflow-input.json \
  --workspace ./assets --request-key site-assets-v1
```

输入使用 `$input.path`，前序结果使用 `$steps.resize.data.artifacts.0.path`，保留 JSON 类型，不解释成脚本。禁止前向引用和嵌套工作流。

重复使用同一 `--request-key` 不会重复提交原任务；改输入/定义却复用旧键会冲突。工作流包含异步或外部交接时会等待，用户调用 `jobs get --refresh` 继续检查，不启动隐形定时器。多个子任务没有事务回滚保证。

## 4. MCP：发现实际工具，不编造函数名

本版为 Figma、Notion、Linear、Playwright、Chrome DevTools、PostHog、Sentry 各提供 `mcp_tools` 与 `mcp_batch`。它们复用一个通用协议客户端，**不意味着七家服务器的所有功能已做过实测**。

`examples/mcp-http.json` / `examples/mcp-stdio.json` 是需要修改的模板。先只允许 discovery，获得真实工具列表，审查后再把确切名称写入 `allow_tools` 并重新批准配置：

```bash
atm mcp bind chrome_devtools --config ./my-mcp.json --approve-config
atm run chrome_devtools.mcp_tools --input examples/empty.json --workspace ./my-project
# 从结果中选择确切工具名与 schema；不要直接使用模板中的占位名称。
atm run chrome_devtools.mcp_batch --input ./reviewed-calls.json \
  --workspace ./my-project --allow-write --allow-code --allow-paid
```

batch 中 1–12 个调用共享一次会话，整个批次的名称/参数先验收，之后才执行首个工具。协议子集支持 stdio 与 Streamable HTTP JSON/SSE，协商版本为 `2025-06-18 / 2025-03-26 / 2024-11-05`。不实现 OAuth 登录/刷新、legacy SSE、sampling、elicitation、回调审批或流重连。需要这些能力的服务器应交给支持它的宿主，或留到后续阶段。

## 5. 网页、桌面与人工任务

```bash
atm run marvelous_designer.handoff \
  --input examples/actions/marvelous_designer.handoff.json \
  --workspace ./garment --request-key sample-001
```

返回 `requires_desktop`；**没有打开或操作 Marvelous Designer**。宿主 computer use / 用户完成后，提交真实文件：

```bash
atm jobs complete <job-id> --file <项目内文件绝对路径> \
  --source-url https://developer.marvelousdesigner.com/
```

网页返回 `requires_browser`，人工服务返回 `requires_human`。交接只确认文件存在、哈希和宿主来源声明，不确认衣服合身、工厂可制造、订单已付或网页动作符合用户预期。不能访问的账号、平台审核和许可不会被绕过。

## 6. 结果与费用

- 每次调用保存本地 job、参数、版本化定义摘要、执行状态、结果文件和验证等级。
- `completed` 是**该动作的完成级别**：HTTP 返回并不等于商业任务完成；排期创建不等于帖子已经公开；构建提交不等于 App 上架。
- `submission_unknown` / 超时不自动重新发帖、下单或部署。先查原任务/上游状态。
- 不知道费用时 `cost_usd=null`，不是零。没有统一钱包、Crypto 支付或严格总预算功能。
- 普通工程文件做存在性和哈希检查；媒体适配器保留原有有限格式检查。不宣称审美/物理/制造质量保证。
- 日志事件不存提示词；任务参数和结果仍以明文保存在本地 SQLite/项目中，仅凭证列加密。源文件和 API 结果不要包含不必要的秘密。

## 测试与开发

```bash
python -m pip install -e '.[secure,test,browser-test]'
# 按需要安装 ffmpeg/ffprobe、ImageMagick 7 (magick)、Pandoc、Chromium。
pytest -q
```

没有依赖的真实本地集成测试会明确 skip；本次交付环境、实际运行结果、覆盖率、已修复问题和未验证项以 [测试报告](docs/TEST_REPORT.md) 为准。供应商测试默认不访问生产环境、不消费、不发真实邮件。CI 文件只是提供给仓库使用，未声称已经在线运行。

源码结构：`catalog` 发现；`engine` 状态机；`actions` 声明式 API/CLI；`mcp_bridge` 协议；`maker` 定义/组合；`vault` 秘密；`storage` 状态。`scripts/build_v02_catalog.py` 与 `build_release_docs.py` 可重建目录和路线图。

外部工具依赖各自许可证和账户条款；ATM 的 MIT 不替代它们。没有打包第三方完整产品代码或字体文件。尚未发布到 GitHub/PyPI，也未宣称 ATM 名称已获得商标或包名专有权。

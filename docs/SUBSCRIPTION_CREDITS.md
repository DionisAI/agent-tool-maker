# 订阅额度（网站 / CLI）

## 合同

- 总览“订阅额度”与 `atm credits` 显示 owner 网站 / CLI 订阅的剩余积分，以及 owner 设置的下次续期日。
  这是订阅积分，与开发者 API 余额（`tripo.generate`、`higgsfield.generate` 等）分开计费，互不替代。
- 提供方与来源固定，不接受自定义；按下表顺序选择第一个**可用**来源：

| 提供方 | 来源（优先顺序） | 读取的字段 |
|---|---|---|
| `tripo_studio` · Tripo Studio | `tripo.studio.account`（本机浏览器）→ `tripo.server.account`（服务器浏览器） | 页头 `credits` |
| `xyq` · 小云雀 / Pippit | `pippit.cli.credit_balance`（官方 CLI，不驱动浏览器）→ `xyq.web.account`（网站） | `total_remain_amount` 字符串 / 页头 `credits` |
| `higgsfield` · Higgsfield | `higgsfield.subscription.account`（官方 CLI） | `credits`、`subscription_plan_type` |

- 可用 = 已安装、已启用、command adapter、`paid:false`、权限只含 `execute_code`、没有凭证
  （`credential` 与 `command.credential_env` 为空），并保持下表审查过的命令：固定的可执行别名，以及完全相同的
  `command`（只读 argv 含审查过的 pin / bundle 摘要、`output:"json"`、`timeout:60`，没有其他字段）。
  格式正确但不是审查值的 pin、bundle 或命名空间组合一律拒绝，同 id 的被替换定义不能借刷新消费、写入、
  读取凭证或运行别的命令。没有可用来源时报告 `not_installed`，不算失败。
- 审查值从哪里来：Tripo 的账户 pin 取自随包发布的 `src/agent_tool_maker/data/tripo_server/index.json`（`account` 项
  的 argv），服务器来源另要求 `--bundle` 等于 `studio_runtime.bundle_digest()`；`xyq.web.account` 只接受两个会生成它
  的命名空间的 pin（`scripts/build_xyq_web.py` 的 `xyq-web` 与 `scripts/build_xyq_runtime.py` 的 `xyq-media`），
  作为常量保存在 `credits.py`，契约测试从适配器源文件重新计算，漂移即在 CI 失败。

| 来源 | 可执行别名 | 只读 argv |
|---|---|---|
| `tripo.studio.account` | `opencliapp` | `__opencli_shim tripo-studio account --pin <index.json 账户 pin> -f json` |
| `tripo.server.account` | `atm` | `--home <本 ATM home> studio adapter --bundle <bundle_digest()> account --pin <index.json 账户 pin> -f json` |
| `xyq.web.account` | `opencliapp` | `__opencli_shim xyq-web account --pin <xyq-web pin> -f json` 或 `__opencli_shim xyq-media account --pin <xyq-media pin> -f json` |
| `pippit.cli.credit_balance` | `xyq` | `get-credit-balance` |
| `higgsfield.subscription.account` | `higgsfield` | `account status --json` |

## 刷新只由 owner 发起

- 查看（`GET /api/credits`、总览、`atm credits`）只读本机缓存（并清理崩溃遗留的原始输出，见下文），不运行工具、不访问供应商；
  没有后台轮询，打开页面不刷新。
- `atm credits refresh [PROVIDER ...]`（默认全部提供方）与网页“刷新 / 全部刷新”运行来源一次：
  每次新的 request key `credits-<provider>-<uuid4>`、`grants=["execute_code"]`、不允许付费，并绑定已检查的定义摘要。
  网站来源会驱动 owner 已登录的浏览器，所以 Agent 只在 owner 要求时刷新。
- `atm credits refresh` 自行为这些固定只读来源授予 `execute_code`（无需 `--allow-code`）。因此便利模式下的 Agent
  也能运行它；SKILL 要求 Agent 只在 owner 要求时刷新。严格客户端配置（`--client` / `--client-profile`）拒绝整个
  `atm credits` 命令（`operation_denied`），不会退回直接执行。
- 工作目录：每次新建 0700 私有临时目录，结束即删除。它不在 ATM home 内，因为 Tripo 服务器运行时拒绝位于其状态目录内的工作区。
- 网页刷新在请求线程内同步运行（工具自身超时），不持有管理台全局锁。
- 每个提供方一个跨进程租约：`<ATM home>/locks/credits-<provider>.lock`（目录 0700、文件 0600）上的
  `flock(LOCK_EX|LOCK_NB)`。被其他线程或进程（另一个 CLI、管理台）持有时立即返回 `refresh_in_progress`
  （网页为 HTTP 409，与其他状态冲突相同），不运行工具；持有进程退出即释放。
  锁文件以 `O_NOFOLLOW|O_NONBLOCK` 打开，必须是只有一个链接的普通文件（`S_ISREG` 且 `st_nlink == 1`）才会 `fchmod`；
  符号链接、硬链接与 FIFO 一律 `unsafe_path`，不改动其他文件的权限，也不运行工具。
- 网页把所有额度刷新放进同一个队列逐个执行（网站来源共用已登录的浏览器），包括“全部刷新”和单张卡片的“刷新”。
- CLI 退出码：所有请求的刷新成功或为 `not_installed` 时为 0，任一失败为 2；未知提供方在运行任何工具前报错。
  `atm credits refresh A B C` 逐个刷新：某个提供方的错误（包括 `refresh_in_progress`）记为该行
  `refresh:"error"` 与 `error.code`，其余提供方照常刷新，最后以 2 退出。

## 保存什么，不保存什么

- 本机设置 `credits:<provider>`：`provider`、`status`（`ok`/`error`）、`credits`、`plan`、`unit:"credits"`、`source`、`checked_at`、`last_ok_at`、`error:{code,message}|null`。
  失败时保留上次成功的 `credits`/`plan`/`last_ok_at`，只更新 `status`、`error`、`checked_at`。
- 读不出数字（缺字段、非数字、负数、NaN/Infinity、布尔值、超过 10^15）记为 `credits_unreadable`，绝不当作 0；
  整数先比较范围再做任何浮点运算，400 位的整数不会溢出。Pippit 的 `"0"` 是真实的 0；`-0.0` 记为 `0.0`。
- 不保存邮箱、用户 ID 或原始输出：刷新 job 完成后清空 `result` 与 `artifacts`（`raw_output_discarded`），临时目录删除。错误信息只含 ATM 自己的代码与说明。
- 刷新 job：工具是上表固定来源之一，且 request key 为 `credits-<provider>-<32 位小写十六进制>`。任何 job 读取方
  （`atm jobs list/get`、`public_job`、管理台任务视图）都不返回刷新 job 的 `result` 与 `artifacts`（管理台 `artifact_count` 为 0），
  崩溃遗留的也一样。用户自己的 job（如 `credits-mytask`）不受影响。
- 崩溃窗口清理：每次刷新运行前与构建 payload（含查看）时，仍带 `result`/`artifacts`、尚未 `raw_output_discarded`
  的刷新 job（已清理的行在 SQL 中跳过）清空记录，并删除其工作区，前提是它是 `tempfile.gettempdir()` 下直接一层、
  名为 `atm-credits-*`、属于本用户的真实目录（`lstat`，不是符号链接）；其中的 artifact 文件随之删除。否则文件保留原处，
  记录写明 `raw_output_files:"left_in_place"`（删除成功为 `"removed"`）。正常刷新先删工作区再清记录，
  因此两步之间崩溃留下的记录会在下次查看或刷新时清理。
- 这些设置不是 `sync:*` 记录，不进入加密同步包。

## 续期日由 owner 设置

- 目前没有任何来源提供续期日期，ATM 不解析、不猜测。owner 用 `atm credits cycle PROVIDER --day N`（1–31）/ `--clear` 或网页“设置续期日”保存 `credits_cycle:<provider>` = `{day}`。
- 下次续期 = 今天或之后第一个该日；短月份取月末（31 日在二月为 28/29 日）。
  payload 为 `next_cycle: {date: "YYYY-MM-DD", source: "owner"}`，未设置为 `null`；保留 `source` 以便将来接入供应商日期而不改界面。

## 接口

- CLI：`atm credits`、`atm credits refresh [PROVIDER ...]`、`atm credits cycle PROVIDER --day N | --clear`；仅输出 JSON，不含秘密。
- HTTP：`GET /api/credits` → `{providers:[{provider,label,brand,billing,sources,installed,source,source_kind,status,credits,plan,unit,checked_at,last_ok_at,error,next_cycle,cycle_day,next_source,next_source_kind,next_executable,bound}]}`；
  `POST /api/credits/refresh {provider}`、`POST /api/credits/cycle {provider, day|null}` 返回更新后的记录。
  写入与其他 POST 一样经过 bearer、精确 Host/Origin、JSON 与长度检查。`/api/overview` 内含同一 `credits`，不增加启动请求。
- `source`/`source_kind` 是已存值的来源；新增的 `next_source`/`next_source_kind`/`next_executable` 是下一次刷新会运行的来源
  及其可执行别名（没有则为 `null`），`bound` 表示该别名是否已用 `atm cli bind` 绑定。未绑定时刷新会得到 `cli_not_configured`，
  网页不显示“刷新”，只提示 `atm cli bind <别名> <path>`。
- `status` 在没有记录时为 `not_read`（有来源）或 `not_installed`；刷新结果另带 `refresh: ok|error|not_installed`。

## Pippit 扩展

`examples/extensions/pippit-cli-credit-balance.json`：`pippit-tool-cli get-credit-balance`，JSON 输出，`paid:false`，
只需 `execute_code`，无凭证字段，使用 CLI 自己的登录。可执行别名是 `xyq`：与内置 `xyq.image` / `xyq.video`
相同的已审查 `pippit-tool-cli` 绑定，已绑定过就不必再绑。按常规 `atm make validate` → `atm make install --approve SHA`
安装；尚未绑定时 `atm cli bind xyq /absolute/path/to/pippit-tool-cli`。

## 测试

- `tests/test_subscription_credits.py`：提取器（Higgsfield 邮箱丢弃、Pippit 字符串与 `"0"`、缺失/非数字/负数/布尔/超大值）、续期日期计算、
  可用来源规则（付费、写入、凭证、同 id 不同别名、argv、pin、bundle、output 或 timeout 均拒绝且不运行；两个 XYQ pin 与 Tripo pin 的契约重算）、`next_source`/`bound`、经 Router 与假子进程刷新三家提供方、
  新 request key、失败保留上次值、崩溃遗留输出清理（job 完成后崩溃：记录、工作区与 artifact 文件都清理，job 列表不含结果；
  无法确认的工作区保留并记录；只认刷新 job 的 key）、另一进程持有租约、锁路径为符号链接/硬链接/FIFO 时拒绝、
  `-0.0`、CLI 与退出码（某个提供方租约被占时继续其余并以 2 退出）、严格客户端拒绝、网页鉴权/Origin/409、不阻塞管理台、同步排除、扩展安装。
- `tests/test_credits_browser.py`（browser）：原生 Chromium 渲染面板、刷新忙碌状态与焦点保留、所有刷新串行、错误短标签与说明、
  未安装的紧凑卡片、未绑定提示、对话框内校验续期日、设置与清除续期日。
- 均为隔离状态与假程序；真实账户、真实已登录浏览器与供应商输出未验收。

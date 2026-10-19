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

- 可用 = 已安装、已启用、command adapter、`paid:false`、权限只含 `execute_code`。其余一律拒绝，
  被替换的定义也不能借刷新消费或写入。没有可用来源时报告 `not_installed`，不算失败。

## 刷新只由 owner 发起

- 查看（`GET /api/credits`、总览、`atm credits`）只读本机缓存，不运行工具、不访问供应商；没有后台轮询，打开页面不刷新。
- `atm credits refresh [PROVIDER ...]`（默认全部提供方）与网页“刷新 / 全部刷新”运行来源一次：
  每次新的 request key `credits-<provider>-<uuid4>`、`grants=["execute_code"]`、不允许付费，并绑定已检查的定义摘要。
  网站来源会驱动 owner 已登录的浏览器，所以 Agent 只在 owner 要求时刷新。
- 工作目录：每次新建 0700 私有临时目录，结束即删除。它不在 ATM home 内，因为 Tripo 服务器运行时拒绝位于其状态目录内的工作区。
- 网页刷新在请求线程内同步运行（工具自身超时），不持有管理台全局锁；同一提供方并发刷新返回 `refresh_in_progress`；“全部刷新”逐个执行。
- CLI 退出码：所有请求的刷新成功或为 `not_installed` 时为 0，任一失败为 2；未知提供方在运行任何工具前报错。

## 保存什么，不保存什么

- 本机设置 `credits:<provider>`：`provider`、`status`（`ok`/`error`）、`credits`、`plan`、`unit:"credits"`、`source`、`checked_at`、`last_ok_at`、`error:{code,message}|null`。
  失败时保留上次成功的 `credits`/`plan`/`last_ok_at`，只更新 `status`、`error`、`checked_at`。
- 读不出数字（缺字段、非数字、负数、NaN/Infinity、布尔值）记为 `credits_unreadable`，绝不当作 0；Pippit 的 `"0"` 是真实的 0。
- 不保存邮箱、用户 ID 或原始输出：刷新 job 完成后清空 `result` 与 `artifacts`（`raw_output_discarded`），临时目录删除。错误信息只含 ATM 自己的代码与说明。
- 这些设置不是 `sync:*` 记录，不进入加密同步包。

## 续期日由 owner 设置

- 目前没有任何来源提供续期日期，ATM 不解析、不猜测。owner 用 `atm credits cycle PROVIDER --day N`（1–31）/ `--clear` 或网页“设置续期日”保存 `credits_cycle:<provider>` = `{day}`。
- 下次续期 = 今天或之后第一个该日；短月份取月末（31 日在二月为 28/29 日）。
  payload 为 `next_cycle: {date: "YYYY-MM-DD", source: "owner"}`，未设置为 `null`；保留 `source` 以便将来接入供应商日期而不改界面。

## 接口

- CLI：`atm credits`、`atm credits refresh [PROVIDER ...]`、`atm credits cycle PROVIDER --day N | --clear`；仅输出 JSON，不含秘密。
- HTTP：`GET /api/credits` → `{providers:[{provider,label,brand,billing,sources,installed,source,source_kind,status,credits,plan,unit,checked_at,last_ok_at,error,next_cycle,cycle_day}]}`；
  `POST /api/credits/refresh {provider}`、`POST /api/credits/cycle {provider, day|null}` 返回更新后的记录。
  写入与其他 POST 一样经过 bearer、精确 Host/Origin、JSON 与长度检查。`/api/overview` 内含同一 `credits`，不增加启动请求。
- `status` 在没有记录时为 `not_read`（有来源）或 `not_installed`；刷新结果另带 `refresh: ok|error|not_installed`。

## Pippit 扩展

`examples/extensions/pippit-cli-credit-balance.json`：`pippit-tool-cli get-credit-balance`，JSON 输出，`paid:false`，
只需 `execute_code`，无凭证字段，使用 CLI 自己的登录。按常规 `atm make validate` → `atm make install --approve SHA`
→ `atm cli bind pippit-tool-cli /absolute/path` 安装与绑定。

## 测试

- `tests/test_subscription_credits.py`：提取器（Higgsfield 邮箱丢弃、Pippit 字符串与 `"0"`、缺失/非数字/负数/布尔）、续期日期计算、
  可用来源规则、经 Router 与假子进程刷新三家提供方、新 request key、失败保留上次值、CLI 与退出码、网页鉴权/Origin、不阻塞管理台、同步排除、扩展安装。
- `tests/test_credits_browser.py`（browser）：原生 Chromium 渲染面板、刷新忙碌状态、设置与清除续期日。
- 均为隔离状态与假程序；真实账户、真实已登录浏览器与供应商输出未验收。

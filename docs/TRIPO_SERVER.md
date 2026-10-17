# Tripo 独立服务器浏览器

## 契约

服务器 Agent → 服务器 ATM → 服务器 Chromium → Tripo Studio。
没有本机中继、OpenCLIApp、Cookie 同步或远程任意命令接口。浏览器自己维护登录。
本机只在首次登录/验证/登录失效时临时观看并操作服务器上的浏览器；关闭查看器后，
浏览器及后台执行继续运行。登录保存不等于供应商永不要求重新认证。

这是现有 31 个 DOM 工具的独立执行后端，不是新增 31 项供应商验收。
本机 delivery 阶段的 texture_quote、texture、operation_status 尚未加入服务器分派；
服务器上的 Texture 仍走已审阅的 workspace_prepare / workspace_submit。
`tripo.server.*` 使用原 `tripo.studio.*` 的 schema、权限、预算和付费回执，旧定义保持原样。
仍使用 Studio 订阅额度；与开发者 API 独立。登录状态不进入 ATM Key 同步。

## Agent 准备，human 只登录

1. 在服务器创建独立 OS 用户/ATM 状态，审阅并安装本项目 `.[secure,server]`、Node.js、
   Playwright 支持的 Chromium 及 Linux 依赖。安装浏览器按
   [Playwright 官方说明](https://playwright.dev/python/docs/browsers)，不是下载同名未知包。
   有现存 vault 时保留它；项目输出与 ATM 状态目录及其父目录分开。
2. Linux 推荐 Xvfb + 完整 Chromium：Agent 安装经审阅的系统 `xvfb`、`x11vnc`。
   `atm studio serve --node /absolute/node --virtual-display :99` 启动专属虚拟显示。
   无实体屏幕，但浏览器始终运行，不在登录后更换另一份 profile。
3. Agent 执行 `atm studio install`，核对 bundle SHA256，随后使用相同 SHA
   `--approve SHA --apply --atm-executable /absolute/atm`。只安装服务器命名空间。
   重复相同安装复用，定义变化明确报错，后续通过已有 CAS 审阅更新流程处理。
4. Agent 执行 `atm studio login --ttl 600`，准备 SSH 本地端口转发与本机 VNC 查看器。
   人在**服务器浏览器**完成 Tripo 官网登录/验证，不把密码、授权链接或 Key 发到聊天。
   `atm studio login-close` 关闭查看器；600 秒固定到期也会自动关闭，不静默续期。
5. Agent 查询服务器 `account`，验证 login/credits，再执行任务。供应商生成/上传/导出
   继续遵守原工具各自的确认门槛，不复用此前付费批准。

人不需要手敲安装、绑定、端口和工具授权清单。SSH/VNC 只用于临时登录，日常执行
不连接本机。服务器重启由自己的服务管理器恢复浏览器，未完成任务不会自动重发。

## 工程/部署命令（由 Agent 执行）

```sh
atm studio status
atm studio run account --input account.json --workspace /srv/tripo-project \
  --request-key account-fresh-001 --allow-code
```

相同 request-key 复用旧 job，不当作最新积分查询。新的只读查询使用新的 key。
写入/表单工具需要 `--allow-write`，付费工具另外需要 `--allow-paid` 及 schema 中
绑定的明确内容、source、quote、credit ceiling 和 human confirmation。
也可使用普通 `atm run tripo.server.OP`；严格 broker scope 保持严格。

**付费与确认工具只走 Router。** generate、image_generate、retopo、rig、workspace_submit
（付费）以及 schema 含 const `human_confirmed` 的 export、image_quote，只能经 `atm studio run`、
`atm run` 或 broker 执行。Router 通过 `--allow-paid`、权限与 broker scope 并认领 job/request-key 后，
签发一次性 ticket（60 秒），绑定该 job、确切 argv、项目目录和 bundle；服务器在打开表单或点击前
原子消费它。隐藏的 `atm studio adapter` 只供已安装定义调用：直接运行它或直接连接 socket
仍可执行只读及未确认的表单工具（其 `--allow-write` 仍只在 Router 路径检查），
但上述工具一律报 `router_ticket_required`（`outcome_uncertain: false`），
没有提交、没有重试。`--confirm` 对应的 const 确认因此只在 Router 已按原 schema 校验真实输入后成立。

`deploy/atm-tripo-studio.service.in` 是 systemd **用户服务模板**。Agent 替换绝对路径，
先本机前台验证再安装。需要断开 SSH 后运行/开机恢复时，按服务器管理员策略设置
用户服务生命周期；不自动提权、启用 linger 或安装服务。浏览器 sandbox 保持启用，
root 容器或缺少 sandbox 依赖明确失败，不加 `--no-sandbox` 兜底。

Headless smoke：`atm studio serve --node /absolute/node --chromium /absolute/chromium`。
此模式验证后台执行；远端人类登录入口使用上面的专属虚拟显示路线。

## 状态与边界

- `studio status` 是运行时状态，不代表供应商已登录；通过 `account` 实际读取网页。
- Unix socket 0600、状态/profile 目录 0700、同 UID 校验；没有 TCP 工具 API。
  只信任本用户代码，不宣称隔离恶意同用户程序。
- Router ticket 只把哈希写入本地 job 记录，secret 只进入该次 adapter 进程环境；
  消费、过期、job 已结束或复用 request-key 后都不能再用。它防止 Agent 绕过
  `--allow-paid`、job 记录或 broker scope，但仍属同 UID 信任：不防御能改写 ATM 状态
  或读取本用户进程环境的恶意程序。Router 与 `studio serve` 须使用同一 `--home`。
- 每次操作绑定包含 Python 驱动、Node dispatcher 和 20 个原适配源文件的 bundle 摘要
  （含随源码闭包打包、但不分派的 2 份 delivery 源）。
  一次只运行一个操作；并发报 busy，不排队或重试副作用。
- 原 paid lock、pre-click receipt、request-key、报价/Private/预算检查不变。
  导出与上传限制在确切项目，不触碰浏览器认证文件。RPC 的 CDP 仅 DOM 上传及原生输入。
- 临时 VNC 只监听 127.0.0.1，通过 SSH 使用；专属 Xvfb 配置私有 Xauthority。
  无公网端口、公开调试端点或网页密码表单。VNC 信任已登录的本机用户，不作多租户隔离。
- profile 仅由浏览器打开。Agent 不读取、导出、复制 Cookies、Token 或 profile 内容。
  停机保留 profile、回执、旧 socket。没有自动永久删除/清理。
- 登录/验证码/站点错误/未知提交明确失败。普通 ATM job 的 CLI 失败可能报告
  `cli_failed`/`submission_unknown`；直接 `studio adapter`（非 Router 专属工具）的 JSON 及保留回执区分根因，
  不因进程或浏览器健康伪造供应商成功。

## 本机验收与待验收

当前测试使用独立 Chrome、真实 Python/Node/Unix socket/ATM 子进程，HTTP 全部拦截到
假 Tripo 页面。假登录在测试浏览器 UI 建立；持久性通过重启后读取 DOM 验证，不读认证文件。
原真实 Chrome 登录、vault、积分和已安装工具均保持原状。

2026-10-04 本机结果（工作区源码，尚未发布）：

- `tests/test_studio_server.py` **43 passed**：37 项协议/定义/权限/路径及模拟查看器测试，
  6 项真实 Chromium 集成。31 定义与原 schema/权限逐项一致，18 份适配器字节一致。
- 真实 ATM/Node 子进程的新会话与稳定 request-key 复用；浏览器退出重启后保留假登录；
  缺登录明确失败；独占 profile、错误 bundle、未授权 RPC 和忙状态明确拒绝。
- 假付费路径：未授 paid 权限时没有提交；批准后只点击一次；重复 key 复用结果，
  假 DOM 余额从 99 到 59。不是供应商扣费/模型生成验收。
- 原生驱动：精确/nth 选择器、焦点/键盘/hover/滚动、ARIA switch 与 checkbox、
  CDP 上传项目夹具和匹配的已完成假下载。覆盖基础传输，不等于真实 GLB 导出。
- 图片生成保留原 OpenCLI wrapper 的 `--image-sha` → `image_sha` 映射；有效参数
  到达缺 draft 门槛，不错误拒绝 hash，也不点击 Generate。
- 原 Node 适配器回归 **237 passed / 0 skipped**。wheel 构建成功并逐字节核对
  23 份驱动/CLI/包内数据文件；只有 `atm` 一个安装入口。
- 完整非浏览器回归 **860 passed / 2 skipped / 17 deselected**；两项跳过为
  本机缺少 pandoc，17 项浏览器测试未包含在该次运行。服务器的 6 项浏览器集成
  已在上述专项独立运行，不把剩余浏览器测试当成已验收。

专项 JUnit：`/private/tmp/atm-studio-server-final-20261004-o.xml`。
非浏览器 JUnit：`/private/tmp/atm-studio-server-regression-20261004-n.xml`。
wheel 核对：`/private/tmp/atm-studio-server-wheel-readback-20261004.json`。
临时 VNC 的 TTL、loopback、Xauthority 和关闭后保留浏览器为**模拟协议测试**，
没有把 macOS 测试当成 Linux 原生查看器验收。

2026-10-17 Router ticket 补丁（同一假 Tripo 夹具，非供应商验收）：`tests/test_studio_server.py`
**54 passed / 0 skipped**（48 项协议/定义/权限 + 6 项真实 Chromium）。直接运行已安装的
`atm studio adapter generate …`（无 ticket 或伪造 ticket）与直接 socket `run` 均报
`router_ticket_required`，无付费 ledger；`atm studio run --allow-paid` 消费自身 ticket 并只提交一次
（假 DOM 余额 99→59）。完整回归 **1469 passed / 2 skipped**（两项为本机缺少 pandoc）。

**仍待用户服务器验收**：Linux Xvfb/x11vnc 生命周期和 SSH 断开后的服务运行；
真实 Tripo 登录/验证码、3D/WebGL、全部 DOM 操作、上传/生成/下载和机器重启。
原本机供应商验收不会自动变成服务器验收。

## 开发真源

DOM 源码只在 `examples/opencli/tripo-studio/` 维护。
`scripts/build_tripo_server.py` 确定性生成包内快照/index；测试校验全部 20 文件字节相同，
不是手工维护第二份适配器。driver/protocol 在 `studio_runtime.py`，CLI 在 `studio_cli.py`。
Playwright 使用[持久上下文](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)，
退出/重启不转储认证状态。只新增 `atm studio` 子命令，没有其他安装命令名。

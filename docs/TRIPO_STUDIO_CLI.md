# Tripo Studio 网页 CLI

当前完整覆盖审计、未接入入口及 DOM 驱动二次调整见 [覆盖报告](TRIPO_STUDIO_COVERAGE.md)。

## 范围与执行方式

这是网页 DOM 适配器，不是开发者 API。Studio 与 API 的积分独立：
[Tripo 官方说明](https://www.tripo3d.ai/help/api-plugins/tripo-studiotripo-api)。
不修改现有 `tripo.generate`，也不导出 Cookie、Token、Chrome profile 或读取认证文件。
浏览器自己维护登录；失效后由人完成官方登录，不承诺通用自动续期。

路线：主 Agent 观察真实 DOM → `examples/opencli/tripo-studio/` 专用适配器 →
`scripts/build_tripo_studio.py` → 固定 manifest / Python CLI / 哈希锁 → ATM →
已安装的 OpenCLIApp 1.8.6 + Chrome 扩展 1.0.24 → Studio 页面。

选择 `UI_SELECTOR` / visible-ui 契约。无内部端点、请求签名重放、网络抓取或
PAGE_FETCH。标题、积分和卡片来自实际观察的 DOM。CSS 与英文界面有漂移风险，
页面错误、缺登录、未加载和契约变化分别失败；未观察到的空列表不伪造成功。

## 已提供工具

| ATM 工具 | 权限 | 实际行为 |
|---|---|---|
| `tripo.studio.account` | code | 登录状态、页头积分；无身份信息 |
| `tripo.studio.assets` | code | 已加载模型卡片，limit 1–100；不自动翻页 |
| `tripo.studio.quote` | code + write | 必要时切文字模式，读取当前报价和设置；不填词、不提交 |
| `tripo.studio.generate` | code + write + paid | 明确确认后，一次私密文字生成；返回新资产页 ID |
| `tripo.studio.assets_all` | code | 自动滚动模型资产，最多 1000 卡片 / 50 轮，去重且标明覆盖范围 |
| `tripo.studio.asset_resolve` | code | 打开指定预览卡片，再点 Edit in Workspace，取得实际资产 UUID |
| `tripo.studio.asset` | code | 模型状态、Faces/Vertices、Export 就绪；可等待 0–120 秒 |
| `tripo.studio.retopo_quote` | code + write | 准备 Quad/Triangle、面数、Smart Mesh，回读报价；不提交 |
| `tripo.studio.retopo` | code + write + paid | 按源资产、报价与预算，单次重拓扑 |
| `tripo.studio.rig_quote` | code + write | 准备 Humanoid/Other、指定骨架，保留姿势警告；不提交 |
| `tripo.studio.rig` | code + write + paid | 核对前置条件后，单次 Auto Rig |
| `tripo.studio.image_quote` | code + write | 明确批准后上传一张项目图片到空的 Private 面板，读取报价；不生成 |
| `tripo.studio.image_generate` | code + write + paid | 使用未变化的已上传图片/设置/报价，单次图片生成 |
| `tripo.studio.export_quote` | code + write | 打开已完成模型的 GLB 导出弹窗，回读格式/纹理；不下载 |
| `tripo.studio.export` | code + write | 单次下载订阅模型 GLB，检查完整文件并返回项目内产物 |

只读资产输出 `coverage=currently_loaded_cards`、`all_assets=false`。
`preview_task_id` 从可见缩略图路径取得，与资产详情 ID 不同；`task_status=null`。
不返回图片签名 URL、邮箱、Cookie 或 Token。非英文/其他缩略图布局需要重新观察。
扩展翻页器支持本次实际观察到的 mesh、gray mesh、part、wireframe 四种缩略图。
`assets_all` 选择 Model / My Assets / All，滚动页面实际的内部网格页尾，而非 window。
只有明确的 UI 结束提示才返回 `all_assets=true`；达到限制或安静的页尾分别返回
partial 和 stop_reason，不用推测总量。该范围是模型卡片，不含 Image/Videos 等分栏。
翻页每轮验证 Model / My Assets / All 的实际选中状态及卡片/预览 ID 对齐；
`scope` 和 `coverage_evidence` 明示范围及页尾证据，`authoritative_total=null`。

生成包位于 `generated/tripo-studio/{account,assets,quote,generate}/`，每包含
`tool.py`、manifest、输入示例、README 与 bundle-lock。只需要 Python 标准库和
已安装 ATM；浏览器依赖不内嵌。唯一由本项目安装的命令仍是 `atm`。
本次新增 11 包在 `generated/tripo-studio-extended/`。适配器摘要覆盖按固定顺序的
8 个源码文件；更新用 CAS 校验旧定义、批准新摘要，并保留定义历史。原来的
4 个包与摘要保持不变。

## 人的体验

Agent 检查 bridge doctor、已注册定义、源文件摘要和真实可执行文件绑定，
直接调用已安装工具。需要登录时仅打开本地官网交给人；不把安装/授权命令清单
交给人，不读取 profile/token 文件，不改浏览器策略。

付费前向人展示实际提示词、模型、Private、报价和积分上限。
获得本次确认后才设置 `human_confirmed=true` 并给 ATM paid/write/code 权限。
代码里有预算字段不代表人的付款确认；`--confirm` 也不是隔离机制。

生成输入：prompt（1–1000 字符）、max_credits（1–10000 整数）、quote_sha256、
request_key、human_confirmed（必须 true）。输入里的 request_key 与 ATM 调用
使用同一个稳定值。未完成输入的 `{}` 示例不会产生收费调用。

## 付费状态与证据边界

- 先读取报价、保留已有草稿，核对 Private/模型/parts/8K；填入明确批准的文字后
  再检查提示词、按钮、报价指纹和积分上限。
- 不重载已打开表单；从站点的可见 Workspace 链接正常导航。曾观察到冷打开路由
  呈现临时错误页；错误不算报价成功，也不隐式重发 Generate。
- `.atm/tripo-studio-paid/` 只存非秘密本地回执。在唯一收费点击前排他创建并
  fsync `dispatch_claimed` 回执；同项目 active.lock 阻止并发。完成锁用 rename
  留档，不永久删除。进程崩溃/未知结果保留回执与 active.lock，人工对账后处理。
- 同 request_key / 相同输入复用既有 submitted 回执，不进行导航、填词或点击；
  输入不同报冲突。结果未知时新 key 也被 active.lock 拦住，不自作重试。
- `submitted` 仅表示观察到新资产路由。ATM 外层 `completed` 是 CLI/JSON 完成，
  **不是生成模型完成**，也没有自动导出。
- 上限是当前可见报价的客户端检查，不是供应商服务端计费承诺；跨项目/用户
  手动同时操作不由本项目 lock 隔离。信任同系统用户的代码，不声称恶意代码隔离。

扩展的图片上传、重拓扑、绑骨和导出复用同一个 active.lock；不跨工具绕开
未知任务。已成功的上传报价/导出也记录回执，相同 key 复用，不重新上传/下载。

## 扩展调用契约

- **资产：**先 `assets_all` 取得 preview_task_id，`asset_resolve` 通过原生详情页
  取得 asset_id，后续工具只接受实际 UUID。导航保留当前资产，跨资产使用可见
  Workspace/侧栏链接；老资产未在侧栏时先 resolve。已复现 Studio 冷打开 UUID
  路由显示服务端错误，错误回执保留，不当作模型就绪。
- **重拓扑：**quote 的 settings 仅接受 topology、polygon_count、smart_mesh。
  面数整数 500–200000，另受当时 UI slider 的实际上下限约束。
- **绑骨：**rigging_type 为 Humanoid/Other；观察到的 skeleton 为 ActorCore、
  Mixamo、UE5 Mannequin、VRM 1.0 Humanoid、Unity Humanoid Compatible。
  前置条件、禁用按钮和 T/A-pose 警告保留。蓝色立方体仅用于报价，不证明人形绑骨质量。
- **图片：**image_quote 的 image 是明确的项目内 PNG/JPEG/WebP，最多 20MiB，
  拒绝符号链接、范围外路径和错误文件头；上传需要本次文件/目的地的明确确认。
  输出 image_sha256 和绑定预览/文件元数据/设置的 quote_sha256。图片生成另需
  max_credits 和 human_confirmed；保留原页面草稿，不重新上传。上传报价不表示
  已批准 Generate，不沿用上一笔文字生成的额度。
  文件输入通过公开的 Chrome CDP DOM.getDocument / DOM.querySelector 预检，
  claim 后只调用一次 DOM.setFileInputFiles；不用 JS 构造文件或供应商隐藏接口。
  这是原生 DOM 交互，不是开发者 API；未支持 CDP 的 backend 在上传前显式失败。
- **执行：**retopo/rig/image_generate 输入包含 quote_sha256、max_credits、
  request_key、human_confirmed=true；前两者另含 asset_id，图片另含 image_sha256。
  同一稳定 key 同时传给生成 CLI 的 --request-key 和输入字段。变化的资产、
  设置、图片或价格在收费点击前失败；唯一点击前 fsync claim，未知结果留锁。
- **导出：**当前仅 GLB。quote 核对完成模型、格式和纹理；export 的输入包含
  asset_id、quote_sha256、request_key、human_confirmed=true。当前订阅弹窗观察为
  无积分标价，出现新标价即契约失败。先建立唯一文件名的下载监听，再唯一点击，
  只接收匹配且 complete 的文件。检查 GLB v2 魔数、总长度、JSON chunk 与 mesh
  primitives，排他写入输出 model.glb，不覆盖已有文件，不返回签名下载 URL。
  相同 key 可从已验证回执复制产物到 ATM 的输出目录；几何质量与 Unreal 导入另验收。

扩展 JSON 在 OpenCLI 层为 `[{"result": {...}}]`，ATM 外层 job.data.result 保留
该结构。外层 completed 表示子进程/协议已完成，业务状态仍以内部 result 为准。

## 重新生成（Agent/开发者）

```sh
PYTHONPATH=src python scripts/build_tripo_studio.py --stage all --out NEW_DIRECTORY
node --test tests/tripo_studio_core.test.mjs tests/tripo_studio_paid.test.mjs tests/tripo_studio_extended.test.mjs
PYTHONPATH=src python -m pytest tests/test_tripo_studio_cli.py tests/test_tripo_studio_extended.py -q
```

先审阅源文件再安装适配器，校验 normalized manifest SHA，再安装/更新 ATM
定义。绑定的是 OpenCLIApp 的实际可执行文件（不是只校验 shell shim），
manifest 额外固定适配器文件摘要。升级需要重新审阅。哈希是完整性检查，不是
作者签名；浏览器扩展与依赖仍属被信任程序。

编译器排他保留输出目录，逐文件原子写入，最后写完整性锁。失败目录保留供诊断，
缺锁的半成品包被 check-bundle 拦住；不调用永久删除清理。

## 本地验收 2026-10-02

- 只读真实 CLI → 已安装 ATM → Chrome：account 已登录、20,155 积分；assets
  返回 20 个当前已加载卡片。未读取 Key 或导出登录态。
- 真实报价：H3.1 – Best Quality、Private、parts=false、8K=false、40 积分。
- 人明确批准单个蓝色立方体，最多 40 积分一次；生成 CLI 实际提交成功，
  资产 ID `6e6198e0-0d74-4522-832f-46a5d49e1d3d`。
- 原生浏览器回读余额 20,115，差额 40；模型已在 3D 视图显示，Export 控件
  可用，Faces 11,550 / Vertices 6,701。已保存 `paid-result.png` 验收截图；未导出。
  这是本次人工界面验收，生成 CLI 本身仍只返回 submitted，不自动等待模型完成。
- 自动化：24 个 Node 合成测试、7 个 Python 合同/真实假子进程测试通过。
  工厂/HTTP/子进程回归 55 passed。完整非浏览器回归 776 passed、2 skipped
  （未安装 pandoc）、11 deselected；浏览器适配器另做上述真实 Chrome 路径验收。
- 四个生成包均通过完整性检查，已安装定义和适配器源码逐项一致；已有
  Claude/Codex 用户 Skill 已同步新工具说明，原运行时路径不变，旧版备份保留。
- 分支 `feat/tripo-studio-cli-20261002`，未提交/推送/发布；保留既有 OAuth/锁定修复。

## 扩展验收 2026-10-03

- 新分支 `feat/tripo-studio-full-cli-20261003` 保留已有未提交改动，新增 11 个工具，
  合计 15 个适配器。真实 OpenCLI validate：15 commands、0 errors、0 warnings。
- 原蓝色立方体模型已完成：Faces 11550、Vertices 6701，Export 可用。
- 真实重拓扑报价：Quad、Smart Mesh、40 积分；真实绑骨报价：Humanoid、
  UE5 Mannequin、20 积分，T/A-pose 警告保留；未点击这两个付费按钮。
  生成 CLI → ATM → Chrome 另验证面数设置为 500 的回读，以及模型 20 秒有界等待。
- 真实 GLB/4k Current 导出：0 积分，5085444 bytes、1 mesh，SHA256
  `310c9ff3f13c357abd97ddf3d1c8873bfc34a068075b953d94b9ec91bebc0ea4`。
  项目产物 `.atm/tripo-blue-cube-export.glb`，同一稳定 key 保留并复用，余额仍为 20115。
- 原生自动滚动读到 400 个模型卡片、21 轮；安静页尾没有权威总量/结束提示，
  返回 partial、all_assets=false，明确不是完整账号资产数证明。
  生成 CLI → ATM 另验证限额 50 卡片 / 3 轮，正确报告 item_limit；原生详情操作
  将预览 UUID `634a9fac-121f-48db-80be-134749ee6b5a` 解析为上述实际蓝色立方体 ID。
  旧的 Assets/UUID 冷导航和异步控件挂载失败回执保留；改为可见 SPA 入口并等待
  唯一语义控件挂载，未通过猜测路由或增加收费重试来修复。
- 人批准仅上传蓝色测试 PNG，image_quote 在 image_upload 阶段返回桥接失败。
  页面没有图片预览，余额 20115，未点击 Generate。**真实上传尚未验收**。
  原未知回执/active.lock 保留，该项目的新上传/付费/导出提交被保护性拦截；
  查询、报价和既有成功结果复用仍可用。已请求核对后仅重试上传一次的明确决定，
  不更换 key 或自行清锁重发。失败路径新增脱敏 failure_type/bridge_error_code，
  无原始错误 URL、登录信息或文件内容。
  不附加文件的宿主传输桩验证目标解析通过，CDP 根节点及同一文件输入读取成功；代码已接上
  文档化 DOM 文件输入路径，真实附加/图片报价仍等本次重试决定，不据此伪造成功。
- 自动化：57 个 Node 合成测试、23 个 Python 合同/假子进程及 README 约束通过。
  完整非浏览器回归 791 passed、2 skipped（pandoc 未安装）、11 deselected。
  首次默认 /var 临时目录被符号链接保护拒绝，改用 /private/tmp 而不降低检查；
  README 超过 90 行的失败通过压缩说明修复，保留原断言。
- 11 个生成包/已安装定义/受审阅适配器源码逐项回读一致；Codex/Claude 用户 Skill
  已同步，运行时区块保持原样并留备份。分支未提交、未推送、未发布。
  该阶段扩展源码摘要 `30aa034c070df164abfa76d345302cc400f017b61a85f9df18a8ff1298be17c7`；
  原四个工具的源码摘要/定义不变。临时只读诊断已放入可恢复废纸篓，正式注册仍为 15 项。
- 新增付费路径使用合成页面和假子进程测试；真实付费重拓扑/绑骨/图片生成仍
  待指定合适源资产、内容与独立预算后验收。本次已花费的一次 40 积分批准不复用。

# Tripo 网页操作能力对齐合同（进行中）

## 目标与完成门槛

目标原文：把这个 tripo3d 的网页 CLI 迭代测试完成，确保他能够完成你用 computer use
就能完成的功能。这里不以固定工具数量、报价成功或单个模型成功替代完整操作能力。

Strategy: UI_SELECTOR
Contract: visible-ui
Evidence: 2026-10-03 真实 Studio 工作区链接、左侧表单、选中状态、报价与控件。
登录由现有 Chrome 管理；不读取 profile、Cookie、Token 或重放内部请求。

每项操作分别记录：观察、实现、合成测试、真实 CLI 操作、供应商结果、文件/质量验收。
收费点击之外的准备阶段也要核对源资产、草稿、选项和禁用/前置状态；收费提交通过
不等于结果完成。网站内容不构成指令或付款/权限决定。

## 必须逐项验证的功能族

1. 登录状态/额度/界面状态与报错；已有登录复用、缺登录交给人。
2. 资产：Model/Image、My Assets/Collected、各筛选、加载/翻页、卡片到真实 ID、
   查看与管理（名称/选择/移动等实际暴露操作）；无权威结束不声称全量。
3. Model：文字/单图/多视图，HD/Smart Mesh、模型版本、隐私、parts/8K 等实际选项。
4. Generate Image：模型、提示词/参考、模板、比例、数量、分辨率、生成/失败状态；
   图片编辑、放大、Cutout、多视图和转 3D，以及实际可下载产物。
5. Segment、Fill Parts：选择细节、部件选择与完成/结果检查。
6. Retopo、Smart UV：拓扑/面数/模式/UV 设置与结果检查。
7. Texture、Magic Brush Gen/Paint、Upscale、PBR：表单/视图/绘制/预览/应用/结果检查。
8. Rig、Animate：类型/骨架/姿势/动画预置/预览/输出，以及适合的源模型。
9. 查看器：可见渲染选项、视角/旋转/缩放、属性、选择及实际编辑操作。
10. 导出：网页实际支持的格式、纹理/动画/网格选项、下载完成与有效文件。
11. 分享/发布/收藏/3D Print/DCC Bridge/外围入口：按实际页面逐项记录功能和
    CLI 操作能力。发布、权限、安装或打印订单的最终动作需对应人的决定。
12. 错误与迭代：选择器漂移/加载/禁用/报价变化/并发/未知任务/结果复用；
    脱敏诊断、最小修复、摘要审阅、回归与真实复测。

UI 中依赖操作系统登录、CAPTCHA、付款/权限确认的人的步骤继续保留；这与
computer use 的交接约束相同，不由 CLI 自动代人批准。该限制不删减上述功能族。

## 当前发现与下一步

- 已有 31 个工具（前 15、工作区 3、资产查询 2、动画/导出选项 4、查看器/层级 5、图片表单 2）及分阶段验收见
  TRIPO_STUDIO_CLI.md；旧未知上传锁保留，不等于 12 功能族完整通过。
- 新观察：Segmentation 默认 Balanced、40 积分；Texture 8K 报价 30；
  Magic Brush Gen 预览 5；Upscale 8K 报价 20；PBR 5。
- Fill Parts 在未分割的立方体上没有提交按钮；Smart UV 的 Unwrap UV 禁用且
  无可见价格；不得推断免费。需要合适的分割/UV 源夹具再测试。
- 已定位零高度链接的真实原因：侧栏子菜单折叠。经原生操作证明先点 Texture
  再进 Edit/Upscale/PBR，先点 Rig 再进 Animate；补齐 CLI 的同样展开路径。
  Animation 面板实际显示 Rig the Model First、Generate 20 禁用，这才是资产前置条件。
- Generate Image 默认 GPT Image 2.5、4 张、80 数值与 Free 14/1000 同时显示，
  无按钮内报价；暂记录未知计费含义，不按文字猜计费并提交。
- 先补全工作区通用观察/语义准备/有报价提交，逐模块与 computer use 对照；
  继续补齐资产图片网格、管理、导出多格式及查看器/绘制等。完成状态逐项更新，
  不把本轮阶段进展标成整体完成。

分支：feat/tripo-ui-parity-20261003，保留既有未提交工作；未提交/推送/发布。

## 本阶段实际完成 2026-10-03

- 已安装 `workspace_inspect`、`workspace_prepare`、`workspace_submit`；总计 18 项。
  旧 15 个包、摘要、权限及原上传未知回执/锁不变；新 3 包逐项回读一致。
- 真实生成 CLI → ATM → Chrome **22 项通过**：一次预览到资产解析，12 模块
  检查，9 条准备/恢复。Segment Simple/Balanced、Upscale 4K/8K、Texture
  4K/8K、PBR 空设置、Magic Brush 测试提示词/0.4 与绑定摘要后清除/恢复0.6。
- 实际动态报价：Upscale 4K=10、8K=20；Texture 4K=20、8K=30；Segment=40、
  PBR=5、Magic Brush Preview=5。Animation=20，当前源显示 Rig the Model First。
  Image/Smart UV/Fill Parts 保持未知报价或前置状态，不推断免费。
- 中途实际失败：首次只读 ID 解析失败；doctor 健康、直接只读解析及后续真实
  CLI 已通过，原因未独立证明，失败回执保留。另一次 Upscale 准备因折叠菜单
  失败，已通过原生父项展开证明根因、增加随机顺序导航回归并真实复测通过。
  不因瞬时失败改认证/网络策略，未重复任何上传或收费请求。
- 自动化 **81 Node / 28 Python 聚焦检查通过**；包含五类付费模块合成测试、
  持久声明在唯一点击前、报价/源/草稿漂移、同 key 复用、旧上传锁跨工具拦截。
  付费合成测试不是供应商真实结果验收。未把先前全工程 791 项写成本轮重跑。
- 页面余额 20115，未扣费；本轮输入测试草稿已按其摘要清除，原源提示词保留。
- 当前工作区源码摘要：
  `18df6607f853c6add97f000d8e781ad14efb38d13e2a24775ae9371604f67607`。
  证据：`/private/tmp/atm-tripo-extended-20261003/workspace-native-acceptance-round3.json`、
  `workspace-r3-result-*.json`、`workspace-node-accepted.log`、`goal-image-card-contract.json`、
  `goal-pbr-approval.png`。临时文件不是永久存储承诺。

## 尚未通过的完成审计

整目标保持 active。以上仅完成工作区表单层的一阶段，功能族 2–11 仍有操作、
供应商完成、下载与质量验收缺口。下一步包含图片资产（无 alt 的图片，单任务
多张需用 task+index 区分，多视图四张为一卡）、管理、查看器/绘制、导出多格式、
图片生成/编辑/多视图、部件/UV、绑骨/动画源夹具，以及相应付费结果。

已向人请求具体下一步：旧“仅蓝色测试图上传未知”锁经核对留档解除但不重试上传，
现有蓝色立方体 PBR 一次最多 5 积分，报价变化停止，不 Share/Feature My Model。
未收到明确决定前保持原锁和未知回执，继续其余观察/本地实现；不把等待决定
扩大为整个目标停工，也不标记目标完成。

## 资产查询阶段 2026-10-03

Strategy: UI_SELECTOR
Contract: visible-ui
Evidence: 真实 Image/All、multi-views、Model/My Assets/Collected 卡片及预览弹层。

- 新增并安装 assets_query、image_preview；独立摘要只覆盖 core.mjs 与新 2 文件，
  原 18 工具源/定义初次安装前后回读一致。后续只对新 2 定义 CAS 更新。
- 无 alt 图片按 task+index 区分；image.png 使用 single。多视图四个索引 0–3
  归为一卡，验证路径和文件名 task 一致、卡片计数/身份唯一，签名参数边界丢弃。
- Model 的五种筛选、Collected（无筛选控件）、Image/All 与 multi-views 为
  类型化范围；每次回读验证 active。没有权威结束/空态契约，不宣称全部账号数据。
- 图片预览核对 task/index，读取 Generation Model、Image dimensions 比例和
  可见转模型动作。只列出动作，不点击，不上传，不视为模型生成完成。
- 真实失败先保留：r1 图片预览失败；直接诊断复现关闭预览触发 Creator 说明
  浮层。r2 Escape 后鼠标留在头部导致浮层再次出现。r3 预览通过，但 Model
  切换被固定 header 遮挡，按钮 y=0 的中心点实际命中 header。原生 Home 验证
  按钮返回 y=116、命中 BUTTON。补命中预检/Home 和移到安全 All 后继续复测。
- 工厂测试发现解释器加载的是旧已安装包，非当前工程源码；脚本固定 src 并
  增加无 PYTHONPATH 的真实构建子进程回归。未为通过测试更改断言或安全检查。
- Python 非浏览器回归 800 passed、2 skipped（pandoc 缺失）、11 deselected；
  此轮收集后追加的工厂子进程测试另行通过，聚焦回归 33 passed。
  初次全量运行因 TMPDIR 的 /var 符号链接报错而中止，改 canonical /private/tmp
  后通过，保护检查保留。初次旧包测试与临时路径失败日志均保留。
- 当前资产查询源码摘要：
  `13c05dc89662502d4209d7b613418b3b54ffa00a973352984206e38801b43b59`。
  r4 的原生 CLI 证明 SDK 的 Home 仍未解除遮挡，命中预检因此在点击前停止。
  观察到 SDK 1.8.6 的键事件只发 key；按[官方 Input 协议](https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/pdl/domains/Input.pdl)
  增加有界等待及 Home 的 code/windowsVirtualKeyCode，直接 CLI 已切换 Model 并
  读到一张蓝色方块卡片。r5 完整 12 路径全部通过：Image/All 148 卡、多视图
  21 组、单图 index 0/3 与多视图 view 0/3 的四次预览、Model/My Assets 五筛选、
  Collected。模型六个范围各限读 10 张（item_limit），不以该数量作完整资产数
  证明。图片安静页尾也保持 partial。未将 r1–r4 失败回执改写为通过。
- 独立 GUI 对照：实际 Model/Collected active，渲染 20 卡，CLI 限读的前 10 个
  preview UUID 与独立 DOM 读取一致。余额 20115；每次真实调用均检查原未知上传
  receipt/active.lock 字节摘要不变。没有新上传、收费、分享、发布或模型导出。
  证据 asset-query-native-acceptance-r5.json、query-collected-independent-gui.json、
  query-collected-accepted.png。
- 当前 Node 回归 109 passed。仅 5 个纯逻辑 .mjs 的仪器化合计行覆盖 86.19%、
  分支 77.43%、函数 83.16%；新 asset-query.mjs 行 97.97%、分支 78.40%。
  注册 .js、Python、供应商付费结果与网站全功能不包含在这些百分比中。

证据目录 `/private/tmp/atm-tripo-extended-20261003/`：query-native-r1–r5.log、
query-r*-result-*.json、query-refresh-before/after-*.json、query-node-accepted-key.log、
query-python-focused-key-final.log、query-python-full-source-r2.log、
query-preview-close-popover.png。临时目录不是永久留存承诺。

此阶段仍只是功能族 2 的查询/图片预览部分；资产管理、图片编辑/下载/转模型、
查看器/绘制、更多导出以及付费供应商结果等缺口继续保留。

下一步优先利用 Rigged 查询返回的已有源，验证真实资产 UUID 与动画前置状态，
再补查看器和只读管理观察。旧上传锁和 5 积分 PBR 决定仍独立等待，不重试上传。

末尾恢复报价页：首个只读 workspace_inspect 请求失败并保留回执（本次未证明
确切根因），浏览器实际已进入空 Workspace；侧栏加载后第二个独立只读请求通过，
同一蓝色立方体、Generate PBR 5、20115 余额、未提交。query-final-pbr-result.json /
query-final-pbr-result-r6.json 与 query-pbr-handoff.png 均保留；页面已重新交接，
不把首个失败抹成成功，也没有为恢复页面解锁或重发任何收费/上传操作。

## 动画草稿与导出选项阶段 2026-10-03

Strategy: UI_SELECTOR
Contract: visible-ui
Evidence: 已有 rigged 人形源的 Animate 表单与六格式 Export 浮层，原立方体的
Rig the Model First 状态。只读取可见 DOM，不读取认证或内部请求。

- 新增 `animation_inspect`、`animation_prepare`、`export_options`、`export_prepare`。
  动画提示词与 1–10 秒时长绑定实际源和旧草稿摘要；预置只列出已渲染项。
  导出支持 USD/FBX/OBJ/STL/GLB/3MF、512/1k/2k/4k/8k 及当前启用的骨架、
  FBX 变体、OBJ 顶点颜色。关闭自有弹层后网页可能记住选项，后续先重新读取。
  没有点击 Generate、最终 Export、Send To；没有新增上传、下载或付费任务。
- 按真实网页失败证据完成最小修复：
  1. Rig 表单和侧栏存在两个相同 Animate href，按实际语义链接的匹配索引点击。
  2. SDK 文本填入排除 number 输入，时长改用原生 focus 与有界方向键，回读验证。
  3. Quad 单计数与 Triangle 当前/总计数分别识别，保留正数与 Export 就绪门槛。
  4. 512 纹理 combobox 不再误作动画数量按钮。
  5. 下拉框 `data-state=closed` 只表示关闭动画开始，层仍拦截点击；等待布局消失
     才打开下一下拉框，核对实际列表类型和命中目标；仅关闭本工具打开的弹层。
  6. 从 Animate 回到 Workspace 时侧栏先挂载、资产卡片后挂载。缺卡不是权威
     缺失；有界等待目标卡片，不重复导航点击，超时明确报告资产缺失。
  7. 原生点击先返回、SPA 路由后更新。直接跨源 CLI 已复现 `asset_mismatch`，
     随后页面进入正确目标；只把已知旧源视为过渡，等待指定源，第三源立即失败。
     自有 Export 弹层也等待布局消失后才返回，保留现有弹层保护和资产校验。
- r1–r9 原生失败日志/回执保留。r8 的前 15 条已通过，包括完整六格式准备、
  FBX Mixamo 与关闭骨架、OBJ 顶点颜色，以及恢复人形源 GLB/4k/骨架默认设置。
  r8 跨源失败、r9 首项失败由直接 CLI 复现 `asset_not_in_workspace`；随后 DOM
  已见该目标卡片，新增挂载等待回归。最终完整矩阵验收以末尾实测记录为准。
- 独立 GUI 对照 FBX/Mixamo/1k/骨架关闭已保存截图；不是导出文件验收。
  四个新定义与共享依赖 11+3 定义均 CAS 更新并回读；原四项及资产查询两项
  源码/定义不变。用户 Codex/Claude Skill 备份同步，运行时区块保持原样。
- 当前源码摘要：
  - extended：`6b9ae8b85aade9dd4a9d9a143a8920358ec4878cbadbb7950e5e26f2512ac99c`
  - workspace：`3b7df85e08edf55de3dc09c777ed771c01fbc0965d13b6db0b20528536909dcc`
  - ui-options：`47aca5a146ab8b2531893e2408a1b2914f2d0efc4ea506e896d2c6655dcebfb9`

### 本阶段最终验收

- r13 **22 条真实生成 CLI → ATM → OpenCLI → Chrome 路径全部通过**：Quad/三角
  网格就绪；人形源动画 3/10 秒准备、回读、清除恢复 5 秒；六格式与骨架/FBX/
  OBJ 选项；恢复人形默认；立方体缺骨架状态、OBJ 准备/恢复、GLB 恢复、PBR 报价页。
  `ui-options-native-acceptance-r13.json` 有逐条 job ID；每条核对旧未知上传 receipt/
  active.lock 字节摘要不变。没有新上传、付费生成、最终 Export 或下载。
- 最新 **143 Node 合成/状态/错误回归、74 Python 合同/假子进程/本地 HTTP 检查**
  全部通过；OpenCLI validate 为 24 commands、0 errors、0 warnings。全部 24 个
  生成包、已安装定义、适配器源字节回读一致。未把先前全工程 800 项写成本轮重跑。
- r10 用 wait=0 查询后立即要求 mesh ready，实际正确返回 pending；保留失败日志，
  真实矩阵改用已有 20 秒等待，完整就绪/计数断言不变。Python 中旧共享源码摘要
  断言的 6 次失败也保留，经审阅更新精确摘要后复测，未移除断言或安全检查。
- r11/r12 与直接跨源诊断继续暴露 SPA 路由过渡问题；r13 为该修复后的完整通过，
  不把 r1–r12 失败回执改写成功。图片上传未知及真实付费验收缺口继续独立保留。
- 最后 GUI 确认同一蓝色立方体 PBR Generator、Generate PBR 5、余额 **20115**，
  无浮层、未提交；原用户资产页保留。CLI 人形动画草稿恢复为空/5 秒，人形导出
  恢复 GLB/4k/骨架打开、FBX Blender；立方体恢复 GLB/4k 和 OBJ 顶点颜色关闭。
  人形 OBJ 顶点颜色 true 的测试值可能仍被 UI 记住，未声称全局偏好全部复原；
  网页后续仍先回读实际格式及选项，准备不等于文件导出。
  此页等待之前的具体人工决定，不清除上传未知锁，也不重复索取已请求的批准。

证据目录 `/private/tmp/atm-tripo-extended-20261003/`：
`ui-options-native-r1–r13.log`、`ui-options-r*-result-*.json`、
`ui-options-route-transition-diagnosis-r12.log`、`ui-options-native-acceptance-r13.json`、
`ui-options-all-node-source-transition-final.log`、`ui-options-python-source-transition-final.log`、
`ui-options-final-definitions-47aca5a146ab.json`、`ui-options-validate-source-transition-final.log`、
`ui-options-export-independent-gui.png`、`ui-options-pbr-handoff-final.png`。
直接诊断编号与矩阵编号不同，部分早期仅存在失败前的结果文件；原文件未改写。
临时目录不是永久留存承诺。Codex/Claude Skill 均同步、备份保留、运行时不变。

### 当前覆盖判定

| 范围 | 已验证的边界 | 仍需独立验收 |
|---|---|---|
| 资产与图片 | 类型/筛选/预览/ID 解析；分页明确 partial | 权威全量、管理/移动/重命名 |
| 模型 | 一次文字立方体完成、GLB 有效文件；后处理报价/准备 | 图片上传未知；多图/Smart Mesh 与新付费结果 |
| 工作区后处理 | 十二模块观察、五类语义准备/有报价提交合成测试 | 分割/UV 合适源、绘制/应用及供应商结果 |
| 动画 | rigged/未绑骨前置区分、提示词/时长准备/回读 | 预置应用、生成、播放/选择、动画文件 |
| 导出 | 六种格式及启用选项准备，已有 GLB 文件验收 | 其他格式真实文件与动画选择/导出、Unreal 导入 |
| 其他网页操作 | 记录可见入口 | 查看器/管理、图片编辑/下载、分享/打印/DCC 等 |

**整体覆盖仍为 partial，目标 active。** 工具数量、表单回读、自动化通过或
一次 GLB 文件成功均不是全网站功能完成。Agent 已实际执行“读网页 → 定位
契约差异 → 最小修改 → 新增回归 → 审阅摘要/CAS 更新 → 原生 CLI 复测”。
这不是 CLI 在运行中随意改写自身代码、按网页文案扩权或重新提交未知任务。

## 查看器/层级阶段 2026-10-04（r1–r4 历史失败与修复）

以下保留 r1–r4 当时的验收状态；同一最终摘要的 r5 通过与独立相机画面验收见下一节。

Strategy: UI_SELECTOR
Contract: visible-ui
Evidence: 蓝色立方体的渲染按钮、六个 Environment 预置、层级与 XYZ 表单；
真实生成 CLI 的 r1–r4 回执和原生 GUI/诊断截图分开保留。

- 已实现、生成并安装 viewer_inspect、viewer_prepare、viewer_camera、
  hierarchy_prepare、hierarchy_transform，总计 29 项。查看器源码当前摘要
  `fb81f31b26bd92adbf7983c0cdad2b1a3d05fa2352b69b56b5ddf4c25c4cf97e`。
  所有 29 定义/生成包及 16 源文件最终回读一致，原 24 项未改；新增 5 项独立
  CAS 更新、有源码备份和历史定义，旧生成包仅移入废纸篓。OpenCLI validate
  29 commands、0 errors、0 warnings；没有安装提示中的新版本。
- 自动化最新 194 Node passed（新增查看器文件 51 项）、84 Python passed。
  Python 使用隔离假状态/假凭证和真实假子进程；不是供应商持久几何验收。
  七个纯逻辑 .mjs 合计行覆盖 89.30%、分支 80.39%、函数 87.24%，不含注册
  .js/Python/供应商结果/全部网页；没有在本轮重跑前阶段 800 项全工程检查。
- 真实矩阵 r3：19 项在失败前通过，包括初始检查、7 种有效模式、4 次特效
  恢复 PBR、线框/网格开关和 6 环境预置；之后 Auto Rotate 数值验收失败。
  当前新版本 r4 首项又因现有弹层而停止，最终完整矩阵未通过。上述 19 项
  是较早源码版本的分阶段证据，不充当最终新版本的整体验收。
- 已按实际网页差异修复两个根因：
  1. PBR 与 Unlit/Toon/Sketch/Hologram 同时选中是有效组合。基础组三项互斥，
     特效最多一项且只在 PBR 基础上。关闭特效可能恢复先前 Normal/Solid；
     恢复普通 PBR 先关闭准确特效、回读，再必要时选基础 PBR。
  2. Auto Rotate 会改变可见角度，不是假固定 90°。起点在停转状态回读验证，
     再开启/恢复开关；rotation_preparation 保留该证据，最终角度返回实际值。
     增加动态角度、原开关恢复、错误数值不启用旋转的针对性回归。
- 真实失败留档：r1 旧标签无样式/无画布，模型就绪门槛保持，刷新后画布/正数
  Faces/Vertices 已恢复；无样式资源丢失的更深原因未证明。r2 Unlit 双选中
  失败是互斥假设错误；r3 数值失败是动态角度比较错误。后续只读诊断/自有层
  恢复也存在关闭超时：页面 hidden、fade-out running、currentTime=0。
  原生选择已有标签后 SDK 曾读到层消失，但最终生成 CLI 仍报 dialog_open；
  不放宽布局消失或已有弹层保护，不推断两个观察已构成最终恢复验收。
  自有层清理错误也保留原错误，避免侧栏遮挡点击把它改写成别的错误。
- 已请求人关闭测试页 Environment Settings/菜单并保持前台后继续不扣费复测。
  未收到完成回复时现有层保持，不自行批准任何登录/付费窗口。
- 层级/变换的合成路径已通过；真实新工具修改/恢复 XYZ 的完整矩阵仍待验收。
  原生手工微调后卡片时间更新，所以没有 Save 点击不等于没有持久变化。
  仅批准的蓝色测试立方体用于修改；其它模型、持久几何和重新下载另验。
- 相机只承诺固定有界原生输入并在失败时释放鼠标，camera_pose_exposed=false。
  全部手势的实际画面/质量验收仍待进行，不把输入回执当精确视角或质量证明。
- 本阶段没有新上传、收费、导出、Share/Feature 或 Delete；旧蓝色测试图
  submission_unknown 回执与 active.lock 每次真实调用后摘要保持不变。Codex/
  Claude Skill 已同步并留备份，注册运行时区块不变。分支未提交/推送/发布。

证据目录 `/private/tmp/atm-tripo-viewer-20261004/`：viewer-native-r1–r4.log、
viewer-r*-result-*.json、viewer-env-numeric-diagnosis-r3.log、
viewer-env-existing-layers-r3.log、viewer-env-layer-styles-r4.log、
viewer-activate-canonical-tab-r4.log、viewer-baseline-diagnosis-r4.log、
viewer-node-instrumented-final.log、viewer-python-r4.log、viewer-all-29-readback-r4.json、
viewer-opencli-validate-r3.log、viewer-skills-sync-r4.log、
unlit-pbr-combination-root-cause.png、environment-auto-rotate-live-angle.png。
诊断脚本一次封装缺 session 导致 bridge_protocol 的失败也保留；后续只读确认
只是诊断，不作为原生矩阵成功。临时目录不是永久留存承诺。

整体目标继续 active；完整功能族和未通过结果/文件/画面门槛保持原合同，不以
本阶段五个新增工具或局部修复缩小 computer use 对齐目标。

## 查看器/层级最终版本验收 2026-10-04（r5 与相机画面）

Strategy: UI_SELECTOR
Contract: visible-ui
Evidence: 生成 CLI → ATM → Chrome 的 r5 全矩阵，以及独立 CUA 截图逐张检查。

- 最终摘要 `fb81f31b26bd92adbf7983c0cdad2b1a3d05fa2352b69b56b5ddf4c25c4cf97e`
  的 **41 条真实 CLI 调用全部通过**。7 种有效渲染模式、4 次恢复普通 PBR、
  线框/网格、6 种环境、强度/角度起点/自动旋转及恢复、层级选中/显隐、XYZ
  三组修改与恢复、11 种相机输入均有逐条 job ID。动态角度起点实际回读 90，
  开启 Auto Rotate 后最终角度 149，是动态状态而非误报设定失败。
- 新鲜 CUA 重新绑定原测试页后读到自有 Environment Settings，关闭该层并
  等待布局消失，确认 0 个浮层，随后真实 r5 完成。此前请求人关闭该层的交接
  已由这次恢复解决，无需重复人工操作。未处理登录/ATM 批准或付费确认。
  浏览器先前脱离/后台动画停滞的更深原因仍未独立证明；r1–r4 失败证据保留。
- 相机另外执行 22 条免费输入（每个非 reset 动作先 reset，最后再 reset），
  对 **11 个动作逐张检查实际画面**：左右环绕分别露出左/右侧面，上下环绕
  露出顶/底面；四向平移改变模型的屏幕位置；放大占满画布，缩小约为基准
  一半线性占屏尺寸；最后回到正面居中基准。不是仅核对 input_dispatched。
- 固定手势的幅度仍有界而非精确视角控制。该测试页放大一步会裁切模型，
  平移也可能越出画布；不声称任意构图、精确相机姿态或所有模型质量通过。
  camera_pose_exposed=false；没有读隐藏引擎/相机对象或重放供应商接口。
- 独立最终 viewer_inspect 确认 PBR、wireframe=false、grid=false，Studio、
  strength=1、rotation=0、auto_rotate=false，唯一节点可见且未选中。r5 已
  回读 XYZ 恢复 position/rotation=[0,0,0]、scale=[1,1,1]。表单恢复不代替
  供应商持久几何或重新导出质量验收，网页可能自动保存仍保留为已知边界。
- 再次只读核对全部 **29 定义/生成包、16 个安装源码文件**一致，原 24 定义
  未改，最终摘要不变。本轮没有产品源码变更；前述最终版本 194 Node /
  84 Python 与 29 commands、0 errors/0 warnings 的记录不写成再次全量重跑。
- 全部真实调用后检查旧 submission_unknown 回执与 active.lock 摘要不变。
  新鲜截图余额 **20115**；没有新上传、付费、Save 点击、导出下载或发布。
  整体 12 功能族仍 partial/active，待付费决定与文件/质量缺口保持原合同。
- 最后用既有 workspace_inspect 恢复同一立方体的 PBR 面板，独立 GUI 确认
  Generate PBR **5**、余额 20115、正面复位、节点可见，无提交。测试页保留为
  既有付费决定的交接页；未重复询问批准、清理未知锁或扩大付费范围。

证据目录 `/private/tmp/atm-tripo-viewer-20261004/`：
`viewer-native-r5.log`、`viewer-native-acceptance-r5.json`、`viewer-r5-result-*.json`、
`camera-visual-acceptance-r1.json`、`camera-visual-r1-*.jpg`、
`camera-visual-r2-reset.jpg`、`camera-visual-*-result.json`、
`camera-visual-final-inspect-r1-result.json`、`viewer-all-29-readback-r5.json`。
最终交接另见 `viewer-r5-pbr-handoff-result.json`、`viewer-r5-pbr-handoff.jpg`。
截图为真实 JPEG、1280×723；最初按 .png 命名的原始字节保留，.jpg 副本字节一致，
没有转换或改图。验收清单脚本首次假定 PNG/720 高度而失败，按实际文件格式修正，
这不是 CLI 或网页功能失败。临时证据目录不承诺永久留存，分支未提交/推送/发布。

## 图片生成表单阶段 2026-10-04（原生验收进行中）

Strategy: UI_SELECTOR
Contract: visible-ui
Evidence: Generate Image 当前可见表单、六模型下拉、五比例/四数量、4K 开关和九模板。

- 新增 `image_form_inspect` / `image_form_prepare`，区别于既有图片转 3D 的
  `image_quote` / `image_generate`。不上传、不点生成、不重放历史任务。
  独立源码组只增加 image-form.mjs/js，不修改原 29 项的源码摘要或定义。
- 实际网页有两个重要契约差异：Midjourney v8.2 隐藏比例、数量与 4K 控件，
  返回 null/不可用，而非套用其它模型的默认数值；比例按钮悬停时文字隐藏，
  用已观察的 button[value] 与 data-state/aria-pressed 核验，避开易变 innerText。
- 比例允许无选中值。模板为单选，选择另一个会替换模板；在自有 Templates
  层再次点同一选中项会清除。它表现为带星标的表单缩略图，不是上传文件。
  已用 CUA 检查 T Pose → Character Extraction → 清除，并恢复初始表单。
- 准备要求 exact expected_draft_sha256，绑定源、模型、提示词、选项、模板和
  已有参考/文件计数；保存提示词与参考，不接收任意 selectors/URL。提示词
  0–10000、五比例/无选中、数量 1–4、布尔 4K、九模板/清除均为类型化输入。
  模型隐藏未请求选项的可见变化通过 implicit_changes 返回，不伪装原值仍可见。
- 免费额度 Free 14/1000 与表单旁 0/80 或 0/40 的数字并存，Generate Image
  按钮本身没有明确报价。billing_observation.quoted_credits=null；未按文案猜
  “免费”并点击。已花费的立方体批准、旧未知上传回执/锁继续保持原边界。
- 初次实现离线 **222 Node / 88 Python passed**，当时新增 Node 28、Python 4，包括
  序列化 DOM、悬停文字隐藏、模型控件缺失、草稿摘要、原有层/遮挡、参考变化、
  关闭失败与真实假子进程/稳定 key 复用。不是图片生成结果或全网站验收。
  Python 首次因沙箱拒绝系统废纸篓而终止；保留日志，获得执行范围后重跑通过。
  全部测试清理仍走 `/usr/bin/trash`，没有删断言或改永久删除保护。
- 本节初次记录时编译包已生成、定义审阅完成；安装与真实 CLI 表单矩阵进行中，最终结果
  应在本节追加，不把 CUA 探查或离线通过当作真实工具验收。

本阶段证据目录 `/private/tmp/atm-tripo-image-form-20261004/`；当前 Node 日志
`node-all-r1.log`、Python `python-r1.log` / `python-r2.log`。整体目标仍 partial/active；
图片上传、生成/编辑/放大/Cutout/多视图、文件与质量均保留独立完成门槛。

## 图片表单根因修复、安装与最终复测边界 2026-10-04

Strategy: UI_SELECTOR
Contract: visible-ui
Evidence: 原测试页的 CUA 命中/滚动、生成 CLI 逐条回执、隔离回归与精确安装回读。

- 最终图片表单源码摘要
  `f95635e8e0db3d85e25e34b44084fbf7752e5972359368be11856d95a597ea10`。
  inspect 定义 `8e48ab6a830a69f2103cca87e7d21942747ef42779d418755a0c974b85b3d0ab`，
  prepare 定义 `6b92b5be98f4902316c3538e14c892ac6d48590c1ad93238eff4dc6afd8fa044`。
  已安装并回读全部 **31 定义/生成包、18 安装源码**一致；原 29 项逐项不变。
  新旧源码备份、旧生成包进废纸篓、CAS 摘要历史保留；没有重装 ATM 或重置 vault。
- 第一项实际失败来自 4K 标签在祖父行而非直接包装层。按真实结构补回归，
  仍保留确切标签断言。第二项来自 Midjourney 移除一个空上传控件：仅允许明确
  模型切换时的 [0]↔[]，记录 implicit_control_changes；非空文件丢失、参考变化、
  无模型切换的空控件变化及其它 FileList 形状仍失败。生成 CLI 的模型恢复已
  回读 [0] 和原 GPT Image 2.5 草稿，未重试旧图片上传。
- r3（8ec8f5…）与 r4（07541c…）各 **18 条真实调用通过**：初始检查、六模型、
  恢复模型、五比例/清除、数量 1–4。两轮都在 4K-on 失败，35 条完整计划未通过。
  这些版本的成功保持为历史，不写成最终 f956 版本已完成原生矩阵。
- 更换 setChecked 为 click 的实验同样失败，后来证明不是勾选状态缓存根因：
  实际 540px 表单位于 511px 内部视口，4K 中心 y=634 命中固定页脚 0/80 区域，
  两种路径均在点击前被命中校验阻止。独立 CUA 点击开/关成功并恢复 false；
  聚焦准确 switch 并按 End 后 y=605、命中恢复，再按 Home 复现原遮挡。
  最终实现 focus + 完整原生 End 键对（VK 35），重新等待命中后仅点击一次。
  resolution_preparation 报告修复与实值；未恢复命中/缺少后端能力分别明确失败。
- 最终离线 **237 Node / 88 Python passed**，新增 Node 43、Python 4。
  Node 八纯逻辑模块仪器化为行 87.48%、分支 81.23%、函数 86.96%，不含注册
  包装器/Python/供应商结果，也不等于全网站覆盖。DOM 序列化在独立 VM 中测试，
  界面代码覆盖数字另有该计量边界。OpenCLI validate：31 commands、0 errors、
  0 warnings；两个用户级 Skill 已备份同步，原运行时块不变，README 仍 90 行。
- Python r4 出现四项本地假 HTTP approve 的 ReadTimeout（84 passed/4 failed）；
  原日志保留，未改断言/放宽超时。停止并行浏览器测试后 r5 同一 88 项通过
  （108.43s）。并行负载/超时的更深原因未独立证明，不声称已修复 HTTP 根因。
- 最终版本的 4K 三调用 smoke r3/r4 都停在初始 inspect，故没有最终 4K/模板/
  提示词矩阵通过证据。只读直接诊断分别见 cleanup_failed、dialog_open；SDK
  只读后见自有层已消失。doctor 仍显示 daemon/extension 健康，不能据此声称
  页面控制健康。CUA 截图超时后重置，原标签页控制接口持续报告未附加调试器。
- 改用原生 Chrome Window 菜单选择准确 Tripo 测试窗口，仅截图核对：地址正确
  但网页区域白屏。SDK 同时确认准确源的空提示词、无参考图/模板、FileList [0]、
  GPT Image 2.5、比例 null、数量 4、4K false；这两个观察不混同为 GUI 验收。
  保存空草稿证据后只普通刷新一次，没有重试任何上传/生成。随后原生前台窗口
  改成 about:blank，第二张截图不算 Tripo 复测；UI/DOM 连接与窗口变化原因仍待查。
  Page.bringToFront 诊断被桥的方法白名单拒绝，失败保留，未修改浏览器策略。
- 人已回复“正常图片生成面板”：原生截图的白色区域不是已确认的网页故障，
  不继续刷新。此回复不是新的付款/上传批准。当前只完成本地实现与安装层，**完整原生验收未通过**，整体
  12 功能族仍 partial。未清理未知锁，没有新增上传、生成、下载、Share 或收费。
  保留此前最多 5 积分 PBR 决定的边界，未重复询问或沿用已消费的立方体批准。

证据目录 `/private/tmp/atm-tripo-image-form-20261004/`：
`node-file-visibility-before.log`、`node-4k-click-before.log`、
`node-4k-footer-before.log`、`node-4k-native-end-before.log`、
`node-instrumented-final-r7.log`、`python-final-r4.log`、`python-final-r5.log`、
`native-r2.log`、`native-r3.log`、`native-r4.log`、`r*-*-result.json`、
`4k-smoke-r3.log`、`4k-smoke-r4.log`、`direct-inspect-r4.stderr`、
`direct-inspect-r5.stderr`、`owned-layer-read-r1.log`、
`empty-draft-before-render-recovery.log`、`owned-layer-bring-front-r1.log`、
`refresh-r6.log`、`all-31-readback-r3.json`、`opencli-validate-final-r2.log`、
`skills-sync-r2.log`、`4k-native-window-baseline.jpg`、
`4k-native-window-after-refresh.jpg`。第二张为 about:blank，明确不作为测试表单截图。
临时证据不承诺永久留存；当前分支未提交、推送或发布。

## 人工显示核对后的控制通道复核 2026-10-04（历史失败；恢复验收见下一节）

- 前台 direct inspect r6 仍报 cleanup_failed。SDK 只读观察到自有模型下拉
  data-state=closed、410px 高、opacity=1；随后标准 selectTab 已选中该页，
  但 document.visibilityState 仍为 hidden。两次间隔 500ms 的读取相同；
  getAnimations() 为空，不把此证据写成已证明的“动画暂停”原因。
  后续只读样式检查时 listbox 已消失，仅零布局 closed dialog；因此也不将
  data-state=closed 等同布局已消失，原有保护保持不变。
- Chrome Window 菜单没有旧测试窗口；浏览器清单仍有旧测试标签记录。
  两个控制面的差异是观察，不推断用户账号退出或网站白屏。原生窗口菜单
  只核对标题，不操作其它前台登录流程，不取消其调试或变更浏览器策略。
- 在原选定 Chrome 新建测试页，经 Assets → 蓝色立方体预览 → Edit in
  Workspace → 已渲染 UUID 资产入口 → Image 的可见 SPA 路径进入。
  新页 CUA 可读且截图正常，余额 20115，Generate Image 禁用；截图
  fresh-image-form-baseline.png。它是独立显示证据，不是生成 CLI 完整通过。
- 最终源码 f956 的 4K smoke r5 再次停在初始 inspect；失败回执/日志保留，
  没有运行完整矩阵或点击 4K/Generate。只对 SDK 自有测试页执行空草稿、
  无参考/文件、全部七项原设置校验后替换标签页；不关用户其它标签或重置登录。
  首次诊断脚本的 JSON 字符串比较受对象键顺序影响，未进行任何关闭；修正为
  完整键集合与逐字段等值比较后才执行。旧日志保留，不跳过草稿保护。
  替换后 SDK 返回 about:blank 且页面 identity 字符串复用；4K smoke r6 仍停在
  初始 inspect，未运行开关动作。只读 r2 捕获 closed listbox 的动画 running、
  currentTime=0、duration=150，间隔 500ms 仍为 0 且文档 hidden；这是此次的
  暂停证据，区别于前次 getAnimations() 为空，原因仍未确定。所有动作保持
  旧未知上传回执/锁。
- 泛用 Chrome 应用读取被执行审查拦截：该绑定可能落在其它 Google OAuth
  登录页。此后停止泛用应用访问，不取消其它调试或读取其它登录内容，仅使用
  精确 Tripo 页和独立桥接应用。未通过间接调用重复被拦截的访问。
- 后续公开 CLI 帮助调用报 OpenCLIApp 未运行/本地桥 socket 不可用（exit 69），
  与此前 daemon 健康为不同时间点。用 CUA 启动既有 /Applications/OpenCLIApp.app，
  其概览显示 0.1.38 / 就绪，未点击安装修复或权限/登录控件。doctor r2 显示
  daemon 1.8.6、extension 1.0.24、连接通过，未升级；恢复后只读 inspect r7
  仍报 cleanup_failed。应用暂时退出是否导致动画问题仍待证，不将时间关联
  写成根因修复；不继续重复 smoke/刷新，最终 f956 原生验收保持未通过。
- 末尾独立 CUA 只读回查：正确 cube 源、GPT Image 2.5、空提示词、比例 null、
  数量 4、4K false、无可见层、Generate 禁用；新页已标记后续交接。
  CUA 的只读 DOM 代理不暴露 FileList，首次尝试读取 files.length 报错，未写入
  页面；修正为仅报告一个 file input。它不替代 SDK 对文件零计数的证据。

追加证据：direct-inspect-r6.stderr、human-normal-panel-draft-check.log、
live-route-r1.log、select-adapter-tab-r1.log、closed-layer-styles-r1.log、
4k-smoke-r5.log / r6.log、renew-empty-test-tab-r1.log / r2.log、live-route-r2.log、
bridge-doctor-r2.log、direct-inspect-r7.stderr、all-31-readback-r4.log / json、
fresh-image-form-baseline.png。

## 前台恢复后的图片表单最终验收 2026-10-04

Strategy: UI_SELECTOR
Contract: visible-ui
Evidence: 最终精确源码的生成 CLI/ATM 回执、独立 CUA 画面与恢复回读。

- 人回复“已置前”后，独立原测试页正常，余额仍为 20115；SDK 初次只读清单
  没有 Tripo 租约页，诊断明确失败而非伪报空账号。随后 foreground inspect r8
  通过，重新建立的真实 CLI 页为 1885519550，与此前用于显示核对的 1885519519
  是两个标签。最终画面验收绑定 9550，不拿未被 CLI 修改的旧页当结果。
- 同一最终源码 f95635… 的生成 CLI → ATM → Chrome **3 项 4K smoke 通过**：
  检查、开启、关闭/恢复。开启实际报告 viewport_repair=focus_end、verified_value=true；
  关闭报告 false，原草稿与计费观察恢复。由此补齐先前失败的真实滚动/开关路径。
  前台/租约变化后恢复是事实；更深的窗口/动画暂停原因未独立证明，不声称
  重启 App 单独修复了根因，也没有修改浏览器策略或放宽层消失/命中校验。
- **r5 全部 35 项真实表单矩阵通过**：初始检查、六模型/恢复、五比例/清除、
  数量 1–4、4K 开/关、九个当前渲染模板/清除、测试提示词/清除、全设置恢复、
  最终检查和组合准备。每项读取确切 source/draft，核对未上传/未生成/未下载、
  Free 14/1000 不变及原未知锁/回执 SHA 不变；所有 35 项定义摘要逐项匹配
  最终 inspect 8e48ab… / prepare 6b92b5…，不是旧版本 18 项成功的合并计数。
- 独立 CUA 在真实 CLI 页观察到 69 字测试提示词、GPT Image 2.5、1:1、
  单张、4K 开启、Generate 启用。保存原视口与 End 滚动后开关完整可见两张
  截图；没有点击 Generate。随后经生成 CLI inspect + prepare、精确摘要绑定
  恢复全部原设置，再独立回读空提示词、比例 null、数量 4、4K false、无模板/
  可见层、Generate 禁用。CLI 另证 references=[] / FileList=[0]；CUA 仅证
  一个 file input，不将代理未暴露 FileList 写成独立文件零计数。
- 回查 **31 定义/生成包、18 源文件**全部精确一致，原 29 项逐项不变，
  未改源码/pin、未重装、未更新凭证或同步配置。本轮没有重跑前阶段
  237 Node / 88 Python；它们仍是该同一最终源码的已有离线证据。
- 该图片表单阶段已完成实现、离线/安装、真实 CLI、独立画面和草稿恢复门槛。
  **不等于图片生成完成或整站 12 功能族完整覆盖**：参考上传、全部未来模板
  分类、图片生成/编辑/放大/Cutout/多视图、产物文件与其它模块结果仍待逐项验收。
  旧未知上传锁继续保留；人置前不是新增付费批准，既有 PBR 决定仍未收到答复。

当前源码摘要：f95635e8e0db3d85e25e34b44084fbf7752e5972359368be11856d95a597ea10。
证据目录仍为 /private/tmp/atm-tripo-image-form-20261004/：
live-route-r3.log（初次租约页缺失）、direct-inspect-r8.stdout / stderr、
4k-smoke-r7.log、native-r5.log、r5-*-result.json、native-accepted-final-r5.json、
native-r5-independent-proof.json、native-r5-prepared-proof.png、
native-r5-prepared-4k-visible.png、native-r5-restored-form.png、restore-baseline-r8.log、
restore-r8-*-result.json、all-31-readback-r5.json / log。原失败日志全部保留。
只对自建旧显示核对页验证空提示词、文件输入空值、无参考图片与禁用生成后
关闭该重复页；真实 CLI 测试页已保留作后续交接。其它用户标签、登录和设置不动。

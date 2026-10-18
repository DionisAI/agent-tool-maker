# 小云雀网页 CLI 覆盖与验收

2026-10-08，当前分支 `feat/media-cli-delivery-20261007`；较早记录保留原阶段名称。

当前默认编译仍为18项。生产 ATM 已安装27项：独立[媒体运行时](XYQ_MEDIA_RUNTIME_CONTRACT.md)
20项、既有3项图片结果和2项下载、2项[首页素材只读发现](XYQ_HOME_MATERIAL_CONTRACT.md)。
新素材模块549相关Node/14新Python通过，实际生成CLI→ATM→App的格式与菜单查询通过，
完整首页草稿保持、同键同job；用户许可限定本轮绑定，结束已官方解绑。
获准“我的世界光影风格图”会话当前渲染1张图片，结果查询完成、未下载，视频/音频样例仍待取得。
此前538 Node/63相关Python与LOCAL原夹具查询通过；独立音频项目 origin_mismatch 仍保留，
此次首页绑定与只读通过不代替项目页验收。
[单次生成合同](XYQ_GENERATION_CONTRACT.md)仍区分提交、真实task与下载验收。
较早阶段的数量、pin 和目录作为历史证据保留。文中 `generated/xyq-*` 阶段目录都是本机构建输出，
未提交到仓库，下文逐处标注；当前27项按[重建步骤](XYQ_MEDIA_RUNTIME_CONTRACT.md#从源码重建并安装27项)重建。

最新[会话图片结果查询](XYQ_RESULT_CONTRACT.md)：三个新只读工具已追加到生产ATM和
独立OpenCLI加载器，真实生成CLI→ATM→App→获准已有会话验收通过。结果资源ID不等于
task ID；下载控件计划不是下载完成。显式 --include-results + --include-delivery 编译23包，
不代表23项全已安装或全面验收。517 Node/90相关Python通过；原唯一下载尝试保持未知，
没有重点击，文件落盘/解码与视频/音频结果覆盖继续待验收。

最新[图片下载交付实现](XYQ_DOWNLOAD_CONTRACT.md)：两个独立工具及常用ATM运行时现已安装。
529 Node/121相关Python通过，含生成CLI→隔离源码ATM→真Chrome合成下载→完整解码；
另完成新安装包的假凭证兼容、完整解码、生成状态CLI及未知新键零桥接预检。
常用ATM原未知标记查询及同键同job通过，不是供应商下载完成。
旧未知下载在本项目/原验证工作目录均登记保护，没有再点下载。
用户本轮仍指定“我的世界光影风格图”：当前渲染只见一张图片，未见视频/音频；
范围是当前DOM而非完整会话历史，视频/音频结果合同仍待实际样例。

随后已安装 App 的纯 CLI 下载组件通过：独立本机合成 PNG，一次原生点击、
真实完成事件含浏览器下载ID/源URL/路径，精确文件SHA与完整解码通过。
另两份不同夹具的阻断/观察差异保留；不把 CUA文件落盘等同App事件。
该组件阶段业务pin/生产安装保持；后续只追加两项下载定义/一条原生加载器，
198旧定义/87旧源码/六原未知或付费回执不变。常用ATM与两个用户Skill已可回退升级。
全仓初轮四失败：旧UI夹具依赖已修复且17项通过，三处旧Tripo快照/pin差异仍待修；
不声明全仓全绿，不发布或合并。详见下载合同最新节和安装复验收据。
本机组件阳性不是小云雀媒体交付，旧未知供应商下载仍保持。

最新实机：用户确认后，旧 c70aa32 上传入口只执行了一次合成 MP3 追加，
返回 `submission_unknown`，原 request-key/intent/active.lock 保持；没有观察到新增 MP3 卡片。
原 WAV、结构化 token、完整音频稿 SHA64b537 与6430积分观察保持。
原生只读诊断证明输入定位/同根重查/原稿稳定；原底层错误没有透过 ATM job 返回，
不把这一未知状态解释为上传成功或确定零传输。
上传桥现已接入公开文件选择器 API，单入口升级为 f33eecb，254 Node/97受影响Python通过；
未自动重传。证据、推断和后续门槛见 [MP3 合同末节](XYQ_MP3_REFERENCE_CONTRACT.md)。

## 范围真源

**最新调整（2026-10-07）：本期仅图像、视频、音频生成的网页功能对齐**，
包括指定音色、自有音色上传、参考素材、参数、任务和下载，见 [媒体合同](XYQ_MEDIA_CONTRACT.md)。
白板、故事板、3D 导演台和复杂时间线暂缓。以下完整网站表保留作先前盘点，不是当前完成门槛。

先前用户要求**网页上的完整功能**。网页实际入口、表单、动态选项及工作区状态是范围真源；
Pippit CLI 的功能清单仅作对照，接入它并不构成网页完整覆盖。

采用 Tripo 同类的受审阅 DOM/原生输入适配器 → ATM manifest → JSON CLI。
查询、编辑、上传、付费、下载、分享/发布分别授权和验收。认证保留人工入口和浏览器所有权；
网站自己要求的登录/MFA/验证码、账号变更和购买不由 Agent 自行确认。
永久删除没有纳入自动执行；可恢复操作需确认产品恢复机制和用户范围。

## 首轮实际观察（历史证据）

在独立 Chrome 盘点 tab 观察已登录网页 `/home`，没有读 Cookie、存储或认证文件。
仅打开/关闭自己的参数弹层、切换空首页模式；没有打开已有创作会话、创建项目、上传、提交生成、购买或发布。
临时切换模式的浏览器 UI 行为与 CLI 的纯读取验收分开记录。

确定的语义锚点包括：

- `nav[aria-label="功能导航"]`、`nav[aria-label="创作快捷入口"]`。
- `#title-section-prompt-container`、`[role="tablist"][aria-label="Agent 类型"]`。
- 个人导航按钮、header 的额度 popover；输出仅登录/额度，不输出姓名或历史标题。
- 选择创作模式、模型选择和偏好设置、可编辑 textbox、画布 switch、开始生成/生成按钮。
- `section[aria-label="模型选择"]` 与 `section[aria-label="偏好设置"]` 内 checkbox/radio、时长字段。

观察到图片的模型/比例/分辨率；视频的模型、参考/编辑/延长/首尾帧、比例、分辨率、时长、seed；
音频的模型和采样率。选项随模式和模型变化，当前可见列表不是全量/永久枚举。
音频成本出现按秒单位；工具保留原单位文字，所有当前成本观察均标为 `not_final`，不是消费批准。

短剧首页有上传剧本、剧本创作、重制转绘、粘贴文本、风格、比例和创建画布入口。
营销首页有商品/角色、素材、创意/Hook/风格、技能和模型偏好。
这些是**入口观察**，不是故事板、3D 或成片导出验收。

促销弹窗 X 控件的 aria-label 误用活动标题，首次关闭被自动审查拦截。
只读 SVG/位置及截图确认其为 `lucide-x` 后关闭；购买按钮保持未点击。
该关闭特例未纳入自动适配器，后续工具保留已有弹层而非自动点活动标题。

## 完整功能对照表

| 网页业务域 | 目标操作 | 目前证据/实现状态 |
|---|---|---|
| 登录、额度、身份范围 | 登录检测、额度查询、账户/空间识别 | 登录/额度只读适配器已实现；空间识别待观察 |
| 首页与导航 | 创作/短剧/营销、快捷入口发现 | 首页入口读取已实现；自动切换尚未实现 |
| 模型与参数 | 当前表单、动态模型/选项、禁用态 | 读取、摘要绑定准备已实现；隔离完整准备和真实采样率 UI 已验收；安装桥接验收待完成 |
| 普通创作 Agent | 原始需求、素材引用、续接、人工问题 | 首页观察；会话业务待实现 |
| 图片生成/编辑 | 参考图、交互式编辑、参数、结果 | 首页表单/选项观察；上传与提交待实现 |
| 视频生成/编辑 | 参考、编辑、延长、首尾帧、Draft/成片 | 首页表单/选项观察；提交与成片待实现 |
| 音频 | 音乐、人声/配音、音效、参考音频 | 网页模型/采样率观察；实际业务待实现 |
| 创意助手/爆款复刻/拉片 | 输入引用、分析、方案、后续生成 | 首页存在入口；领域流程待观察 |
| 素材/角色/商品库 | 查询、上传、组织、引用 | 首页入口观察；库内部待观察 |
| 项目/历史/任务中心 | 查询、筛选、续接、任务状态、取件 | 空测试项目创建/命名 UI 验证；任务中心通知列表观察；业务解析与分页待实现 |
| 自由/创作画布 | 节点、连线、布局、上下文、编辑 | 当前画布读取已实现并以实际源码实测；文本节点 UI 创建/编辑及新页面回读已验收；CLI 写入待实现 |
| 画布图片/视频工具 | 裁剪、抽帧、打光、镜头、全景、重拍 | 教程候选；当前 UI 与工作流待观察 |
| 剧本助手/解析 | 上传/粘贴、创作、修改/版本、解析 | 短剧首页观察；实际业务待实现 |
| 短剧资产与分集 | 角色/场景/音色、分集、素材 | 教程候选；当前工作区待观察 |
| 故事板/智能预演 | 镜头增删排序、脚本、重拍/生成、确认 | 教程候选；当前工作区待观察 |
| 3D 导演台 | 对象、机位、关键帧、预演、截图/渲染 | 教程候选；当前 UI 操作待观察 |
| 时间线与合成 | 多轨、剪辑、音频、输出、成片导出 | 教程候选；实际 UI 与输出待观察 |
| 营销 Agent | 商品/角色、Hook/创意/风格、方案、成片 | 首页控件观察；完整流程待实现 |
| 技能/资源/课程/模板 | 发现、引用、技能导入/创作 | 首页存在入口；安装/上传另验收 |
| 导出、分享、发布、团队 | 文件交付、可见性、协作范围 | 待逐项观察；发布/权限扩大单独确认 |
| 账单/订阅/账号管理 | 只读信息与人工操作入口 | 待观察；购买和认证确认留给人 |

没有全量覆盖百分比：分母尚在工作区观察过程中确认。
先前 8 个生成工具不代表上表各项都已可执行，也未安装到实际 ATM。
最新默认编译为十四个媒体阶段工具；复杂工作区暂缓，见本页末节。

## 首批生成 CLI

| 工具 | 行为 |
|---|---|
| `xyq.web.account` | 当前首页的登录/额度读取，排除身份原文 |
| `xyq.web.surface` | 当前首页导航/快捷入口/Agent 选中状态，明确部分覆盖 |
| `xyq.web.form_inspect` | 当前创作/营销表单元数据、禁用态、成本观察；排除提示词原文 |
| `xyq.web.form_options` | 读取**已打开**的模型/参数菜单，不开关菜单，不修改选项 |

本批工具完全没有导航、点击、上传或提交动作。短剧工作区当前没有相应通用表单解析，
`form_inspect` 返回明确的 `unsupported_surface`，而不是成功空结果。
菜单未展开报 `options_closed`；加载、登录、页面改变、源摘要漂移及桥接错误各自区分。

真源：`examples/opencli/xyq-web/{core.mjs,inspect.js}`。
编译：`scripts/build_xyq_web.py`。
生成包：`generated/xyq-web-foundation/{account,surface,form_inspect,form_options}`（本机构建输出，未提交）。
每个包有 manifest、标准库 `tool.py`、输入示例、README、bundle-lock；没有登录数据。
适配器源摘要：`94fd1bdfffa400c0276c3ae30f19fb9cfe38a4a26077cd3c29813ec930d823d3`。
工具仍以 `atm` 为调用入口，未另装供应商命令。

## 验收证据与缺口

- Node 协议/无副作用/错误分型测试：**16 passed**。
- Python manifest、摘要、CLI 包完整性、已有输出保留：**7 passed**，含上述 Node 测试包装运行。
- 原生 Chrome 假网页：**13 passed / 0 skipped**，所有应用请求夹具响应或终止。
  图片/视频/音频读取、单位、隐私过滤、非法额度、origin、登录、域缺口和菜单仅读取。
- 初轮原生测试 10 项失败，定位为中文夹具缺 UTF-8 声明；修复夹具后原断言全部通过。
  初轮回执保留，不删除失败证据。
- 原生回执：`/private/tmp/atm-xyq-web-browser-20261007-r2.xml`。
- 真实网站：上述入口与 DOM 锚点由 CUA 观察；**不等于已安装工具的真实端到端验收**。
- OpenCLIApp 当前未运行，启动被自动审查暂停，已请求明确的小云雀只读使用许可。
  没有通过另一条路径绕过该暂停，没有修改浏览器策略或扩大其它站点访问。
  此为初轮历史状态；最新许可、CLI 执行与待验收项见本页末节及音频合同。
- 真实账户中没有生成/上传/购买/发布；编辑、付费、交付和独立服务器均待后续验收。

下一步先完成浏览器桥只读端到端验收，再按领域扩充表单准备、任务/结果读取、
画布与短剧工作区。具体上传/消费测试绑定新的素材、模型、报价与预算。

## 第二批：表单准备与真实测试画布

2026-10-07。前一节保留首批历史证据，当前使用
`generated/xyq-web-form-canvas-stage/`（本机构建输出，未提交）八个包。
旧 foundation/form-stage 包保持原状；源已变化，旧 pin 会报 `definition_changed`，不继续使用旧定义。

新增工具：

| 工具 | 行为与验收边界 |
|---|---|
| `xyq.web.form_state` | 当前创作图片/视频/音频草稿、引用/文件元数据摘要；不输出提示词原文 |
| `xyq.web.form_choices` | 打开并关闭自己的模型/偏好菜单，返回动态语义选项；已有弹层保留 |
| `xyq.web.form_prepare` | 绑定完整草稿摘要；原生设置模型、参数组、视频时长、画布和纯文本提示词；无上传/生成 |
| `xyq.web.canvas_inspect` | 当前 `/project` 的确切项目/画布绑定、DOM 节点类型/ID/布局及文本摘要；不打开其它项目 |

表单合同见 [XYQ_FORM_CONTRACT.md](XYQ_FORM_CONTRACT.md)。
图像/视频/音频的准备使用**当前可见选项**，不把教程或过期 Pippit 枚举当成可执行按钮。
新增两个真实 DOM 根因修正：

1. 首页模型在 AX 是 checkbox，在 DOM 却是 `button[aria-pressed]` 和 title slot。
   原仅读 role=checkbox 的夹具成功与真实网页支持不一致；修正语义读取并增加真实形状原生测试。
   音频 radio 的组名来自参数 heading slot，也纳入解析。
2. 新页面的文本节点 `contenteditable=false`，选中编辑时才为 true。
   首轮新页读取显式返回文本未知；观察同一 editor class 后扩展纯读取范围，两种状态均测试。
   没有为读文本而选中或激活节点。

真实 UI：采样率 `44.1kHz -> 48kHz -> 44.1kHz` 回读验证，原设置已恢复。
弹层关闭使用本次菜单的原生 Escape，并保留已存在的其它层。
截图：`/private/tmp/atm-xyq-audio-restored-20261007.jpg`。

用户明确允许创建 `ATM-XYQ-CLI-test`，仅测试内部编辑，零上传/生成/消费。
通过首页的创建画布按钮创建**一个**项目；该入口在新标签页打开，首页 URL 保持不变。
先检查标签页增量而非重复创建。项目命名、文本节点新建和编辑均用原生 UI。
测试文本 `ATM CLI text-node smoke test`。
在全新页面用 `canvas.mjs` **实际源码**经 CUA 读取，项目名、节点 ID 和文本 SHA 一致，积分保持 6396。
这是测试文本持久化证据；工具的 `saving=false` 本身仍不等于保存完成证明。
截图：`/private/tmp/atm-xyq-text-node-persisted-20261007.jpg`。
实际源码的 CUA 读取通过，不等于 OpenCLIApp/已安装 CLI 路径通过。

任务中心已观察：通知式 `ul>li`、收起、开启桌面通知、查看项目/对话；无筛选 tabs。
任务完成通知不是视频/资产交付证明。没有开启通知或打开用户的已有项目/对话。
后续首页源码查询遇到原首页标签被关闭，诊断为页面引用失效；没有将它计为 DOM 成功。

当前源 pin：

- 查询：`b72cbc4c1c7eeff39b8b0e9c20fc4d2837205724782915e3b573ebf3a9f247c4`。
- 表单：`f39da193447c8982390dab0103e09a5b9bc1e97b2a64ad637c7a73ef5b2f0a90`。
- 画布：`915256ebf08cfc739ebd44396becb5a28d9600a69cd1151736b14ccd2247fd96`。

本批验证：Node **40 passed**；Python 定义/摘要/隔离实际子进程 **15 passed**；
原生 Chrome **24 passed / 0 skipped**。
表单原生测试通过 test-only RPC 执行实际 JS 工作流，所有应用请求被假页响应或终止；
没有借用生产 profile。回执：`/private/tmp/atm-xyq-form-canvas-native-20261007.xml`。
不将 Python 内包装的 Node 测试重复累计为独立覆盖。

本段的复杂工作区路线已被最新范围调整暂缓；既有源码/生成包/测试项目保持原状。
下一步按 XYQ_MEDIA_CONTRACT.md 补齐音色/素材、三个生成流程的任务与交付。

## 当前媒体优先阶段

最新用户指令收敛到图像、视频、音频生成，同时要求网页的指定音色、自有音色上传等能力。
范围/操作链路真源为 XYQ_MEDIA_CONTRACT.md；复杂工作区从本期完成门槛移出，源码与旧包保留。
AGENTS、README、根/包内 SKILL 及编译器默认范围已对应调整，未重装用户级 Skill 或操作 vault。

当前包：`generated/xyq-web-media-stage/`（本机构建输出，未提交），七个媒体基础包均 `validate_bundle.valid=true`，
查询和表单 source pin 与第二批一致，仍未安装。
编译默认不包含画布；显式 `--include-canvas` 保留实验导出能力，测试验证两种输出范围。
没有把基础表单准备标成已完成生成、音色选择或上传。

真实音频首页：Seed Audio 1.0 提供六个采样率并描述参考音频支持；标准生成的偏好菜单无其它设置。
两个首页菜单中均未观察到独立音色选择器，其它音频工作流的入口继续定位。
临时参数与工具引入的 `@` 均已恢复；没有选择既有角色/素材、上传、生成或消费。
截图：`/private/tmp/atm-xyq-media-audio-scope-r2-20261007.jpg`。

本轮综合回归：Node **56 passed**（含暂缓的画布/文本回归）；Python 非浏览器 **21 passed**；
原生隔离 Chrome **31 passed / 0 skipped**，不重复累计 Python 内的 Node 包装。
原生回执：`/private/tmp/atm-xyq-media-and-parked-native-20261007.xml`。
实际网站参数观察、源码经 CUA 的编辑、原生假页与安装后的 CLI 验收仍各自记录。
画布文本实验已收尾恢复，合同见 XYQ_CANVAS_EDIT_CONTRACT.md；未继续开展复杂工作区。

下一步优先结构化音色/自有音色和参考素材入口，再补三个生成流程的报价、单次提交、任务和下载。
真实上传/生成测试绑定新的确切文件、参数、报价和预算；之前 Tripo 的批准不用于小云雀。

## 最新阶段：媒体模式与音频参考上传

用户澄清音色入口是“加号上传音频作参考”，不是另外的音色库。当前细节真源：
[XYQ_AUDIO_CONTRACT.md](XYQ_AUDIO_CONTRACT.md)。保留上一节历史 7 包/零上传记录；本节取代当前状态。

新增 `mode_choices` / `mode_prepare`、`audio_form_state` / `audio_reference_upload`。
模式准备只切换完整已知空草稿；菜单标题剔除 badge，Agent 模式不在此合同中。
音频参考上传绑定文件、完整草稿、明确确认与稳定 key，持久 intent/lock 先于一次原生输入。
FileList 重置后的参考卡片仍被读取；音频节点卡片最多3个、图像参考最多1个。
同 key 复用不重传，未知结果保留锁；卡片状态不标成已验证音色效果/最终生成。

根因修复：首页 FileList 与 img/video/audio 并不涵盖所有音频/文件卡片，
草稿摘要与 preservation checks 增加实际附件 rail；带卡片的空 FileList 停止模式切换。
旧表单 pin 保留但过期，新包不覆写旧目录。

当前生成包：`generated/xyq-web-audio-reference-stage-r2/`（本机构建输出，未提交），默认 **11个**，未安装；首轮目录保留。
最新 pin：form `20c454a89e6912b1f2982ed1853c61bf5e8edc06b887b584ca0c589fb055802b`；
mode `1f43dd755ba88f1a0ec220e0377d28f70e8589eb58828c8248178ef8c09710c9`；
audio `b90b0a150403016741e29f8034723ea4fa58db2aa64eff227e6a6fa9c5760250`。
查询、暂缓画布/文本源码未改。

真实 UI：一次获批1秒合成 WAV，参考音频 0/3→1/3、积分6396保持、无生成/购买。
实际源码经 CUA/CDP 仅读已上传卡片和已知空 FileList；不是已安装 CLI 的真实上传验收。
项目音频 footer 未公开节点关联 ID，第一版只接受恰好一个音频节点；明确报歧义而非猜测。

验证：Node **85 passed**；Python非浏览器 **31 passed**；原生隔离 Chrome **41 passed / 0 skipped**。
原生模式原生点击、PCM WAV DOM 文件输入均通过 test-only RPC 执行实际工作流，全部供应商流量拦截。
回执 `/private/tmp/atm-xyq-media-audio-native-20261007-r2.xml`（初轮同名无 r2 回执保留）。
源码/假子进程/原生夹具/实际 CUA DOM/安装桥接分列，不累计成“全部功能覆盖”。

## 最新阶段：结构化音频引用与真正 CLI 只读启动

新增 `audio_prompt_prepare`，默认包数12；`--include-canvas` 为15。
当前包 `generated/xyq-web-audio-prompt-stage/`（本机构建输出，未提交），12个 `validate_bundle.valid=true`，
未安装到真实 ATM；11包旧目录保留。prompt 源码 pin：
`094f2a8475c4e60ea2ffbfec5a52ab4f6068898017fbd09f02d9f38feb8fa8b6`。
其它 source pin 未变；根/包内 SKILL 与合同同步。

真实 UI 的 @ 音频按钮插入数字 Pippit asset token，而非文件名文本。
准备器绑定确切草稿/参考摘要，原生文末光标后点击一次；已有引用零输入返回。
真实草稿的一个 token 经实际源码只读验证，模型、采样率、积分6396保留。
CUA 手工准备、实际源码零输入读取、原生假页写入、已安装 CLI 写入分别记录。
协议/隐私/草稿保护和详细状态见 [音频合同](XYQ_AUDIO_CONTRACT.md)。

原生测试首次空格失败：夹具使用 normal，而真实编辑器是 break-spaces；Chrome
原生 fill 因此插入 NBSP。修复夹具样式，保留原断言并新增 normal 样式明确报错回归。
Node **99 passed**；Python **84 passed**，其中非浏览器34、原生隔离50，零跳过。
媒体三文件69项与暂缓画布/文本15项分开执行，不重复累计 Node 包装作为新覆盖。
回执：`/private/tmp/atm-xyq-audio-prompt-node-20261007.txt`、
`/private/tmp/atm-xyq-audio-prompt-native-20261007.xml`、
`/private/tmp/atm-xyq-parked-regression-20261007.xml`。

用户明确允许已安装 OpenCLIApp 的仅小云雀只读验收后，内置 CLI 命令/doctor 已执行；
只加载一个 read 入口，没有注册上传入口。真正桥当前连到 about:blank，精确项目
读取报 `origin_mismatch`，尚未通过。已请求人工打开 App 内测试项目音频面板。
没有导出登录态、更新第三方工具、生成或扣积分；报价、单次提交、任务与下载仍待实现。

## 最新阶段：音频 footer 动态参数及遮挡修复

新增 audio_choices / audio_prepare，默认14包，显式包含暂缓画布为17包。
当前 `generated/xyq-web-audio-settings-stage-r2/`（本机构建输出，未提交）的14包全部有效，未安装到真实 ATM。
参数 pin 为 `357d3a6ed5a0795145fa1a9e5e24ed829a37c046aeb17ba826f60912d644b5d6`。
12包及初轮14包目录保留，其它旧 source pin 未变。详见音频合同的动态 ID/菜单关联/草稿保护。

真实源码发现两个模型及当前模型的六档采样率；提示词、结构化音频引用、文件与已选参数完整摘要不变。
采样率按钮中心被“添加节点”工具条盖住，实际左侧区域可命中；修复为精确控件内部点 hit test
加原生输入，完全遮挡明确报错。源码/原生假页/CUA/安装 CLI 证据仍各自记录。
标准生成与采样率真实选择未开展，不把原生隔离准备测试算成真实参数写入。

Node114通过；Python102通过（39非浏览器、63原生隔离），零跳过。
覆盖固定原生点输入、模糊/额外层清理、严格 JSON 类型、模型隐式采样率、已存在的结构化引用保留。
最终回执 `/private/tmp/atm-xyq-audio-settings-all-20261007-r2.xml`。

任务中心首轮 UI 仅显示全账户最近的对话/项目完成或中断通知；通知完成不是媒体完成证明。
详细 DOM 元数据提取因超出测试项目范围被自动审查暂停，已收起本轮打开的面板。
已请求仅仅读取全账户任务状态/类型/非秘密 ID 的范围确认，未继续提取其它项目内容。
App 内测试音频面板的人工 handoff 也仍待就绪。后续优先媒体报价、任务 ID、产物与下载，
保持图像/视频/音频三链路的目标，未把参数或工具数量作为完整覆盖。

## 最新阶段：模式菜单背景 mask 根因修复与仅只读复核

首页模式菜单展开后，Radix 将渲染中的背景标为 aria-hidden；旧普通读取返回
`page_not_ready`，清理同样超时。该次仅开菜单，模式仍为音频，未选择、上传或生成；
通过原生 Escape 收起自己的菜单。修复仅在自有模式菜单的内部快照应用严格背景规则，
验证单一弹层、互相绑定的触发器/菜单 ID 和展开状态；其它 mask 保持排除。
菜单目标也校验相同关联，无 DOM 属性变更或强制点击。细节见 XYQ_FORM_CONTRACT.md。

Node **115 passed / 0 skipped**；Python **111 passed / 0 skipped**，
其中39非浏览器、72原生隔离。新增原生 modal/non-modal 模式选择、私有草稿发现并关闭、
默认读取仍 pending、错误关联/额外弹层、独立内部 mask、只读无 DOM 变更；原断言保留。
首次隔离 Chrome 在执行沙箱内启动失败（14 setup errors），回执保留；同一测试在获准
独立测试进程后聚焦19通过，再执行六文件全回归111通过。所有网页流量均由夹具响应或终止。
回执：`/private/tmp/atm-xyq-mode-modal-focused-20261007.xml`（启动失败）、
`/private/tmp/atm-xyq-mode-modal-focused-20261007-r2.xml`、
`/private/tmp/atm-xyq-mode-modal-all-20261007.xml`、
`/private/tmp/atm-xyq-mode-modal-all-node-20261007.txt`。

最新默认14包：`generated/xyq-web-mode-modal-stage-r2/`（本机构建输出，未提交），均完整性有效，未安装到真实 ATM。
共享 core 更新使依赖它的所有 pin 更新；各旧目录和已安装独立旧只读源码保持原状。

| 最新 source pin | SHA256 |
|---|---|
| 查询 | `72acafd658bbf06c3be1457178f1d211b2732ccab8a90d221c3926df1c35fab1` |
| 表单 | `5373d3a5a09830b8588cc4a6e21cea4a46d8d59c9dd89770c5572d1ae4feb9f3` |
| 模式 | `0b40a14d59573d4f62f28591b8a87ef9f5cfbea6cf795a7f25628574a18540b2` |
| 音频读取/上传 | `f0cd688f6ae400c35a9291f24f0127808333b9d372bd15b21a2577e07105f6eb` |
| 音频引用 | `c0f214ede74873240dd45284ee8c6804505b441ef2067fd84e4ac5f807790f40` |
| 音频模型/采样率 | `f38261c1dff0e67a4f22182b1da78f13f45681cfad812c251d2bb07af8ee1049` |

本次最新实机许可仅测试项目音频表单只读，真实修复后的首页菜单复测未开展。
当前源码经 CUA 仅读测试项目，Seed Audio 1.0 / 44.1kHz、一个音频参考和一个结构化引用，
form SHA 与先前完整摘要一致；没有输入、再次上传、生成或扣积分。
当前真实已安装只读 CLI 的同一精确项目调用仍 `origin_mismatch`（exit 1），没有记为通过。
该错误表明当前 CLI 表面不在目标域；about:blank 是上一轮观察，非本次重新盘点。
等待 App 内测试面板的人工 handoff；未导出认证、扩大读取范围或加载写入入口。
回执/截图见音频合同本次复核节。全账户任务中心的额外读取许可仍待回复；未继续提取。

## 最新阶段：草稿绑定音频显示费率

新增 `xyq.web.audio_quote`，纯读取，固定项目/画布/唯一音频节点和已选 footer，
绑定 `expected_form_sha256`，两次价格读取由三次完整草稿读取包围。
实际价格控件为 `span[title="预计消耗积分"][aria-busy="false"]`，当前显示 `1积分/3s`。
保留分母3秒作为估算费率；总价和输出时长仍为 null，预算上限及最终账单验证为 false。
详细协议、忙态/未知价格及 ATM 历史请求复用语义见 XYQ_AUDIO_QUOTE_CONTRACT.md。

实际最终源码经 CUA 仅读测试项目返回 quoted_rate / unit_rate_only，显示1积分/3s。
完整 form SHA 仍为 `64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97`，
Seed Audio 1.0 / 44.1kHz、WAV 卡片和结构化引用保持，截图积分6396。
零菜单操作、输入、上传、生成或消费。源码只读不是安装后 CLI 验收。
最终 mode-600 回执 `/private/tmp/atm-xyq-audio-quote-cua-receipt-20261007-r2.json`，
截图 `/private/tmp/atm-xyq-audio-quote-readonly-final-20261007.jpg`。

当前15包：`generated/xyq-web-audio-quote-stage-r2/`（本机构建输出，未提交），全部 validate_bundle 有效，尚未安装。
新增 quote pin：`cf5ba2c6e35ff6e4213dc7e014bfcffb2d8f7697490e8199593832adb7667bbb`。
原14个工具的 source pin 与模式菜单修复阶段一致；初轮 quote stage 和所有旧包保留。
初轮报价 Node130通过；最终增加严格 ready 信封验证后 Node **131 passed / 0 skipped**。
Python **124 passed / 0 skipped**，42非浏览器、82隔离原生。新增报价文件13项，
覆盖费率单位、未知/隐藏/加载价格、重复锚点、草稿绑定、原样保留、假子进程复用及新的只读观察键。
原生仍只访问夹具，全部供应商请求响应为假页或终止；保留的画布/文本回归也全部执行。
回执 `/private/tmp/atm-xyq-audio-quote-all-node-20261007-r2.txt`、
`/private/tmp/atm-xyq-audio-quote-focused-20261007.xml`、
`/private/tmp/atm-xyq-audio-quote-all-20261007.xml`。

安装后 CLI 的 App 内测试面板 handoff、全账户任务元数据的范围确认仍待就绪，
没有通过另一条路径提取其它项目任务。单次总价、报价锁定、预算内提交、媒体任务与下载继续待实现；
不将15个包或估算费率当作完整图像/视频/音频生成交付。

## 最新阶段：显式追加音频参考与既有稿保留

`audio_reference_upload.settings.mode` 新增可选 empty / append。缺省保持原空稿保护；
仅显式自有 mode=append 逐个追加获批 PCM WAV 至最多3个音频参考，并保留已有图像卡片、
提示词/结构化引用、卡片相对顺序、模型、采样率及文件控件。继承的 mode 不开启追加。
同名、满槽、未知或非空 FileList 在 intent/input 前停止；输入仍仅一次。
写入 intent 后增加 input_preflight；草稿变化保留 lock/intent，附已完成步骤，不清稿或重传。
等待新卡片期间先核对旧稿，已有卡片不算新上传成功。完整合同见 XYQ_AUDIO_CONTRACT.md。
旧 empty 指纹及缺模式字段的结果回执仍可复用；append 单独指纹，换模式报 request_key_conflict。

新增 Node8项（音频文件从14到22项），最终全 Node **139 passed / 0 skipped**。
新增 Python11项（1假子进程、10原生）：当前八文件全回归 **135 passed / 0 skipped**，
43非浏览器、92隔离原生。覆盖1→2/2→3、一张已有图像、原生结构化引用保留、同名/满槽
零输入、提示词/卡片变化留锁、稳定请求键复用、默认/旧回执兼容、显式模式到真正假子进程。
原生网页流量全部夹具响应或终止，素材为隔离新建假 WAV，没有实际账户追加上传。
回执 `/private/tmp/atm-xyq-audio-append-focused-20261007.xml`、
`/private/tmp/atm-xyq-audio-append-all-node-20261007-r2.txt`、
`/private/tmp/atm-xyq-audio-append-all-20261007-r2.xml`。初轮全回归和生成目录保留。

当前15包 `generated/xyq-web-audio-append-stage-r2/`（本机构建输出，未提交）全部有效、未安装到实际 ATM。
查询/表单/模式 pin 不变；共享 audio 更新带动下列依赖 pin 更新：

| 当前音频 source pin | SHA256 |
|---|---|
| 表单/上传 | `99a5b1970e859d80a80fe496cf54dffcec2b98efb546c9fda5718d75ee8c5831` |
| 结构化引用 | `678c7718e170e0a9e8c49b8b1ec0d7d710f54a3259d1973b9cade04e8f19a250` |
| 模型/采样率 | `66465a24f34dff1e05438b31548999834c386832f805b938fe6a236c9bed7af1` |
| 显示费率 | `2c78060ed5961012c14e1a0bc0f33317d8f3cf5737fc63a16531c79ddd7b1fb3` |

本次当前许可仍仅测试项目音频表单只读。最终更新源码经 CUA 仅读：Seed Audio 1.0 /44.1kHz、
原一份 WAV 卡片和一个结构化引用，完整 form SHA 仍为
`64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97`，费率1积分/3s、截图6396积分。
零输入、菜单、上传、生成或消费。代码追加成功的隔离测试不是实际追加成功。
0600 回执 `/private/tmp/atm-xyq-audio-append-readonly-receipt-20261007-r2.json`；
截图 `/private/tmp/atm-xyq-audio-append-readonly-final-20261007-r2.jpg`。
已安装独立旧只读 loader 保持原样；App 面板 handoff 和全账户任务读取范围仍待确认。
真实追加/MP3/首页上传、单次总价、生成、任务和下载继续单列验收，整体目标未完成。

## 最新实机证据：模式菜单根因修复复测通过

当前实际源码 mode_choices 经 CUA 原生点击及 Escape 成功，发现 Agent / 视频 / 图片 / 音频
四项语义标题；Agent模式 eligible=false，音频仍选中。只打开/收起自己的模式菜单，
没有选择其它模式、输入内容、上传或生成。Radix aria-hidden 处理现有真实网页证据，
不再仅依赖隔离 modal 夹具。源码未因此调整，mode pin 仍
`0b40a14d59573d4f62f28591b8a87ef9f5cfbea6cf795a7f25628574a18540b2`。

前后空首页完整 draft SHA 相同：
`cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf`，
Seed Audio 1.0 /44.1kHz、文件0/0已知、无参考、生成禁用保持；截图积分6396。
独立 readModeMenuDOM 回读 mode_closed。照片仅空稿主区域，排除历史侧栏。
最终0600回执 `/private/tmp/atm-xyq-home-mode-choices-live-20261007-r2.json`，
初轮回执保留；截图 `/private/tmp/atm-xyq-home-mode-choices-live-final-20261007.png`。

本次是源码 CUA 菜单发现，而非已安装 CLI 或 mode_prepare 验收。当前代码/15包仍为
上一节追加参考快照，原139 Node /135 Python回归对应当前未变源码；仅更新验收记录和根/包内 Skill。
已请求在当前空稿临时切换图片/视频并读取默认参数菜单、最终恢复音频的范围确认。
尚未选择模式或开展该下一步；现有测试项目、单份 WAV 和已安装只读 loader 保持原样。
App 面板 handoff、全账户任务元数据范围仍待就绪，整体生成交付目标继续未完成。

## 最新阶段：空稿图片/视频默认参数及偏好展开状态根因修复

用户独立确认允许空首页临时切换图片/视频、读取默认模型参数并恢复音频。最终源码的
mode_prepare / form_choices 均经 CUA 原生输入通过，默认图片/视频各9个模型标题。
图片比例/分辨率，视频参考生成/编辑/延长/首尾帧、比例/分辨率/4–30秒时长及 Seed
随机/自定义按钮已实际发现。未选择其它模型/参数、输入内容、上传、生成或扣费。
all_options 仍 false；其它模型动态参数、Seed自定义输入和值准备不冒充已覆盖。

首轮偏好发现失败的根因：实际 trigger aria-expanded=true，但 data-state=closed。
修复读取明确展开布尔值并验证 aria-controls 绑定的唯一可见 generation面板/open状态及
模型/偏好 section。缺面板保持 pending，错误关联明确失败；旧无 aria-expanded 契约保留。
真实时长控件为 input[type=range] 而非 role=slider，读取其原生 min/max/value；
Seed按钮是 aria-pressed 而非 radio，新增纯观察 pressed_buttons，未知布尔状态报错。
没有修改DOM属性、隐藏层输入或强制点击。初轮失败后仅原生 Escape 关闭已核对自己的菜单。

最终恢复的完整空音频 draft SHA 与本次开始及原稿相同：
cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf。
Seed Audio 1.0 /44.1kHz、文件0/0已知、无参考、生成禁用保持；模式/偏好菜单关闭，积分6396。
最终0600回执 /private/tmp/atm-xyq-default-media-receipt-20261007-r3.json，
截图 /private/tmp/atm-xyq-default-media-restored-final-20261007-r3.jpg（已核对JPEG格式；错扩展名副本保留）；初轮/r2证据保留。
这是源码经 CUA 实机验收，不是安装后 CLI 通过。

本次已安装只读 audio-form-state 精确测试项目调用仍 origin_mismatch、exit1；
native App 入口仍报 native_pipe_startup_failed。已安装 read loader/旧源码保持原样，
未重装第三方软件、导出登录态或通过别的路径提取全账户任务。测试项目源码只读复核
完整 form SHA 保持64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97。
App面板人工 handoff、全账户任务元数据范围确认仍待就绪，没有重复发起这些问题。

新增15项原生隔离回归：展开状态/关联错误/缺面板、菜单关闭和稿保留、真实range
时长准备/超界保护、Seed读取/未知状态失败；均只用假页，第三方请求全部响应为夹具或终止。
最终 Node **139 passed /0 skipped**；Python **150 passed /0 skipped**（43非浏览器、107原生隔离）。
回执 /private/tmp/atm-xyq-expanded-popover-all-node-20261007-r3.txt，
/private/tmp/atm-xyq-expanded-popover-all-20261007-r3.xml；初轮及r2回执保留。

当前15包 generated/xyq-web-expanded-popover-stage-r3/（本机构建输出，未提交）全部有效，未安装到真实 ATM。
共享 core 变更带动依赖 pin 更新；已安装独立旧只读入口及所有旧目录保留。

| 当前 source pin | SHA256 |
|---|---|
| 查询 | 4183404ea6c890635af1a17d96050d6e8d4d7f8253e2ef2fe9a02cde80236f1f |
| 表单 | b84012052caf5fcbb7f37f51e89a92c9c1c8ec8617922af7c73a9897849be188 |
| 模式 | 9dc62fb67f71b7a8666fed0c04ebf111f833c95c3443b2d6bc5b645e1e578abc |
| 音频读取/上传 | dce36bd654e8746ca5cfcf74b445727aaee8fc25a83668603a1bbb621b7281ee |
| 音频引用 | 350aecf0a6caccfb6f105a621d25f602539d83c641c3887baf53c54b37c60827 |
| 音频参数 | b447d0c771ce6534d92d3ed7f5383796b541692960152e9adf22bc13363e5e68 |
| 音频费率 | ff9a3b160553d75302573e985e383a38f53ffe4a9d6b5fc3feb4d287ee0a727c |

图像/视频素材上传、其它动态参数、单次总价/生成/媒体任务/下载以及已安装 CLI 交付继续
单列待验收，未将参数发现、回归数量或15个包作为完整媒体生成交付。

## 最新阶段：显式绑定读取与真实生成 CLI 链路通过

重新盘点 OpenCLIApp0.1.38 / CLI1.8.6 / extension1.0.24：桥正常、仅一个连接 profile，
xyq-web独立页面实际为 about:blank。CUA Page.bringToFront 将确切测试页置前，
browser bind 返回 URL 精确匹配项目/画布；但普通 adapter仍 origin_mismatch。
本机运行库代码明确 browser/adapter surface 不同；公开 Page API 的 browser会话只读探针成功。
没有把 getApp native_pipe_startup_failed 当作登录丢失或继续等待它。

新增明确的 audio_form_state_bound，不替换旧入口或失败后自动换后端。
它只通过安装库公开 Page构造API读取固定 site:xyq-web browser会话，继承公开profile路由；
实际 DOM仍绑定精确项目/画布/唯一音频节点，只有evaluate能力，无 bind/navigation/input/auth读取。
详细范围和生命周期为 XYQ_BOUND_READ_CONTRACT.md。已安装仅新只读loader和旧只读loader，
其它实际写入注册入口未加载；旧源码/pin与第三方软件保持原状。

真正 OpenCLIApp __opencli_shim 新读取命令 exit0/ready。
生成 tool.py → 已安装 ATM（仅临时隔离 home）→ 已安装App → 原测试表单也通过，
同一request-key复用同一job；本机生产 ATM/vault/授权未改动。
当前 Seed Audio1.0 /44.1kHz、原一个WAV卡片/一个结构化引用，完整form SHA保持
64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97，独立源码读回一致；截图6396积分。
零内容输入、再次上传、生成或消费。此完成状态仅只读，不是供应商媒体生成完成。
最终回执 /private/tmp/atm-xyq-bound-generated-e2e-receipt-20261007.json（0600）；
截图 /private/tmp/atm-xyq-bound-read-final-20261007-r2.jpg。先前 App面板手动handoff不再是该路由门槛。

新增10项Node、4项非浏览器Python和2项原生隔离，覆盖精确pin、profile路由、拒绝错页/登录丢失、
无输入/无自动绑定、隐藏诊断、原稿/已有层保留、真实假子进程/请求复用。
原生首轮2项因测试夹具错误落到 /home 而不是 /project 失败；修正夹具路由，原断言全部保留，
r2两项通过。失败回执保留，没有放松页面范围检查。
最终全回归 Node **149 passed /0 skipped**；Python **156 passed /0 skipped**（47非浏览器、109原生隔离）。
回执 /private/tmp/atm-xyq-bound-all-node-20261007.txt、/private/tmp/atm-xyq-bound-all-20261007.xml。

当前16包 generated/xyq-web-bound-read-stage/（本机构建输出，未提交）全部有效；只有新读取包在隔离ATM安装，
未安装到生产ATM。所有旧包保留，原15工具source pin未变。
新增bound pin b1a9df91e506bfb6b2c8a715752b00365730f2e3729efb033228abbc9918288f；
definition SHA dd1f09a7db3afd0e2ca5da4d74cedccd47624daa9fd4c0a11ebdb1eda178b3ec。
全账户任务元数据许可仍待回复，没有另路读取其它项目。
真实其它CLI入口/写入、图像视频素材、自定义Seed、总价/预算内单次提交、任务与下载继续待实现/验收。

## 最新阶段：首页独立绑定、原生菜单路由及已有菜单诊断

新增首页 binding 入口复用既有 form_state/form_choices/mode_choices/mode_prepare，
编译器 --bound-home 显式修改这四个定义的注册命令与 source pin，ID及原输入/权限不变。
不新增工具数量、不静默替换缺省路由。详细契约与全部当前证据为
[XYQ_HOME_BINDING_CONTRACT.md](XYQ_HOME_BINDING_CONTRACT.md)。

原生输入边界只有经命中检查的三个模式/偏好选择器及自有 Escape；只读入口只有evaluate。
现有页面/菜单、原稿、输入文件和两个原音频只读 loader保持；认证及原生产ATM未动。
初次当前tab绑定不是首页，严格校验停止。用户置前后已精确绑定 /home，但已有模式菜单
掩罩背景；生成CLI/隔离ATM首次只读 job为submission_unknown/cli_failed，保留原回执，
不作为安装后读取通过。新增边界在实际已安装CLI立即报告 dialog_open，保留人打开的菜单；
不读取其它页面内容、不自动关闭菜单或绕过 mask。等待用户收起后继续真正空稿链路。

最终 Node161、Python174（53非浏览器、121原生隔离），全部通过零跳过。
新增12项Node/18项Python（6非浏览器、12原生隔离）；原全回归及失败/跳过快照保留。
初次pytest收集未用源码PYTHONPATH，明确失败；初轮native缺ATM_CHROMIUM显式跳过。
最终使用仓库源码及已核对Chrome路径，所有第三方请求拦截，未移除断言或改浏览器策略。
当前16包 generated/xyq-web-home-bound-stage-r3/（本机构建输出，未提交）；bound pin
c6cb485f03a7d28fb348d3c06dd620529dfe1a75a3b3202d4405ed73777e1d42。
安装前三次源码快照与包目录保留，生产 ATM 未安装。首页实际完整CLI验收仍待继续，
不把生成包/隔离测试/正确URL/明确失败报告作为参数读取成功或完整生成交付。

## 最新阶段：首页默认菜单的真实生成 CLI 八阶段通过

恢复会话时独立CUA确认原模式菜单已收起、root未mask、layers=0，原音频空稿SHA保持。
没有由工具关闭人打开的弹层。使用新临时ATM state安装四个已核对的r3首页定义，
生产ATM/vault/授权、第三方App及两个原音频read loader保持。
生成tool.py → 已安装ATM（隔离home）→ 已安装OpenCLIApp → 绑定首页，真实八阶段全部完成：
audio state / mode choices / image prepare / image choices / video prepare /
video choices / restore audio / final state；每阶段后均独立CUA读回再继续。

图片默认Seedream5.0 Pro，9个模型标题、7种比例、1K/1.5K/2K/4K；
视频默认Seedance2.5，9个模型标题、参考生成/编辑/延长/首尾帧、7种比例、
480P/720P/1080P、时长4–30秒（当前30）、Seed随机/自定义按钮。
只读默认菜单且all_options=false，不记为全部模型参数覆盖。

image阶段验收helper错误断言ready，实际产品正确prepared且job已completed。
核对当前页面后，用jobs get读取已完成job并校验产物协调image回执，没有重复模式输入；
helper按操作区分ready/prepared并在断言前保存observed-job。
共8个独立job/request-key、3次mode_input，final相同请求复用同job。
初轮submission_unknown只读失败及已有菜单截图保持历史状态，不覆盖为成功。

最终独立CUA前后全表单完全一致，draft SHA
cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf；
音频SeedAudio1.0/44.1kHz，空稿/引用0/真实文件0/0已知、开始生成禁用、所有菜单关闭；
积分6396，零上传/生成/消费。本轮回执目录
/private/tmp/atm-xyq-home-binding-e2e-20261007-r3/，独立终态回执
/private/tmp/atm-xyq-home-cli-final-cua-20261007.json；恢复截图
/private/tmp/atm-xyq-home-cli-restored-final-20261007.jpg（真实JPEG/0600）。

适配器/16包和source pin与上一阶段一致，未重跑Node161/Python174回归，沿用未变源码对应回执。
新增真实验收最终核对 /private/tmp/atm-xyq-home-cli-final-verification-20261007.json（0600）：
验证8个阶段定义/权限/产物、同job复用、独立原稿恢复，安装源码一致、其它12定义和旧loader保持。
详见 [首页合同](XYQ_HOME_BINDING_CONTRACT.md)。

下一范围为其它模型动态参数，已请求独立空稿模型切换许可，待用户回复。
参数值/bound form_prepare、自定义Seed、首页/MP3与多参考上传、真实音色效果、单次总价、
预算内提交、媒体任务/下载仍待实现或验收；全账户任务元数据许可仍待回复。
四入口和默认菜单实测通过不代表完整媒体生成目标完成。

## 最新开发阶段：首页绑定参数准备与原生选区/换行修复

`--bound-home`现为五个既有首页定义，加入form_prepare；媒体工具总数仍16、缺省路由保持。
复用既有语义字段和草稿/引用合同，桥只开放固定模型/radio/画布点击及纯文本/时长输入。
公开native快捷键的首次实测未全选，修复为固定原生selectAll并验证真实选区；
整段nativeType的LF会产生段落双换行，修复固定insertLineBreak、逐行输入及caret检查。
真实空编辑器只读样式break-spaces/p margin0用于校正夹具，NBSP差异反例仍明确失败。
非空文字逐字验证，语义空稿复用原合同；type=number选区公开证据不足时零文本替换。
详细策略/输入边界/失败及待验收为 [参数准备合同](XYQ_HOME_PREPARE_CONTRACT.md)。

最终Node168 / Python190（55非浏览器、135原生隔离），全部通过/零跳过。
新增7Node、2非浏览器Python、14原生隔离；保留沙箱Chrome初始化错误、选区失败、
换行/空格诊断和各轮回执，没有放松选区/字面回读或浏览器策略。
原生全部只用本地假页，所有第三方请求响应为夹具或终止；假子进程稳定请求只执行一次。
回执 /private/tmp/atm-xyq-bound-prepare-all-node-20261007.txt、
/private/tmp/atm-xyq-bound-prepare-all-20261007.xml。

新16包 generated/xyq-web-home-prepare-stage/（本机构建输出，未提交），source pin
7d009002f133eac8addcd459b227d0b4cfee2709c972231bad20d33658bea09b；
仅五个首页定义变化，其它11个与r3保持。新入口未加载、未安装生产ATM。
实际App仍原四入口c6cb485f...快照、两个audio read loader和第三方软件保持。
真实网页本轮只读：原音频完整SHA仍cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf，
无输入/上传/生成；0600回执 /private/tmp/atm-xyq-bound-prepare-readonly-site-20261007.json。
最终源码/包锁/回归/安装快照核对为 /private/tmp/atm-xyq-home-prepare-final-verification-20261007.json（0600）。
原四入口实机通过保持历史证据，不作为新准备入口已通过；其它模型切换许可仍待回复，
真实参数/提示词写入、number控件类型/尾部空行、Seed、音色效果、上传、总价/提交/任务/下载继续验收。

## 最新实机阶段：绑定参数准备的零输入生成 CLI 通过

更新已审阅home-bound.mjs/home-bound.js和home loader，五个首页注册入口加载，source pin仍
7d009002f133eac8addcd459b227d0b4cfee2709c972231bad20d33658bea09b。
完整旧四入口代码/loader快照保存在 /private/tmp/atm-xyq-home-prepare-installed-before-20261007/；
两个原音频read loader、第三方App、生产ATM/vault/授权保持，未加载上传或生成入口。
安装回执 /private/tmp/atm-xyq-home-prepare-install-20261007.json（0600）。

生成tool.py→新临时ATM（仅两个定义）→已安装App→原绑定空首页：
before form_state、仅expected_draft_sha256的form_prepare、after form_state，三个job全部completed。
准备结果ready/prepared=true、completed_steps=[]、options=null；没有任何参数/提示词请求，
同一准备request-key复用原job。此只验证注册/路由/合同/真实读取，不记为原生参数写入。
独立CUA前后全表单完全一致，音频SeedAudio1.0/44.1kHz、原SHA
cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf、参考0、文件0/0已知、
生成禁用/layers0、积分6396；无菜单/输入/导航/重绑定/上传/生成/消费。

真实回执目录 /private/tmp/atm-xyq-home-prepare-noop-e2e-20261007/；
独立终态 /private/tmp/atm-xyq-prepare-noop-after-20261007.json，截图
/private/tmp/atm-xyq-prepare-noop-final-20261007.jpg（真实JPEG/0600）。
最终 /private/tmp/atm-xyq-prepare-noop-final-verification-20261007.json（0600）核对3个job、
输入/定义/产物/请求复用、当前安装源码一致、旧快照/loader保持、16包锁与其它11个定义保持。
源码未变，未重跑168Node/190Python，沿用相同pin回归回执。

已独立请求同一空首页默认视频6秒/16:9/480P和两行测试提示词后完整恢复的实机写入范围；
该请求不选择其它模型、不上传/生成/扣积分，待用户回复。此前其它模型菜单请求仍待回复。
实际字段输入、音色效果、素材、单次总价/预算提交、任务/下载继续推进，完整媒体目标未完成。

## 最新实机阶段：显式绑定音频单位费率生成 CLI 通过

新增 audio-quote-bound 只读注册，复用原报价和公开绑定 Page/evaluate-only 合同；
显式 `--bound-audio-quote` 只调整既有 audio_quote 定义，缺省路由/工具ID保持且仍16包。
可与 `--bound-home` 组合；无失败后换后端、重绑定、导航、菜单/文字输入、上传或付费。
原 quote/audio-bound/home 源码闭包和两个音频read、五个首页入口/第三方App保持。
新10文件pin 8c9ca1dbac5ed34d71afd5b2413c90e3c2c3fbb0b6c8ad2d827cb1c6579a499b，
新包 generated/xyq-web-audio-quote-bound-stage/（本机构建输出，未提交）；相对上轮仅费率定义变化。

生成CLI→新隔离ATM（仅2只读定义）→已安装App→原绑定ATM-XYQ-CLI-test：
before、quote、after三个job completed；quote同请求键复用同job，不重新取价。
quote job b7f54aaf-d068-48d5-9c45-d079fe6536a7，实际返回 quoted_rate/unit_rate_only、1积分/3s；
独立CUA前后表单SHA 64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97一致，
费率摘要一致、合成WAV卡片/结构化引用保留、原首页6396积分。
只读费率回执是金额来源；面板截图的费率文字未清晰呈现，不标为文字视觉验收。
总积分和输出时长仍null，预算/最终账单验证false；零输入、上传、生成、扣分，生产ATM/vault保持。

Node176、Python201（60非浏览器/141原生隔离），全通过、零跳过。
协议测试保持typed pin/scope/settings、严格/首选路由、未知/忙态/竞态与错误不夹带私有内容；
假子进程同键仅执行一次，新纯读键才刷新观察；原生fixture完整DOM保持，供应商请求被隔离。
回归 /private/tmp/atm-xyq-quote-bound-all-node-20261007.txt、
/private/tmp/atm-xyq-quote-bound-all-20261007.xml，实机job/产物
/private/tmp/atm-xyq-quote-bound-e2e-20261007/，独立前后
/private/tmp/atm-xyq-quote-bound-cua-before-20261007.json、
/private/tmp/atm-xyq-quote-bound-cua-after-20261007.json。
安装与最终验证回执 /private/tmp/atm-xyq-quote-bound-install-20261007.json、
/private/tmp/atm-xyq-quote-bound-final-verification-20261007.json（均0600）。
细节见 [音频费率合同](XYQ_AUDIO_QUOTE_CONTRACT.md)。

实际字段写入、其它模型范围确认仍待用户回复；其它音色/素材、单次总价、预算提交、任务/下载
继续单列。单位费率读取通过不代表完整媒体生成目标完成，不借用Tripo付费批准。

## 最新开发/实机阶段：音频参数与已有引用的显式绑定

新增 `--bound-audio-edit` 接通既有 audio_choices/audio_prepare/audio_prompt_prepare，
支持与首页/费率显式选项组合，缺省schema/权限/路由保持、仍16包；只有三条定义改变。
新原生桥每次输入绑定唯一音频node/footer、关联、禁用和命中；部分遮挡只用实际有界命中点。
纯文本使用焦点/完整选区、固定编辑命令和字面回读；引用保留富提示词，原生End后验证末尾光标。
菜单Escape仅作用于本调用仍能确认的菜单；派发后异常即使业务步骤未记录也保留uncertainty。
没有任意选择器/JS/键/CDP、认证读取、重绑定、上传或付费入口，详细合同
[音频显式准备](XYQ_AUDIO_BINDING_CONTRACT.md)。

三条注册已审阅加载，原八条注册/各闭包、第三方App、生产ATM/vault保持。
source pin 5540b133586aa08216298e57f959397e6493a0b2e2615a143a4737b5468a4567，
新包 generated/xyq-web-audio-edit-bound-stage/（本机构建输出，未提交），相对费率阶段其它13定义保持。
Node186 / Python231（69非浏览器、162原生隔离），全部通过、零跳过；新增10Node、9非浏览器、
21原生隔离，覆盖参数/字面文字/多行/结构化引用、已有引用零输入及错误/遮挡/选区/菜单保护。
全套fixture拦截供应商请求，同键假子进程执行一次，浏览器策略保持。
回归 /private/tmp/atm-xyq-audio-edit-bound-all-node-20261007.txt、
/private/tmp/atm-xyq-audio-edit-bound-all-20261007.xml；安装回执
/private/tmp/atm-xyq-audio-edit-bound-install-20261007.json（0600）。

真实验收仅“同一已存在合成音频引用”零输入：生成CLI→新隔离ATM（2定义）→App→原绑定测试项目，
before/prepare/after三个job completed，prepare b59e8962-b3dd-491f-982f-2a0aa8a28566、同键复用同job。
输入只含原form SHA与reference SHA，无模型/采样率值或文字；prepared、steps=[]，不定位或追加。
独立CUA前后完整表单SHA 64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97、
prompt文档摘要一致，仍1个token、SeedAudio1.0/44.1kHz、6396积分；零菜单/输入/上传/生成/消费。
真实job/产物 /private/tmp/atm-xyq-audio-edit-bound-noop-e2e-20261007/，独立基线与终态
/private/tmp/atm-xyq-audio-edit-bound-cua-before-20261007.json、
/private/tmp/atm-xyq-audio-edit-bound-cua-after-20261007.json，最终完整核对
/private/tmp/atm-xyq-audio-edit-bound-final-verification-20261007.json（0600）。

真实菜单发现、字段/文字写入、引用追加与音色效果尚未验收，不以此零输入路径替代。
原空首页字段写入/其它模型确认仍待回复；上传、单次总价/预算提交、任务与下载继续分别推进。
完整媒体目标保持进行中，未借用Tripo付费许可，未更新用户级Skill或生产ATM。

## 最新开发/实机阶段：音频上传显式桥与旧摘要预检

新增 `--bound-audio-upload` 调整同一audio_reference_upload路由/pin/条件停止输出，
保持缺省schema/权限/16包，和home/quote/edit组合；仅一条定义变化。
原空稿/append、本地PCM WAV、完整草稿、durable intent/lock、单次原生file input与历史复用合同保持。
原生首轮8项失败定位为DOM.getDocument重新分配frontend nodeId，同backend节点被误判替换；
修复为同根重查，真实input clone仍停止，intent后未知结果保留lock且零重试。
CDP诊断、初轮失败和第二轮测试位置错误的回执保留；第三轮focused25全部通过。
具体证据/策略/输出见 [音频上传绑定合同](XYQ_AUDIO_UPLOAD_BINDING_CONTRACT.md)。

最终Node196/Python256（74非浏览器、182原生隔离），全部通过、零跳过。
新增10Node/25Python覆盖单次输入、追加1→2/2→3、图像/token保留、历史零输入、
原生节点替换、协议/文件/菜单错误、原生异常与意图后草稿变化，不以已知预检掩盖未知结果。
全部native供应商请求夹具响应或终止，同键假子进程只执行一次；策略保持。
最终 `/private/tmp/atm-xyq-upload-bound-all-node-20261007-r2.txt`、
`/private/tmp/atm-xyq-upload-bound-all-20261007-r2.xml`，source pin
5b84f42acb11b641bd025875399c79e743570cc1b820d2229f3da0dcda1bd4d5。
新包 `generated/xyq-web-audio-upload-bound-stage-r2/`（本机构建输出，未提交）相对准备阶段其它15条定义保持。

一条reviewed音频上传注册已加载，原11条/各闭包、App、生产ATM/vault和用户级Skill保持。
生成CLI→新隔离ATM（2定义）→App→原绑定测试表单，before/预检/after三个completed job，
预检7b80d7d4-6f86-4b3b-ae37-7576acac524c返回upload_rejected/draft_changed/preflight，
steps=[]、native_file_input_sent=false、upload_accepted=false、outcome_uncertain=false，
未建active.lock/intent；同键复用同job。completed只表示预检检查完成，不是上传成功。
新建合成WAV仅本地校验，故意全零旧摘要在input前停止，未使用新的上传许可。
独立CUA/CLI前后全稿SHA64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97，
文档/原卡片/单token保持、6396积分；零输入/上传/生成/扣分。
实机产物 `/private/tmp/atm-xyq-upload-bound-preflight-e2e-20261007/`、前后独立回执
`/private/tmp/atm-xyq-upload-bound-cua-before-20261007.json`、
`/private/tmp/atm-xyq-upload-bound-cua-after-20261007.json`，最终核对
`/private/tmp/atm-xyq-upload-bound-final-verification-20261007.json`（0600）。

真实CLI附件成功、追加及音色效果仍待新文件范围确认，未重复使用已消耗的单WAV批准。
参数值/其它模型许可、首页/MP3/多模态参考、单次总价/预算生成、媒体任务与下载继续单列。
本轮只完成上传桥和真实负例路径，不代表完整媒体生成目标已完成。

## 最新开发/实机阶段：首页图像、视频、音频显示报价

新增`xyq.web.home_quote`只读定义，编译默认17包；原16条定义/pin/路由全部保持。
明确绑定site:xyq-home/browser，三组price和完整draft交错核对，不开菜单/导航/输入或读认证。
实际主页价格slot为唯一amount，视频划线originalAmount独立核对；不是拼接全部innerText。
缺失/忙态/未知分列，rate保持每秒精度；quoted_estimate仍只是显示预估，
total_credits/output_duration_seconds保持null，预算硬上限/计费范围/最终账单验证false。
源闭包pin4d14f22835161254af05445445c9f4ed0fd838c9d4ca27ba1868e6a0629832cc，
17包 `generated/xyq-web-home-quote-stage/`（本机构建输出，未提交）；合同 [首页报价](XYQ_HOME_QUOTE_CONTRACT.md)。

先行CUA现场观察发现模式切换后价格异步消失，第一轮恢复比较只在成本观察上不同，
原草稿SHA已一致；保留失败回执，等待价格实际出现后完整音频稿一致，没有重复生成。
图片默认5.0Pro/1K显示6，视频SD2.5/30秒/720P当前600/划线780，音频SeedAudio1.0显示0.33/秒。
全部是当时空稿默认模式读数，不推断其它模型/提示词/音色或最终账单。

最终208Node/285Python（79非浏览器、206原生隔离），全通过、零跳过；新增12Node/29Python。
Focused两项隐私失败定位为测试RPC夹带旧读器raw成本调试字段，改为只返回所需基线digest，
新报价数字/摘要输出与原隐私断言保持。全套首轮旧绑定ID枚举漏新定义1失败，
明确加入新home_quote预期，保留原16条严格定义/路由断言；历史失败不覆盖。
供应商请求均夹具响应或终止，所有只读测试完整body保持/零生成，浏览器策略保持。
回归 `/private/tmp/atm-xyq-home-quote-all-node-20261007.txt`、
`/private/tmp/atm-xyq-home-quote-all-20261007-r2.xml`。

只新增1个reviewed首页报价注册，原12条/各闭包、第三方App、生产ATM/vault与用户级Skill保持。
生成CLI→新隔离ATM（3定义）→App→原空首页9阶段通过：状态、音频报价、
图片默认模式/报价、视频默认模式/报价、恢复音频、final状态/报价；只有3次mode_input。
图片6、视频当前600/原780、音频0.33/秒；final-quote
f32d6942-7594-44f5-b9ee-c2c7b8c69761同键复用同job/result。
独立CUA与前后CLI完整原稿SHA cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf，
音频quote SHA6fd62ef76e71c4ef08185541126f47bcfe605d2ff24425c4f48afeade655fe6f保持、6396积分。
无文字/参数值/文件输入，零上传/生成/扣分；原空稿/文件0/菜单关闭已恢复。
真实job/产物 `/private/tmp/atm-xyq-home-quote-e2e-20261007/`，独立终态
`/private/tmp/atm-xyq-home-quote-cli-cua-after-20261007.json`、截图
`/private/tmp/atm-xyq-home-quote-cli-restored-20261007.jpg`，最终核对
`/private/tmp/atm-xyq-home-quote-final-verification-20261007.json`（0600）。

本轮完成三种默认模式显示报价，实际其它参数/模型、新文件上传/音色效果、硬预算单次提交、
任务/下载仍逐项推进。前述范围确认待回复，完整媒体目标保持进行中，未消费积分。

## 最新开发/实机阶段：精确项目生成历史视图

新增xyq.web.project_history_state，默认18包generated/xyq-web-history-stage/（本机构建输出，未提交）。
原17条完整定义/各闭包保持；固定site:xyq-web/browser的公开evaluate-only路由，
schema仅精确project_id/canvas_id，仅读当前视图，不开关层/切筛选/导航，不解析未知任务行。
真实“生成历史”trigger/dialog、四media tabs/受控tabpanel及生成状态filter关联均核对。
测试项目当前“全部媒体/成功”筛选为明确empty，不代表全项目/全账户无任务。
关闭/加载的数量为null；task_count=null、all_records/row_scope_verified/task_rows_parsed=false。
有真实行时unsupported_history_records，错页/重复控件/其它层/竞态保持明确失败，
没有用全账户TaskCenter或内部接口替代。详见[项目生成历史合同](XYQ_PROJECT_HISTORY_CONTRACT.md)。

源闭包8文件pin ef9de8acd17f8c999d5367440cadbfeb6e9f0f87be39863b0597bbd087d23ac5，
新增1条reviewed只读注册，原13条/各原闭包/App/生产ATM/vault/用户级Skill保持。
最终Node218/Python316（84非浏览器/232原生隔离），全通过零失败/跳过；新增10Node/31Python。
覆盖真实可见空态标签、动态media/status、closed/loading区别、严格上下文、未知行停止、
双快照竞态、权限和同键复用；供应商请求仅隔离夹具响应或终止，浏览器策略保持。
回归/private/tmp/atm-xyq-history-all-node-20261007.txt、
/private/tmp/atm-xyq-history-all-20261007.xml。

生成CLI→新隔离ATM（1定义）→App→测试项目真实两阶段通过：
open job0cd4b5be-e924-4e98-ac04-99f2944fc5ec返回history_empty/visible_count0；
同键复用同job/result。CUA仅关闭自有历史popover后，
closed jobc952c05b-986f-4f0a-8be0-19f011a429d1返回history_closed/数量null。
均只授execute_code、paid_granted=false，artifact路径/大小/SHA/JSON逐一通过；CLI零输入。
独立CUA前后全音频form SHA64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97，
原合成素材卡/结构化引用/模型/采样率/原稿保持，原首页全稿SHA cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf保持。
当前两页面显示6430积分，上一阶段6396仅历史读数，原因未查，不当作本轮余额未变证据。
余额观察器首次将项目页标签用于首页而超时，按实际数字banner按钮定位后成功；
没有改源契约、生成重提或其它账户调查。本轮零上传/生成/下载/付费提交。
真实job/产物/private/tmp/atm-xyq-history-e2e-20261007/、独立终态
/private/tmp/atm-xyq-history-cli-cua-after-20261007.json、恢复截图
/private/tmp/atm-xyq-history-cli-restored-20261007.jpg、最终核对
/private/tmp/atm-xyq-history-final-verification-20261007.json（0600）。

实际行project/task ID/状态/结果与媒体下载尚未验收；新独立图片节点准备、
由用户最终生成一次的范围已询问待回复。本轮未新建节点/写入新提示词/上传或提交。
其它模型/参数、音色实际效果和硬预算提交仍分别推进，完整媒体目标未完成。

## 最新开发/本地实机阶段：媒体字节与完整解码交付组件

新增独立xyq.media.artifact_inspect单包与源码atm media inspect，不改变原网页18定义、
各闭包、浏览器绑定或注册。合同[本地产物校验](XYQ_MEDIA_DELIVERY_CONTRACT.md)。
项目相对路径/普通单链接文件/expected SHA绑定，逐级no-follow打开，检查完整容器和实际解码，
末尾重开完整路径验证祖先/叶身份并重新核对字节；HTML、伪后缀、截断、竞态明确拒绝。
PNG/JPEG/WebP执行verify后重新打开/load，PCM WAV遍历全部帧，MP3/MP4核对帧/box边界后
使用固定hash-pinned FFprobe字段白名单与FFmpeg完整解码，只允许fd输入，MOV外部引用关闭。
容量/像素/时长/进程/诊断有界；stderr/tag/EXIF/提示词不回传。依赖/崩溃/超时/协议错误分开，
不会把仅probe成功说成完整媒体，也不会把条件负例说成有效交付。
源pin7ea6f054a0568b17de0554e44ad35c1b2027c968dfda11218b04c5782b292efd，
本机definition SHA3f5d83af53a1ffcb8a50654b0b9738e995ca1f0832e259f2e08c3cacd2c629a4，
包generated/xyq-media-delivery-stage/artifact_inspect/（本机构建输出，未提交）。既有Pillow12.3.0/FFmpeg8.1.2未升级。

新增56本地/真实子进程测试；小云雀+CLI+quickstart扩展422通过、零失败/跳过，
含原232原生隔离浏览器。既有Node源未变，原218通过回执与当前各闭包仍一致。
focused初轮2失败是-m仅导入cli模块，修正到原__main__入口，退出码/JSON断言保留。
扩展初轮3失败为/var临时目录符号链接保护和README106行；TMPDIR规范为/private/tmp，
README恢复90行、细节归入合同/Skill，原断言/保护保持。首次扩展期间有最后duration补充，
最终以fresh r2回归为准，历史失败不覆盖；
/private/tmp/atm-xyq-media-delivery-all-20261007-r2.xml及txt。

实际生成CLI→隔离ATM→仓库源码ATM包装→真实解码器：六个合成格式通过，7个不同job（含新键负例），
无返回固定媒体结果的假程序。每个job权限/媒体SHA与输出artifact路径/字节数/SHA/JSON核对。
改变测试PNG后同键复用原历史结果，新键artifact_rejected/media_hash_mismatch/valid=false，
直接CLI负例退出2；原图副本保留。未读取浏览器/认证文件/Key，未上传/生成/下载或付费。
生产ATM来自pipx site-packages，本轮没有安装升级生产包、Skill或浏览器注册。
实际回执/private/tmp/atm-xyq-media-delivery-e2e-20261007/verification.json，
最终核对/private/tmp/atm-xyq-media-delivery-final-verification-20261007.json。

artifact_verified仅本地字节/解码证据，provider_generation_verified/task_association_verified/
download_verified=false；它不是实际网页产物交付。真实task/下载事件/落盘后校验仍待，
图片准备与用户最终生成的确认未收到；完整媒体目标保持进行中。

## MP3 参考上传源码与隔离验收

同一audio_reference_upload现校验 PCM WAV/有界MPEG Layer-III MP3，再走原
empty/append、exact-form、单文件intent和回读；无新增权限/工具ID/schema/生成入口。
帧样本时长含编码padding，不是解码时长或报价。首页过滤器有MP3，节点accept=null；
真实节点接收尚待独立文件许可，不从无过滤声明推断任意格式可用。

最新18包见本页顶部；3个适配源码文件变化导致14个定义pin/格式说明更新，4个基础定义保持。
原已安装78个源码文件和history阶段90个文件保持，生产ATM/App/用户级Skill未升级。
最终248 Node/434 Python全部通过，新增30/12；包含5份真实本地合成编码+独立解码，
以及原生隔离MP3一次输入、已有WAV/token/图片保留、历史复用零重传、满槽/截断/未知保护。
夹具接收不等于供应商接收，网页MP3、真实音色效果、生成、实际task/result和下载仍待。
最新pin/全部回执真源为 [MP3参考合同](XYQ_MP3_REFERENCE_CONTRACT.md)。

随后仅升级已有显式上传注册到MP3版本（旧9文件备份，编辑5文件，其余13注册/69源码保持）。
最终上传c70aa32 pin，新18包相比上个MP3快照仅上传定义pin变化；其余实际入口保留旧pin。
当前Node248/相关Python97通过；生成CLI→隔离ATM→已安装App的MP3旧摘要预检通过，
upload_rejected/draft_changed，不是上传成功。零原生文件输入/intent，同键同job，
原音频节点/WAV/token与空首页完整摘要前后保持，生产ATM/用户级Skill未升级。
安装、真实链路、失败诊断和最新回执均见 MP3参考合同末节；实际附件和媒体生成交付仍待。

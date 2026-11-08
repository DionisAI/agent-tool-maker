# Tripo Studio 网页 CLI

当前完整覆盖审计、未接入入口及 DOM 驱动二次调整见 [覆盖报告](TRIPO_STUDIO_COVERAGE.md)。
“达到 computer use 操作能力”的持续目标与逐项完成门槛见 [对齐合同](TRIPO_UI_PARITY.md)。

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
| `tripo.studio.workspace_inspect` | code | 观察 12 个工作区模块的源资产、设置、选项、警告与明确/未知报价 |
| `tripo.studio.workspace_prepare` | code + write | 设置 Segment/Texture/Magic Brush/Upscale/PBR 的受审阅参数，不提交 |
| `tripo.studio.workspace_submit` | code + write + paid | 上述五类有明确报价的模型操作，按源资产/报价/预算单次提交 |
| `tripo.studio.assets_query` | code | 模型各筛选/Collected、单图/多视图查询，逐轮检查范围，显式 partial |
| `tripo.studio.image_preview` | code | 核对指定图片及视图，读取预览信息，只关闭自己开的预览 |
| `tripo.studio.animation_inspect` | code | 动画源前置、草稿/时长、按钮报价、当前渲染预置；不应用或生成 |
| `tripo.studio.animation_prepare` | code + write | 填写动画提示词/1–10 秒并回读；替换/清除原草稿需其摘要 |
| `tripo.studio.export_options` | code | 打开自己管理的导出弹窗，读取格式/纹理和动态选项后关闭；不下载 |
| `tripo.studio.export_prepare` | code + write | 准备六格式、纹理、骨架、FBX 变体/OBJ 顶点色，回读后关闭；不点保存/下载 |
| `tripo.studio.viewer_inspect` | code | 查看器、环境与层级的可见状态；恢复侧栏，只关闭自有环境浮层 |
| `tripo.studio.viewer_prepare` | code + write | 七种有效渲染模式、线框/网格、六环境及数值/自动旋转，回读验证 |
| `tripo.studio.viewer_camera` | code + write | 有界原生旋转/平移/缩放/重置；输入成功与画面验收分开 |
| `tripo.studio.hierarchy_prepare` | code + write | 按准确节点名称选中/显示/隐藏；隐藏会清除选择 |
| `tripo.studio.hierarchy_transform` | code + write | 对已选节点以旧状态摘要绑定 XYZ 位置/旋转/缩放；可能自动保存 |
| `tripo.studio.image_form_inspect` | code | Generate Image 草稿、模型/模板、比例/数量/4K 可用状态；不上传或生成 |
| `tripo.studio.image_form_prepare` | code + write | 以精确草稿摘要绑定图片生成表单设置，回读并报告模型引起的隐式变化 |

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

工作区另有 3 包在 `generated/tripo-studio-workspace/`，正式注册总计 18 项。
工作区摘要覆盖旧 8 文件和 workspace.mjs/workspace.js，旧 15 包不随这次更新改写。
侧栏实际折叠的子项先点已观察的可见父项再进入，不把零高度误判为资产禁用。
workspace_inspect 对按钮无报价返回 quoted_credits=null；动画预置与主表单分开报告。
workspace_prepare 仅接受对应模块的细节/分辨率/提示词/Remove Lighting/Creativity；
替换或清除现有提示词需要 expected_prompt_sha256，回读实际表单验证变更。
workspace_submit 仍复用原 unknown 上传锁，不跨工具绕开；其真实付费结果尚待验收。

资产查询独立 2 包在 `generated/tripo-studio-asset-query/`，已注册总计 20 项。
`assets_query` 的 category/ownership/filter 必须是观察到的组合：Model/My Assets
支持 All、Smart Mesh、Untextured、Textured、Rigged；Model/Collected 不显示筛选控件，
输入 filter=All 仅表示不筛选，输出 filter=null；Image/Image Assets 支持 All、multi-views。
limit 1–1000、max_pages 1–50；每次回读验证选中范围，用嵌套滚动容器的哨兵加载。
没有观察到权威结束/空态契约时始终 partial、all_assets=false；零卡片保持 pending，
不把加载或漂移写成成功的空列表。card_id 对单图为 image:TASK:INDEX（image.png 用
single），多视图为 multiview:TASK，四个不同视图归为一卡；Model 仍是 preview_task_id。
不输出签名 URL 或凭据，不把图片 task ID 当模型 UUID。

`image_preview` 输入 card_id、view_index；单图用 view_index=0，多视图用 0–3。
通过已观察卡片进入预览，验证准确 task/index，再读取模型名称和 Image dimensions
对应的比例。关闭自己打开的预览；已有可见浮层保持原状。Generate HD Model /
Generate Smart Mesh 仅列出，不提交。图片下载/编辑/转 3D 另验。
查询摘要覆盖 core.mjs、asset-query.mjs、asset-query.js；原 18 工具的源/定义不改写。
新增两个工具仅 execute_code，不需要 vault Key、external_write 或 paid。
滚动后实际类别按钮会被固定导航挡住；先检查中心点命中，必要时 focus + Home
回到真实嵌套滚动容器顶部，再验证命中后点击。未解除遮挡报 control_obscured，
不发送误点。关闭自己打开的图片预览后移到 All，等待关闭动画，并仅处理本次
引发的已知 Creator 说明浮层；Escape 后仍将鼠标留在头部会让该浮层再次弹出。

工厂脚本固定加载本工程的 src；进程若已缓存其他 ATM 包则明确报错，避免误用
已安装旧工厂的临时目录清理行为。构建失败保留现场，升级安装另属运行时维护。

动画/导出选项独立 4 包在 `generated/tripo-studio-ui-options/`，正式总计 24 项。
动画准备仅支持 prompt、duration 1–10、expected_prompt_sha256；已有绑骨源的
空草稿与未绑骨源分开报告（draft_empty / rig_prerequisite_missing），不以禁用
Generate 推断所有模型都缺绑骨。报价随可见按钮读取，返回 ready 仍不是完成动画。
预置列表仅当前渲染范围，不声称全部预置或自动应用；动作生成/播放/下载另验。

导出选项按实际菜单接受 USD、FBX、OBJ、STL、GLB、3MF；texture_resolution 为
512/1k/2k/4k/8k。export_skeleton 仅实际可用时设置；fbx_variant 为 Blender/Mixamo/
3dsmax 且仅 FBX；vertex_colors 仅 OBJ。准备是自有弹窗中的临时设置，回读后关闭，
不点击保存、不触发 Send To/Export、不生成付费回执；options_sha256 不是旧 export 工具
的 quote_sha256。未定价的选项观察保持 quoted_credits=null，不据此推断免费。
已有弹窗留给人；布局/遮挡/源资产变化明确失败，失败后的自有弹窗关闭另验证。
实际页面会记住部分已准备选项；关闭自有弹窗不等于恢复默认值，任何后续操作
先重新读取选项。下拉框逐一验证 format/texture 类型并等旧列表关闭，避免关闭动画
把上一个格式列表误当纹理列表。使用已观察的关闭图标，不以 Escape 发出算关闭成功。
旧 GLB export_quote/export 不扩成多格式；其它格式的完成文件验收仍待进行。

已有绑骨源 Rig 表单提供与侧栏 Animate 相同 href 的快捷链接。导航先按语义
唯一定位，再把匹配序号绑定到同 href 点击，避免选择器歧义；这是工作区共享根因
修复，所以 3 个工作区定义及新 4 包重新审阅，原 15 项和资产查询 2 项保持原摘要。
随后实际 Quad 源显示单值 Faces/Vertices，旧完成状态仅识别 current/total；共享
状态解析补齐两种实际格式，拒绝未知/非整数/不安全数值。这个根因修复也影响
11 个扩展定义，已独立 CAS 审阅；因此本阶段最终保持原摘要的是基础 4 项与
资产查询 2 项，不把早期“旧 15 不变”的阶段证据当最终状态。

## 人的体验

查看器/层级独立 5 包在 `generated/tripo-studio-viewer/`，正式总计 29 项。
查看器摘要覆盖工作区 10 文件和 viewer.mjs/viewer.js；更新新 5 项时原 24 项
定义及源摘要逐项保留。每个工具绑定准确的已完成源 UUID，现有弹层留给人。

`viewer_prepare.settings` 接受 render_mode=solid/pbr/normal/unlit/toon/sketch/hologram、
wireframe、grid 和 environment（surrounding=Beach/Desert/Forest/Interior/Night/Studio，
strength 0–2、rotation 0–360、auto_rotate）。实际只有 Solid/PBR/Normal 基础组互斥；
Unlit/Toon/Sketch/Hologram 是 PBR 特效，选中时 PBR 同时保持按下。关闭特效可能
恢复先前 Solid/Normal；恢复普通 PBR 要关闭准确特效，再回读并选择基础 PBR。
此处 render_mode 表示最终有效模式，不是伪造七个按钮互斥。线框与网格独立。
Auto Rotate 会持续改变可见 Rotation。设置起始角度时先停转、原生输入并回读，
再开启/恢复旋转；`environment.rotation_preparation` 记录 requested、verified_value、
auto_rotate_after。最终 settings.rotation 返回实际动态角度，不伪报为固定起点。
关闭 Auto Rotate 后则按固定角度完整验证。缺少起点回读或其它字段变化仍报错。

`hierarchy_prepare` 的 node_name 来自实际渲染层级，settings 支持 select=true、
visible；隐藏会清除选中，select=false 的清除操作未观察，暂不接受。层级只代表
当前渲染范围，不宣称全部节点。`hierarchy_transform` 需要该节点已经选中及
expected_transform_sha256，position/rotation/scale 每组三个数，精度两位小数。
绝对值 1000000 是本工具审阅的输入边界，不声称所有值都在真实 UI 验收过。
文本数值经原生 Tab 提交并逐项回读。没有点击 Save 不等于没有持久变化：本次
测试字段改动后源卡片时间更新，可能自动保存。只在批准的蓝色立方体夹具测试，
恢复确切原向量；服务端几何持久化与重新下载仍是独立验收。

`viewer_camera.action` 为 reset、orbit_left/right/up/down、pan_left/right/up/down、
zoom_in/out。对模型画布命中预检后发出固定有界原生输入，失败也释放鼠标。
返回 camera_pose_exposed=false / input_dispatched；具体视角、质量和每个手势的
画面效果另行验收，既不读取隐藏引擎状态，也不将原生输入回执当精确姿态证明。
五工具都不提交生成、上传、导出、Share/Feature 或节点 Delete。

图片生成表单独立 2 包在 `generated/tripo-studio-image-form/`，已注册总计 31 项。
该组覆盖工作区 10 文件和 image-form.mjs/js，原 29 定义与源摘要逐项不变。
这不是 `image_quote` / `image_generate` 的图片转 3D。准备要求
`expected_draft_sha256`，绑定源 UUID、完整设置、参考图片与实际 FileList 计数。
模型为 GPT Image 2/2.5、Nano Banana Pro/2/基础版、Midjourney v8.2；比例为
1:1、16:9、9:16、4:3、3:4 或 null（无选中），数量 1–4，4K 布尔，提示词
0–10000 字符。九模板按实际渲染选择，template=null 清除；不上传参考文件。
模板列表只代表当前渲染分类，不声称所有未来类别或全部模板已经覆盖。
Midjourney 隐藏比例、数量、4K 和一个空上传控件。隐藏选项返回 null；
`implicit_changes` 报告设置变化，`implicit_control_changes` 报告已观察的空控件
1↔0 变化；非空文件丢失、参考变化及其它控件形状变化仍报错。比例按钮悬停时
文字会消失，故以已观察的 value/data-state/aria-pressed 核验，不猜文字定位。
实际固定页脚可能遮挡 4K：先按已观察路径聚焦准确开关并按 End，再重新核对
中心点命中，仅命中恢复后单次点击；仍有遮挡则明确失败。
`resolution_preparation` 记录 viewport_repair、requested 与实际 verified_value。
读取只关闭自己打开的选择层；既有弹层保持原状，草稿变化明确失败。
Free 14/1000 与表单旁数值只是计费观察，`quoted_credits=null`；不据此点击生成。
实际图片生成/编辑/放大/Cutout/多视图、下载文件与画面质量仍分别验收。
2026-10-04 同一最终源码的 35 项真实表单矩阵、独立画面与原草稿恢复通过；
原生 4K smoke 另 3 项通过，包含实际 focus_end 视口修复。完整证据与未完成
边界见 [对齐合同](TRIPO_UI_PARITY.md#前台恢复后的图片表单最终验收-2026-10-04)。
自有选择层关闭卡住时保留失败和草稿，先核对准确 CLI 标签页的可见性；账号
显示核对页可能是另一标签，不将它当作 CLI 结果。不得只凭 closed 状态放行。

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

## 当前分阶段状态

上述 15 项为历史验收。现有 29 项还包含工作区 3、资产查询 2、动画/导出选项 4、查看器/层级 5。
最新摘要、真实失败修复、逐项原生复测与剩余缺口以
[操作对齐合同](TRIPO_UI_PARITY.md) 为准。动画草稿和多格式选项已接入不等于
动画产物或六种格式文件均验收；旧未知上传锁保留，新付费决定单独等待。

查看器/层级新增 5 项已在最终摘要下通过 41 条真实调用，另逐张验看 11 个相机
动作的实际画面并复位；PBR 特效组合与动态旋转已按网页差异修复并真实复测。
此前 r1–r4 失败、最终 r5 通过和精确姿态/持久几何等剩余边界分别记录在合同末尾；
本阶段验收不代表全网站、所有模型质量或付费结果完整覆盖。

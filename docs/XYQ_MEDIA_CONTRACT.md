# 小云雀媒体生成 CLI 合同

2026-10-07，用户最新范围：专注**图像、视频、音频生成的网页功能对齐**。
本合同是当前范围真源，取代此前“完整网站”的本期验收范围。
白板/画布编辑、故事板、3D 导演台、复杂时间线暂缓；既有源码与证据保留。
Pippit 只作实现参考，命令数量不作为网页能力覆盖证明。

最新实机门槛：用户已确认额外合成 MP3 测试；一次真实 CLI 追加返回
`submission_unknown`，原请求与操作锁保留、原 WAV/token/稿摘要保持。
公开文件选择器桥修复已安装到单个既有 OpenCLI 入口并隔离验收；未自动重传，
附件接收、音色效果和生成/任务/下载仍待实机验收。详细状态以 MP3 合同末节为准。

## 三个生成流程

| 流程 | 必须逐项核对网页并接入的能力 |
|---|---|
| 图像 | 文生图、参考图/多图、网页提供的编辑入口、模型、比例、分辨率、其它动态参数、任务、图片下载 |
| 视频 | 文生视频、图/视频/音频参考、首尾帧、编辑/延长、模型、时长、比例/分辨率、声音、Draft/成片、任务、视频下载 |
| 音频 | 音乐/音效/人声等网页实际模式、模型、采样率、指定音色、自有音色/参考音频上传与引用、其它动态参数、任务、音频下载 |

用户已澄清本期“上传音色”指 **加号上传音频，作为音色/音频参考**，不是新建独立音色库。
音色不得降级为提示词里写一个名字。若网页有结构化音色选择、已有音色库或自定义音色流程，
CLI 应绑定实际可选 ID/名称与当前状态并回读验证。参考上传、引用准备和实际音色效果分别验收，
文件输入接受音频格式并不证明已有克隆音色/指定音色功能。
语言、语速、情绪、音高、seed、数量等字段仅在相应模型的实际网页中观察到后接入；
未知、禁用和不支持明确区分，不猜模型枚举或伪造已应用参数。

## 操作链路

1. 读取登录、额度、当前模式、模型/动态选项和草稿摘要。
2. 在确切草稿上准备模式与参数；保留用户原稿，切换会清稿时先报告冲突。
3. 上传绑定用户明确选定的文件、目的和所在项目；校验规则文件/摘要/类型/大小，
   文件内容及认证状态不进入聊天。普通参考、音色样本和可能收费的音色创建分别处理。
4. 报价绑定内容、素材、音色、模型和全部实际参数；未知报价保持未知。
5. 生成须独立批准本次内容与预算；持久化提交意图、稳定 request-key、单操作锁后仅提交一次。
   模糊结果先核对上游任务，不换后端或换 request-key 重提。
6. 任务区分 submitted / pending / needs_input / completed / failed / submission_unknown。
   完成通知不是文件交付；下载到明确项目路径并检查类型、摘要和媒体信息。

模式/参数、素材发现、音频参考上传、报价、单次提交及图片结果/下载已分别接入工具；
生产安装与每项真实网页/完成媒体验收分列，不依据安装数量判定上述链路全部完成。

## 当前事实与待验证项

2026-10-08：生产 ATM 共27项 `xyq.web.*`，其中20项媒体运行时、3项图片结果读取、
2项图片下载、2项首页素材发现。具体定义、pin 与边界分别见
[运行时](XYQ_MEDIA_RUNTIME_CONTRACT.md)、[结果](XYQ_RESULT_CONTRACT.md)、
[下载](XYQ_DOWNLOAD_CONTRACT.md)、[素材发现](XYQ_HOME_MATERIAL_CONTRACT.md)。
首页实际 CLI 读取格式/三项素材菜单和已有会话图片结果通过；完整原稿保持，临时绑定已解除。
声明 WAV/MP3 接受格式仍不是上传、声音效果或完成音频。原 MP3/图片下载未知状态、
独立音频项目 origin_mismatch 保留；真实生成、非默认参数全量覆盖与视频/音频结果/下载仍待验收。

## 阶段记录（2026-10-07）与未完成验收

- 十八个媒体阶段工具：account / surface / form_inspect / form_options /
  form_state / form_choices / form_prepare / mode_choices / mode_prepare /
  audio_form_state / audio_form_state_bound / audio_reference_upload / audio_prompt_prepare / audio_choices / audio_prepare / audio_quote / home_quote / project_history_state；已实现源码与生成包，
  未安装到生产 ATM。显式绑定读取入口已在隔离 ATM 状态和已安装 OpenCLIApp 上端到端只读通过；
  已安装 OpenCLI 保留原两个音频读取入口，新增显式绑定单位费率入口，另有五个首页显式状态/菜单/模式/准备入口；
  首页四个入口已通过生成 CLI → 隔离 ATM → 已安装 App → 真实首页的八阶段默认菜单链路，
  原音频稿完整恢复、积分6396、零上传/生成。其它模型和生成交付继续单列，
  详见 XYQ_BOUND_READ_CONTRACT.md 和 XYQ_HOME_BINDING_CONTRACT.md。
- 当前 `--bound-home` 编译加入既有form_prepare，为五个显式首页定义（home_quote阶段17包，新增history视图后18包）。
  新准备桥的原生模型/radio/时长/画布/纯文本及焦点/选区/逐字回读隔离测试通过；
  实际App现加载五入口新源码，原四入口完整旧快照保留；新准备入口的生成CLI仅摘要零输入通过，
  ready/prepared=true、完成步骤为空、同job复用，原稿/6396积分保持。参数值真实写入待范围确认。
  新source pin、number选区未知和真实写入门槛见 XYQ_HOME_PREPARE_CONTRACT.md。
- 当前表单准备覆盖已有创作模式中的动态模型/radio、视频时长、画布开关和纯文本提示词；
  模式工具绑定已知空草稿，拒绝带附件/提示词的切换并报告模型/画布默认变化。
  首页草稿摘要已包含附件 rail，上传后清空 FileList 的音频卡片也参与冲突判断。
  模式菜单的 Radix 背景 mask 仅在已验证的自有菜单快照中读取；普通读取不变，
  保留网页属性，使用原生命中输入。隔离回归与真实菜单复测分列，见表单合同。
  音频节点 WAV 参考上传见 XYQ_AUDIO_CONTRACT.md；草稿绑定的显示费率见 XYQ_AUDIO_QUOTE_CONTRACT.md。
  上传缺省保持空稿保护；显式 append 逐个追加至最多3个音频参考并保留既有提示词/token/图像参考。
  追加的源码和隔离回归与真实追加验收分开，原批准的单份 WAV 不重复上传。
  显示费率保留每秒单位，总价、单次提交和媒体交付仍待实现。
  显式 `--bound-audio-quote` 保持同一工具ID/缺省路由，新的评估只读入口已通过生成CLI→隔离ATM→
  已安装App→精确测试音频表单：1积分/3s，前后完整草稿与引用保持、同job复用、原首页6396积分。
  实机只证明单位费率读取，不代表任何生成/预算/最终账单验收；详见费率合同。
  显式 `--bound-audio-edit` 接通既有音频菜单/参数/提示词引用三路由，新增原生桥隔离测试通过；
  三条注册已加载，生成CLI→隔离ATM→App的已有引用零输入核对通过，原全文/引用/积分保持。
  此路径零菜单/光标/文字/参数输入；实际菜单/改值/引用追加仍待实机验收，见 XYQ_AUDIO_BINDING_CONTRACT.md。
  显式 `--bound-audio-upload` 接通同一既有上传定义，单独加载一条注册，保留原11条及生产ATM。
  隔离原生上传/追加和真实input替换保护通过；生成CLI→隔离ATM→App只验收旧摘要的预检停止，
  返回 upload_rejected/draft_changed、零原生文件输入，同键复用同job，原完整表单/引用/6396积分保持。
  本轮新建WAV只在本地校验，未传到网页；真实CLI上传成功路径与新文件许可另列，
  不把completed预检job解释为上传成功，详见 XYQ_AUDIO_UPLOAD_BINDING_CONTRACT.md。
  空首页模式切换和默认图片/视频参数菜单在独立批准范围内经最终源码 CUA、生成 CLI 链路通过，
  已完整恢复原音频稿。偏好展开状态以精确受控面板关联的 aria-expanded 为准，
  兼容原生 range 时长及实际 Seed pressed按钮读取；Seed值写入及其它模型参数仍待验收。
  音频节点模型/采样率有独立动态菜单合同：已知草稿摘要、实际模型 ID、采样率 Hz，
  保留结构化引用/提示词/文件输入。真实源码菜单发现通过，真实参数选择与已安装 CLI 分开验收。
- 真实音频首页观察：Seed Audio 1.0 描述支持参考音频，采样率为
  8 / 16 / 24 / 32 / 44.1 / 48 kHz；标准生成模型显示“当前模型无需额外设置”。
  当前首页这两个模型的偏好菜单里没有观察到独立音色选择器。
  用户指出的加号路径已核对：首页“本地上传”接受 WAV/MP3 等格式，另有替换素材文件输入。
  首页尚未上传；真实上传验收在获批空测试项目的音频节点面板执行。
- 音频节点加号：参考音频最多 3 个、参考图最多 1 个。已批准的 1 秒合成 WAV 上传一次，
  实际菜单从 0/3 到 1/3，卡片的 type/title/object-id 一致，真实 FileList 清空。
  源码经 CUA/CDP 仅读 DOM 验证 files_known=true、layers=0；空提示词、模型/采样率保留。
  卡片存在不等于音色效果、音色克隆、供应商持久化或最终生成。
  后续 CUA 手工核对真实结构化音频 token；新增准备器已通过原生隔离测试与真实源码零输入检查。
- `@引用角色与素材` 按钮会插入 `@` 并打开菜单，不是无副作用的音色列表查询。
  本次在新的空草稿里打开并检查，未选择用户资产；原生键盘撤销工具插入的 `@` 后回读为空。
  CUA 的空 fill 曾保持该字符，记录为后端验收差异，不当作清空成功。
- 测试节点模型恢复 Seed Audio 1.0 / 44.1kHz，积分保持 6396；一次获批上传，零生成/消费。
  截图：`/private/tmp/atm-xyq-audio-reference-upload-final-20261007.jpg`；
  mode-600 最终回执：`/private/tmp/atm-xyq-audio-reference-receipt-20261007-r2.json`（初轮保留）。
- OpenCLIApp 内置 CLI 已运行且桥连通；普通 adapter 的独立页面仍 origin_mismatch。
  本次重新盘点其页面为 about:blank；browser bind 成功并不影响 adapter 的独立 surface。
  新显式音频绑定读取器已通过实际 App CLI 和生成包→隔离 ATM→App→测试表单的链路，
  完整 form SHA 与独立源码仅读一致。其它已安装 CLI 入口、写入、音色效果、生成/下载继续单列待验收。
  CUA 经原生输入执行源码、隔离浏览器测试、已安装 CLI 是不同证据。

新增只读home_quote把音频单位费率、图像无单位显示金额、视频折扣amount/originalAmount分别读取；
生成CLI→隔离ATM→App的9阶段默认模式报价链路通过，图片6/视频600与划线780/音频0.33每秒，
完整原音频稿恢复且余额6396；同键复用同job。单条报价注册加载，原12条和生产ATM保持。
详见 XYQ_HOME_QUOTE_CONTRACT.md。绑定完整原稿，报价缺失/忙态与竞态明确区分，
显示预估不等于最终账单或已验证硬预算，单次提交及付费生成验收保持独立。

新增只读project_history_state绑定精确测试项目/canvas，仅仅读当前历史视图和筛选。
生成CLI→隔离ATM→App的实际空态/关闭态通过；同键复用同job，原音频节点和空首页全稿保持。
关闭/加载数量是null，empty只证明当前“全部媒体/成功”筛选可见记录为0；
task_count=null、all_records=false，任务行所属项目与格式仍待核对，有行时明确停止。
当前两页面显示6430积分；此前6396是上一阶段读数，不称本轮余额未变。
本轮CLI零输入，CUA只关闭自己打开的历史层；没有上传、生成或读取全账户任务。
新增1条history注册，保留原13条/17定义和生产ATM；18包见generated/xyq-web-history-stage/。
本页 `generated/xyq-*` 阶段目录都是本机构建输出，未提交到仓库；当前27项按[重建步骤](XYQ_MEDIA_RUNTIME_CONTRACT.md#从源码重建并安装27项)重建。
最终Node218/Python316全通过零跳过；实际任务ID/状态/结果及下载仍待验收，
详见 XYQ_PROJECT_HISTORY_CONTRACT.md。

编译器默认生成十八个媒体阶段包。`--include-canvas` 仅显式导出暂缓的实验源码，
不把复杂工作区列为当前媒体生成完成门槛。真实状态见 XYQ_WEB_COVERAGE.md。

另新增独立本地xyq.media.artifact_inspect与atm media inspect，网页18定义保持。
PNG/JPEG/WebP/PCM WAV/MP3/MP4的摘要、容器、完整解码和路径/字节竞态核对已实现；
合成六格式通过生成CLI→隔离源码ATM→真实解码器，同键历史复用与新键识别文件变化通过。
新增56测试；小云雀/CLI/quickstart扩展422全通过、零跳过，原断言/路径保护保持。
生产ATM未升级，未下载网页文件；本地字节通过不证明task关联、供应商生成或实际下载。
artifact_rejected/valid=false的completed检查job也不是有效文件，详见 XYQ_MEDIA_DELIVERY_CONTRACT.md。

同一音频参考上传入口的源码现增加有界 MP3 intake，WAV校验/历史指纹/empty/append/
一次输入与未知锁保持；独立18包位于generated/xyq-web-mp3-reference-stage/（本机构建输出，未提交）。
最终248 Node/434 Python通过，含5份真实本地编码和原生隔离卡片/引用保留；
已安装WAV闭包/生产ATM保持，网页实际MP3接收仍待新文件许可。
格式声明、帧时长与完整解码区别、全部pin和回执见 XYQ_MP3_REFERENCE_CONTRACT.md。

后续现有显式上传注册已单独升级MP3（最终c70aa32 pin，旧版9文件完整备份），
其它13条注册继续旧pin，生产ATM保持。生成CLI→隔离ATM→App的MP3旧摘要预检已通过，
upload_rejected/draft_changed、零文件输入、同键同job，原音频及首页全稿保持。
当前18源码包位于generated/xyq-web-mp3-cli-stage/（本机构建输出，未提交）；相关验收、失败根因及真实附件门槛仍以
XYQ_MP3_REFERENCE_CONTRACT.md末节为准，不把预检completed解释为上传或生成完成。

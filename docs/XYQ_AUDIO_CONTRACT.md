# 小云雀音频参考合同

当前实现是音频**生成表单**和用户批准的 WAV 参考上传，不开展复杂白板编辑。
用户所说“上传音色”是加号上传音频作参考；不宣称有独立音色库或已验证音色克隆。

## 工具与绑定

- `xyq.web.audio_form_state`：当前 `/project`，精确 project/canvas/audio-node ID，
  仅读模型、采样率、提示词摘要、参考 type/名称摘要/引用摘要、FileList 已知态。
- `xyq.web.audio_reference_upload`：精确 `expected_form_sha256`、项目 WAV 路径、
  文件 SHA256、`purpose=audio_reference`、本次 `confirm=true`、稳定 `request_key`。
  ATM workspace 自动作为文件归属和回执根，不接受任意回执目录。
  可选 `mode=empty|append`；缺省/empty 沿用原空草稿合同，append 明确追加一份获批 WAV。
- `xyq.web.audio_prompt_prepare`：精确表单摘要与纯文本 `prompt` 或已上传音频的
  `reference_sha256`。先准备纯文本，再通过素材卡片的 mention 按钮追加结构化引用。
  至少提供一个动作字段；运行时在读浏览器前校验，不接受原始素材 ID、HTML 或任意 selector。
- 页面 footer 是 viewport portal，实际 DOM 没有 node-id 关联标记。
  第一版要求画布**恰好一个音频节点**且 ID 一致；多个音频节点报 `audio_node_ambiguous`，
  不把某个现存 footer 猜成请求节点。该限制和当前关联方式在 JSON 明确报告。
- 仅读以实际提示词/引用/FileList 计算完整表单摘要，输出仅摘要；不读取认证、浏览器档案或内部状态。
- 缺省/empty 上传要求空提示词、空引用、已知空 FileList、无其它弹层、非提交中。
  已有内容留原样；不替换素材、不插入 @、不切换节点/项目、不点生成。
- 显式 append 允许既有提示词/结构化引用及音频/图像卡片；所有既有卡片及相对顺序、
  提示词树/引用计数、模型/采样率、FileList 控件形状均须保留。最多3个音频参考，
  本次仅加一个；同名文件或满槽在 intent/input 之前报 reference_name_conflict / reference_limit。

## 文件与单次上传

- 第一版文件：项目内普通 PCM WAV，mono/stereo，8/16/24/32-bit，8–192kHz。
  **20MiB / 120秒是本工具的保守客户端边界，不是已确认供应商上限**。
  校验 RIFF/WAVE、完整 chunk、byte-rate/block-align/data 对齐和 SHA；不只检查后缀。
  禁止 symlink、路径越界、缺失/非法文件；读取上限确定后才读内容。MP3 接入另验收。
- 通过已观察唯一的 `input[data-audio-reference-upload=true]` 和 reviewed DOM file-input 桥上传。
  CDP 只使用 DOM.getDocument/querySelector/setFileInputFiles；没有隐藏供应商 API 重放。
- 在原生文件输入前持久化 `.atm/xyq-audio-uploads/active.lock` 和本次 intent。
  输入只发送一次。卡片匹配文件名且模型/采样率/提示词和其它状态未改，才写 result；
  完成 lock 移为独立 completed.lock 保留，不删除回执。
  intent 之后、输入之前再次核对确切表单。发生变化保留 intent/lock，报告 input_preflight
  和仅 upload_intent 的已完成步骤；没有为通过检查而清稿或重试。
  追加时回读须发现恰好一个新 ID 的音频卡片；先前卡片仍显示不算上传成功。
  等待新卡片时发现旧卡片、提示词或模型变化立即报错，保留不确定性锁。
- 同 request-key/指纹复用结果，零浏览器调用；复用结果标记 `current_form_verified=false`。
  失败或结果未知保留 active.lock/intent，报告 phase/completed_steps/outcome_uncertain。
  不换 key 重传、不自动移走锁；先核对供应商草稿，再另行制定人工 reconciliation。
  缺省/empty 继续使用旧版本指纹算法和旧结果模式缺省；append 有独立指纹，
  同一个请求键更换模式报 request_key_conflict，原上传回执仍可复用。
- `attached` 仅代表 **visible_audio_reference_chip_only**。
  `voice_effect_verified=false`、`persistence_verified=false`、`paid_submitted=false`；
  参考芯片不证明音色效果、上游媒体处理成功或音频生成完成。

## 真实验收与仍待验证

在用户批准的 `ATM-XYQ-CLI-test`（project 10500937705228 / canvas 10520952130316）
创建一个空音频节点 10538862125068，原有文本节点保留。
经 CUA filechooser 上传一次合成纯音 WAV：1秒、88244字节、无真人声音。
文件 SHA：`65a86cc41b797cfe952202e728aa5044ea1c25312567c03789f9aed1bd9ca530`。

- 菜单参考音频 **0/3 → 1/3**，参考图 0/1；实际卡片 title/type/mention-remove object-id 一致。
- 真实 FileList 已清空，卡片保留；这促使首页表单摘要增加附件 rail，防止漏判已有参考。
- `audio.mjs` 实际源码通过 CUA/CDP 仅读 DOM：已知空 FileList、无其它层、空提示词，
  Seed Audio 1.0 / 44.1kHz 保留，生成按钮 disabled，积分 6396 保持。
- 本次 filechooser 返回耗时较长，后续只读核对已出现卡片，没有再次上传。
  LV 上传菜单的 Escape 未关闭，通过该菜单自己的加号 toggle 关闭后回读 layers=0。
- 截图 `/private/tmp/atm-xyq-audio-reference-upload-final-20261007.jpg`。
  最终 reader 回执 `/private/tmp/atm-xyq-audio-reference-receipt-20261007-r2.json`（0600、无认证数据）。
  初轮回执保留；最终版还绑定空编辑器结构、富引用计数、原生输入前后文件摘要和 FileList 控件形状。

源码原生隔离上传、真实 CUA filechooser、安装桥接是三个证据。
安装后的 CLI 上传、首页上传、MP3/多参考、@结构化引用准备、真实音色生成效果、报价/任务/下载仍待验收。

## 新增：结构化音频引用准备

真实素材卡片的 @ 按钮插入 `data-type=canvasPippitAssetMention` 的不可编辑 SPAN，
带实际数字 `data-id` / `data-pippit-asset-id` / `data-material-pippit-asset-id`，
三者须一致，并有 audio-preview 标记。不是把文件名写成 `@name`。
观察到该 UI 在 token 后追加一个 ASCII 空格；准备器检查此精确结构和既有文本/token 不变。

- 提示词只解析已观察的 P、文本、BR 和音频 token；未知结构报错并保留草稿。
  有结构化引用时保留原稿，纯文本整体替换会报 `rich_prompt_present`。
- 通过已上传参考摘要定位唯一卡片；重名参考报 `reference_ambiguous`。
  已出现的目标引用直接零输入返回，避免重复插入。
- 原生 focus/end-caret 后回读真实 Selection，确认目标编辑器、折叠光标和文末位置，
  才点击一个确切 mention 控件。未知 Selection、覆盖控件、其它弹层或草稿变化明确报错。
  发生输入后的失败保留 phase/completed_steps/outcome_uncertain；不重试或自动回滚。
- Chrome 原生首尾空格输入依赖实际编辑器的 `white-space:break-spaces`。
  夹具漏此样式曾产生 NBSP，修复夹具后原精确字面断言通过；另有 normal 样式回归
  验证 `settings_changed` 和零 mention 点击，不静默归一化用户文本。
- 原生隔离测试验证中文、多行、首尾空格、结构化 token、幂等和失败路径。
  真实 CUA 草稿手工准备了“ATM 音频引用测试：”及一个 token，实际 asset ID 为
  `10536312462092`。随后实际源码经 CUA/CDP 执行已有引用零输入检查：
  `completed_steps=[]`，模型 Seed Audio 1.0、44.1kHz、额度 6396 保留。
  此证据是源码只读执行，尚非已安装 CLI 的提示词/引用写入验收。
- 最终 mode-600 回执：`/private/tmp/atm-xyq-audio-prompt-readonly-receipt-20261007-r2.json`。
  初轮额度探针选到风格库，初轮回执保留；最终版用唯一 `积分余额` aria-label 校正。
  截图：`/private/tmp/atm-xyq-audio-prompt-readonly-final-20261007.jpg`。

当前生成包为 `generated/xyq-web-audio-prompt-stage/`，12个均通过完整性验证。
本页 `generated/xyq-*` 阶段目录都是本机构建输出，未提交到仓库；当前27项按[重建步骤](XYQ_MEDIA_RUNTIME_CONTRACT.md#从源码重建并安装27项)重建。
prompt 源码 pin：`094f2a8475c4e60ea2ffbfec5a52ab4f6068898017fbd09f02d9f38feb8fa8b6`。
上传、引用准备、真实音色效果、付费生成、持久化和下载保持独立验收。

## 已安装桥的只读验收状态

用户已明确允许启动已安装 OpenCLIApp 和加载本工程适配器，仅仅读测试项目音频表单。
OpenCLIApp 0.1.38 的内置 CLI 1.8.6 可运行，doctor 显示 daemon 与扩展 1.0.24 连通。
桌面 CUA 启动通道报错；不以 CLI 可运行声称 GUI 已正常启动。

只新增 `~/.opencli/clis/xyq-web/read.js` 一个读取注册入口；四个原始 pin 文件位于
`reviewed/` 子目录，未扫描加载其中的上传/其它注册入口。没有替换既有目录。
读取 loader SHA：`05dd7a45592a7bc30ac22cd1a2e51b9a6d546ab82713083b973e1c8766a1da53`；
audio 原始源码 pin 保持 `b90b0a150403016741e29f8034723ea4fa58db2aa64eff227e6a6fa9c5760250`。

实际命令发现/帮助通过；CUA tab ID 与 OpenCLI page identity 属不同命名空间。
直接选择 CUA ID 返回 stale identity；CLI 绑定后的自有窗口仅见 `about:blank`。
精确项目/画布/节点读取返回 `origin_mismatch`，未导航或读取其它页面内容。
已请求人工打开 OpenCLIApp 内测试项目音频面板；真正 CLI 表单读取仍待该状态就绪。
未导出认证、改变浏览器策略、安装更新、上传、生成或消费。

## 新增：音频节点模型与采样率

`xyq.web.audio_choices` 只打开/收起自己的模型和采样率菜单；
`xyq.web.audio_prepare` 绑定 `expected_form_sha256`，接受实际 `model_id` 与整数 `sample_rate_hz`。
两者在 ATM 都要求 execute_code/external_write，因为发现操作也会打开菜单。
准备至少需一个动作字段；JSON 数组、数字模型 ID 和字符串采样率在浏览器访问前明确报错。

- 模型语义来自 `select-audio-model-*` 及 model-picker-item-title；当前真实测试面板
  观察到 seed_audio / Seed Audio 1.0、qwen_tts / 标准生成。该列表是当前菜单，不是永久枚举。
- 采样率来自菜单的 `select-audio-parameter` / sample_rate / 数字 data-action-value，
  且菜单 aria-labelledby 必须对应当前音频 footer 的触发器。当前 Seed Audio 的六档为
  8000 / 16000 / 24000 / 32000 / 44100 / 48000 Hz。
  数值与 kHz 标签、唯一选中值、实际 footer 读回均核对；无控件时显式报告不可用。
- 原生选择后核对目标值；提示词树、已上传卡片、结构化 token 和 FileList/控件形状保留。
  模型切换引起的采样率默认变化作为实际 implicit_sample_rate_change 返回，不猜默认值。
  若同时请求采样率，则在新模型的实际菜单中校验，失败保留已完成步骤。
  已选参数只发现菜单，不再次选择；原生输入后的失败报告 uncertainty，不自动回滚。
- 真实根因：画布底部的“添加节点”工具条覆盖采样率按钮中心。
  适配器对精确控件的七个有界内部点做 elementFromPoint；中心遮挡但左侧可见时，
  从该精确可见点发送原生点击。全部遮挡则停止输入；没有强制点击或隐藏/移动遮挡物。
  原生夹具分别验证局部/完全遮挡、菜单关联错误、额外弹层、输入未生效与富引用保留。
- 最终源码经 CUA 的原生点击/Escape 完成真实菜单发现，模型、44.1kHz、
  提示词/token/参考卡片的完整 form SHA 保持 `64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97`。
  未选择新参数，积分显示6396；这里是源码菜单发现，不是已安装 CLI 参数写入验收。

当前14包：`generated/xyq-web-audio-settings-stage-r2/`（本机构建输出，未提交），均完整性有效，未安装到真实 ATM。
源码 pin：`357d3a6ed5a0795145fa1a9e5e24ed829a37c046aeb17ba826f60912d644b5d6`。
初轮包/源码回执保留；r2 增加显式 JSON 字符串类型校验，最终 CUA 回执 pin 与14包一致。
真实 mode-600 回执：`/private/tmp/atm-xyq-audio-settings-cua-receipt-20261007-r2.json`；
截图：`/private/tmp/atm-xyq-audio-settings-cua-final-20261007.jpg`。
全回归 Node114、Python102（非浏览器39、原生隔离63），全部通过，零跳过。
回执 `/private/tmp/atm-xyq-audio-settings-node-20261007-r2.txt` 和
`/private/tmp/atm-xyq-audio-settings-all-20261007-r2.xml`。

真实参数选择、标准生成切换后的具体文件/音色能力、付费/任务/下载、已安装 CLI 仍待验收。

## 本次仅只读复核及新编译快照

再次执行获批的已安装 `audio-form-state`，精确绑定上述测试项目/画布/节点，
仍返回 `origin_mismatch`；这不是 CLI 表单读取通过。已安装 read loader 和其独立旧源码
保持原样，未加载写入注册入口，仍等待 OpenCLIApp 内测试面板的人工 handoff。

当前源码经 CUA 仅只读同一测试表单：Seed Audio 1.0 / 44.1kHz、一个音频参考、
一个结构化引用，完整 form SHA 仍为 `64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97`。
没有发送输入、重新上传或生成；未重新验证音色效果或持久化。
回执 `/private/tmp/atm-xyq-mode-modal-readonly-20261007.json`（0600），
截图 `/private/tmp/atm-xyq-mode-modal-readonly-20261007.jpg`。

首页模式菜单修复更新共享 core，因此新默认14包位于 `generated/xyq-web-mode-modal-stage-r2/`（本机构建输出，未提交），
音频 source pin 也随依赖更新。上一节音频参数14包是保留的历史快照；最新 pin 和
回归真源见 XYQ_WEB_COVERAGE.md 末节。新 ATM 包尚未安装，当前旧只读安装不静默替换。

## 新增：草稿绑定的显示费率

纯只读 `audio_quote` 的金额语义与快照协议见 XYQ_AUDIO_QUOTE_CONTRACT.md。
测试项目真实显示 `1积分/3s`，这是预计费率而非单次总价/输出时长或扣费上限。
该入口保留既有模型、采样率、WAV 卡片与结构化引用，单次总价、生成和交付另列。
编译默认增至15个媒体包，旧14包及原已安装只读 loader 保留，最新证据见覆盖文档。

## 新增：多音频参考追加

显式 mode=append 的源码/隔离原生回归现已覆盖：1→2、2→3音频参考、保留一份图像参考、
既有结构化音频 token 和提示词保留，第四份或同名冲突零输入，变化/未知结果保留 intent/lock。
返回 upload_mode / previous_reference_count / added_reference_sha256 / references_preserved，
仅代表已读取的卡片与既有 DOM 状态，不代表供应商持久化或实际音色效果。

真实账户仍只上传过原批准的一份合成 WAV。当前许可仅只读；本批没有追加上传，
新增源 pin、包快照、回归和只读复核证据见 XYQ_WEB_COVERAGE.md 末节。
MP3/首页上传、真实追加、付费生成与完整媒体交付继续单列验收。

## 最新：显式绑定只读 CLI 已验收

新增 `audio_form_state_bound` 使用已核对测试页的显式 browser 会话，
完整范围、路由差异与回执见 [显式绑定读取合同](XYQ_BOUND_READ_CONTRACT.md)。
真实生成的 CLI → 隔离临时 ATM → 已安装 OpenCLIApp → 测试音频表单已通过；
同一 request-key 复用同一已完成只读 job，完整 form SHA 与独立源码读回相同。
原普通 adapter 的 origin_mismatch 仍是独立未通过项；先前 App 面板人工 handoff
已不再是新入口的门槛。新入口仅只读，生产 ATM 安装、其它参数/引用写入、
音色效果、生成、任务与下载仍单独验收；没有再次上传或消费。

后续显式 audio-quote-bound 已通过单位费率生成CLI只读链路，见 XYQ_AUDIO_QUOTE_CONTRACT.md。
音频参数/提示词/引用三个显式绑定路由已接入并加载，详见 XYQ_AUDIO_BINDING_CONTRACT.md；
隔离原生桥测试通过，真实生成CLI只验收已存在引用的零输入核对，不记为实机字段写入/引用追加。
原全文、单个token、模型/采样率与6396积分保持，16包和生产ATM状态分列。

上传的显式绑定桥现已接入，详见 XYQ_AUDIO_UPLOAD_BINDING_CONTRACT.md；缺省上传业务合同保持。
一条注册已加载，隔离原生上传/追加通过，真实生成CLI仅通过旧摘要的零输入预检停止，
返回upload_rejected/draft_changed，不记为成功上传。真实账户仍只有原批准的一份测试WAV，
新文件未传输，原稿/引用/6396积分保持；实际CLI附件、音色效果与持久化继续单独验收。

## 音频节点素材菜单：格式声明与实际支持分开

2026-10-07，精确测试节点的加号菜单再次读到“上传参考音频 1/3”和
“上传参考图片 0/1”。音频专用 input 的 `accept` 为 `null`；图片专用 input 为
`.jpg,.jpeg,.png,.webp`。这与首页上传 input 显式列出 WAV/MP3 是不同表面，
缺少过滤声明不证明节点支持任意音频格式，也不证明 MP3 已被供应商接收。
本次观察时已安装 CLI 上传校验仅接受 PCM WAV；本地 MP3 解码通过也不是网页上传验收。

仅查看菜单并用同一个加号收起，未选文件或发送生成。独立源码回读确认：
原音频完整 SHA `64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97`、
Seed Audio 1.0 / 44.1kHz、单个 WAV 卡片和结构化引用保持，两个 FileList 已知为空，layers=0。
空首页完整 SHA `cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf`
与原稿一致，仍为音频模式。当前显示余额6430，旧6396是历史读数。
观察回执 `/private/tmp/atm-xyq-audio-upload-menu-observation-20261007.json`（0600），
恢复截图 `/private/tmp/atm-xyq-audio-upload-menu-restored-20261007.jpg`（0600）。
本次没有新增适配器、修改 pin 或升级生产 ATM。MP3 附件需独立文件/追加测试许可；
卡片、持久化、音色效果和付费生成仍分别验收。

后续 MP3 源码阶段已扩展同一上传业务入口，格式/回执兼容、传递 pin、完整回归和
实机许可门槛见 [MP3 参考上传合同](XYQ_MP3_REFERENCE_CONTRACT.md)。已安装 WAV 闭包保持，
新增格式的隔离卡片回读不作为供应商接收或真实音色效果证据。

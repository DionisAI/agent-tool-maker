# 小云雀音频参数与引用的显式绑定

## Strategy note

- Strategy: UI_SELECTOR; Contract: visible-ui.
- Evidence: 已核对的单音频节点 footer、模型/采样率菜单及合成 WAV 结构化引用，
  复用 XYQ_AUDIO_CONTRACT.md；独立 browser/adapter surface 的实际路由差异已验证。
- Auth source: Chrome-owned login。公开 Page 固定 site:xyq-web/browser/persistent，
  沿用严格/首选 profile 路由；不读取或迁移 Cookie、token、profile、认证存储。
- Replay: 复用既有参数/引用业务合同，新增仅语义目标的原生输入桥；
  源码、隔离原生 DOM、生成CLI零输入和实际字段写入分别验收。

## 范围

显式编译 `--bound-audio-edit` 调整既有 audio_choices、audio_prepare、audio_prompt_prepare
三定义，不新增工具ID、不调整缺省路由、不在失败后自动重绑定或换后端；总数仍16。
不含音频上传、生成、单次总价、任务或下载；本合同只是完整媒体流程中的参数/引用准备阶段。
当前媒体范围真源仍 XYQ_MEDIA_CONTRACT.md。

精确 project/canvas/node，完整 form SHA，模型 ID/采样率整数及已有音频 reference SHA
沿用既有 typed schema。参数先于 Page 构造校验。坐标、选择器、JS、原生键和 CDP 不进入输入。
每次输入重新核对唯一音频节点/选中 footer、目标关联、禁用状态和真实 pointer hit。
模型/采样率仅在所属菜单；Escape 仅关闭本调用打开且仍可核对的菜单。
部分遮挡复用既有有界内部命中点，禁止强制输入或更改 DOM/浏览器策略。

纯文本仅在没有结构化 token 时全选替换，原生焦点/真实完整选区/字面回读均须成立。
固定 selectAll/deleteBackward/insertLineBreak 与 nativeType，不开放任意 CDP 或键序列。
已有富引用保持，引用追加只允许确切已上传音频，通过原生 End 与真实末尾光标校验。
已经存在的引用可返回 zero steps，不追加、不定位光标；此状态不是音色效果或生成验收。
失败保留 phase/input_phase/completed_steps/outcome_uncertain/cleanup_code；零自动重试、回滚或重提。

## 验收状态

2026-10-07：源码和隔离原生桥通过，三条注册已加载，真实CLI仅验收已有引用的零输入路径。
实机字段写入仍须本次范围确认。用户此前的单次 WAV 上传批准不重复使用。

- 12文件闭包，source pin `5540b133586aa08216298e57f959397e6493a0b2e2615a143a4737b5468a4567`。
  原首页、音频读取、费率/参数/引用业务源码及 pin 保持。公开输入桥独立，不重构原模块。
- `~/.opencli/clis/xyq-audio-edit-bound/edit.js` 加载三条显式注册，reviewed/ 保存全闭包；
  loader SHA `b506853ca61c7ace1bfd280a7cb578e5babe9f1e35e00c0fb51fb8292a12065b`。
  原八条注册、第三方App和生产ATM/vault保持。安装计划/回执为
  `/private/tmp/atm-xyq-audio-edit-bound-install-plan-20261007.json`、
  `/private/tmp/atm-xyq-audio-edit-bound-install-20261007.json`（0600）。
- 新16包 `generated/xyq-web-audio-edit-bound-stage/`，相对费率阶段只变三条定义，其它13条保持。
  该目录是本机构建输出，未提交到仓库；当前27项按[重建步骤](XYQ_MEDIA_RUNTIME_CONTRACT.md#从源码重建并安装27项)重建。
  缺省schema/权限仍为既有合同：execute_code+external_write，即使零输入也保留该权限要求。
- Node186、Python231（69非浏览器/162原生隔离），全部通过、零跳过；新增10Node、9非浏览器
  和21原生隔离。实际桥测模型/采样率、已有引用零输入、原生纯文本/中文/空格/多行和结构化引用，
  覆盖选区丢失、忽略输入、内容竞态、非自有菜单、原生派发后异常、禁止生成目标及遮挡。
  原生输入仅在本地fixture，供应商请求被拦截；同键假子进程仅执行一次，未更改浏览器策略。
  回执 `/private/tmp/atm-xyq-audio-edit-bound-all-node-20261007.txt`、
  `/private/tmp/atm-xyq-audio-edit-bound-all-20261007.xml`。
- 获批 `ATM-XYQ-CLI-test` 已有一份合成WAV和一份结构化引用：源码evaluate-only工厂先验证
  同ref零输入；随后生成CLI→新隔离ATM（仅2定义）→已安装App→原绑定测试表单的
  before/prepare/after三job全部completed，prepare job `b59e8962-b3dd-491f-982f-2a0aa8a28566`。
  请求只含原完整 form SHA 与已有 reference SHA，不含文字或模型/采样率值。
  结果prepared、completed_steps=[]、同request-key复用同job；不定位光标或追加 token。
- 实机完整form SHA `64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97`。
  独立CUA前后完整表单与prompt文档摘要一致，仍一个token、SeedAudio1.0/44.1kHz、6396积分。
  零菜单/输入、上传、生成或扣分，voice_effect_verified/persistence_verified仍false。
  实机回执 `/private/tmp/atm-xyq-audio-edit-bound-noop-e2e-20261007/`，独立基线/终态
  `/private/tmp/atm-xyq-audio-edit-bound-cua-before-20261007.json`、
  `/private/tmp/atm-xyq-audio-edit-bound-cua-after-20261007.json`，最终核对
  `/private/tmp/atm-xyq-audio-edit-bound-final-verification-20261007.json`（0600）。

实际生成CLI菜单发现、参数值改变、文字输入和引用追加尚未实机验收，零输入不当作字段写入。
音色效果、单次总价/预算内提交、任务与下载仍分别待实现或验收，完整媒体目标保持进行中。

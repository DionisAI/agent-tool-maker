# 小云雀首页显式绑定参数准备

## Strategy note

- Strategy: UI_SELECTOR；Contract: visible-ui。
- Evidence: 首页精确 origin/path、现有模型/radio/时长/画布/纯文本合同；
  已安装 Page 公开 evaluate/nativeClick/nativeType/cdp 接口。
  真实空编辑器只读样式为 white-space:break-spaces，p 的上下 margin 为0。
- Auth source: Chrome-owned login；无认证、Cookie、存储或浏览器 profile 文件读取。
- Replay: 新入口先源码/假子进程/隔离原生 Chrome 验证。真实写入和生成交付分列。

当前 `--bound-home` 为五个既有工具选择明确绑定路由：form_state / form_choices /
form_prepare / mode_choices / mode_prepare，仍为16个媒体阶段包，缺省路由和工具ID保持。
已有四入口实际链路通过见 [首页绑定合同](XYQ_HOME_BINDING_CONTRACT.md)。
新增准备入口现已加载到实际 App，完成了生成CLI的仅摘要零输入验收；生产 ATM未安装。
新source pin/定义与原四入口实测不同，历史菜单通过和本轮零输入通过都不等于参数值写入验收。

## 参数与输入边界

复用原 `prepareForm`，输入 schema 不变：完整 expected_draft_sha256、实际可用模型标题、
实际 radio组/选项、duration_seconds、canvas、纯文本 prompt；只有请求的字段参与修改。
不接收 selectors、URL、JS、坐标、任意 CDP/键盘命令、生成或上传操作。
准备不要求空提示词，但每次替换绑定完整原稿摘要，富文本引用保持原有专用合同。
未知 FileList、旧摘要、既有弹层、不可用选项与遮挡均停止相应输入；不扩大授权。

模型/radio 点击只在唯一、精确关联的自有偏好面板内，画布点击只在无弹层的首页。
原有模式点击仍保持原范围；自有菜单 Escape 继续验证关联，页面属性保持原样。
文本桥仅开放固定纯文本编辑器及视频时长文本输入：

1. 唯一语义目标、可见/可编辑/命中检查后原生点击；再核对实际 focus和字段原值。
2. 固定原生 selectAll 编辑事件；读取实际全选范围。禁止以“发过快捷键”假定已全选。
3. 中文/emoji 用公开 nativeType；清空用固定 deleteBackward。
   LF分行使用固定 insertLineBreak（原生Shift+Enter），各行输入前检查 caret仍位于同一编辑器。
4. 逐字回读非空内容，保留空格/LF；空稿沿用现有 readDraftDOM 的语义空约定。
   NBSP、额外换行等非空差异明确报 settings_changed，不归一化为成功。
5. 全表单回读继续验证提示词、参考、文件状态、参数和自有菜单关闭。

Input.dispatchKeyEvent 的 commands 为 Chrome公开协议定义的编辑命令：
[协议来源](https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/pdl/domains/Input.pdl)、
[Blink命令表](https://raw.githubusercontent.com/chromium/chromium/main/third_party/blink/renderer/core/editing/commands/editor_command_names.h)。
它们由内部工作流固定选择，不透传调用者命令；不是 DOM属性/选区setter或页面脚本提交。
type=number 的选区没有可验证 selectionStart/End，明确 selection_unverifiable；
零文本替换并关闭自有面板。当前真实时长输入的类型、尾部空行等仍需实机核对。

失败保留 phase / input_phase / completed_steps / cleanup_code / outcome_uncertain。
原生输入异常及应用后读回差异保留不确定状态；不重试、回滚、切换后端或重绑定。
适配器输出只有草稿摘要/状态/参数，没有读取到的原稿文本或认证数据。

## 根因与测试证据

- 首轮 Node新增7项按预期失败：form_prepare未接入、缺fillText。红色回执保留。
- 首轮原生测试在执行沙箱内Chrome启动失败（8通过/21初始化错误），不是供应商异常。
  后续获准在外部执行隔离假页，未更改浏览器策略，全部第三方请求响应为夹具或终止。
- 已安装 nativeKeyPress只发key/modifiers，隔离测试证实快捷键未全选；修复固定原生编辑事件，
  保留真实选区检查。选择受阻或focus移走时仍为零文本替换。
- 整段 Input.insertText 的LF变成段落，innerText产生双换行；修复逐行原生Shift+Enter。
  首轮夹具的normal空白样式将多空格转NBSP；真实只读样式证据校正夹具至break-spaces，
  另保留normal样式的反例，明确失败且只执行一次替换，不放松字面回读。

最终全回归 Node **168 passed /0 skipped**；Python **190 passed /0 skipped**
（55非浏览器、135原生隔离）。新增7Node、2非浏览器Python、14原生隔离：
全部语义字段、单/多行中文/emoji/空格、明确清空、已有附件保留、错摘要/富引用、
focus/选区中断、原生异常、number选区未知、NBSP差异、Control分支及稳定请求复用。
Control分支是macOS隔离Chrome中的平台元数据夹具，不当作Linux实机验收。

回执 `/private/tmp/atm-xyq-bound-prepare-all-node-20261007.txt`、
`/private/tmp/atm-xyq-bound-prepare-all-20261007.xml`；初轮与r2/r3/r4失败、诊断及r5 focused回执保留。
真实只读 `/private/tmp/atm-xyq-bound-prepare-readonly-site-20261007.json`（0600）：
仍为音频空稿，完整SHA
`cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf`，零实际输入/上传/生成。

## 当前编译和安装状态

- 新源码 pin `7d009002f133eac8addcd459b227d0b4cfee2709c972231bad20d33658bea09b`。
- `generated/xyq-web-home-prepare-stage/`：16包、五个显式首页定义，其它11个定义与r3完全一致。
  所有旧目录和原回执保留。生产ATM保持；仅在新临时ATM安装form_state/form_prepare两定义验收。
- 当前App加载相同新pin的五入口，home loader SHA
  `2828bfbcf253f95e83cd9dea6eaa777d7e3aa667e8321cc668b84538cfd0b68b`。
  只更新home-bound.mjs/home-bound.js和home loader，没有更新第三方App或两个原音频read loader。
- 原四入口实测pin `c6cb485f03a7d28fb348d3c06dd620529dfe1a75a3b3202d4405ed73777e1d42`及完整旧闭包/
  loader已保存 `/private/tmp/atm-xyq-home-prepare-installed-before-20261007/`；所有旧回执保持。
  安装回执 `/private/tmp/atm-xyq-home-prepare-install-20261007.json`（0600）。
- 上阶段源码/测试核对 `/private/tmp/atm-xyq-home-prepare-final-verification-20261007.json`（历史/0600）；
  本轮核对 `/private/tmp/atm-xyq-prepare-noop-final-verification-20261007.json`（0600）。

## 实际零输入链路通过

新生成tool.py → 已安装ATM（仅新临时state）→ 已安装App → 同一已绑定音频空首页：
before状态读取、form_prepare仅expected_draft_sha256、after独立状态读取，三个job均completed。
准备输入没有模型/radio/时长/画布/提示词，结果ready、prepared=true、completed_steps=[]、options=null。
同一准备request-key复用同一个job；源代码此分支不打开菜单或调用任何原生输入。

独立CUA前后完整表单完全一致：原SHA cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf，
SeedAudio1.0/44.1kHz、参考0、文件0/0已知、生成禁用、layers=0，积分6396。
零上传/生成/消费，没有导航、重绑定、凭证读取或生产ATM授权改动。
回执目录 `/private/tmp/atm-xyq-home-prepare-noop-e2e-20261007/`，独立读回
`/private/tmp/atm-xyq-prepare-noop-after-20261007.json`；截图
`/private/tmp/atm-xyq-prepare-noop-final-20261007.jpg`（真实JPEG/0600）。
本轮源码pin保持，不重跑168Node/190Python，沿用相同源码回归回执；新证据为实际CLI零输入链路。

待验收：新准备入口的真实App/生成CLI写入、其它模型动态菜单、自定义Seed、实际音色效果、
上传/引用、单次总价与预算内提交、媒体任务/下载。现有模型菜单切换确认仍待用户回复；
另已请求同一空首页“ATM 参数测试\n第二行”、默认视频6秒/16:9/480P及完整恢复的实际写入范围，
不选择其它模型/上传/生成/扣积分，待用户回复。全媒体生成目标保持进行中。

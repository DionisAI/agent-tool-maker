# 小云雀 MP3 参考上传合同

## Strategy note

- Strategy: UI_SELECTOR; Contract: visible-ui.
- Evidence: 首页上传过滤器显式列出 `.wav,.mp3`；测试音频节点加号是参考音频3份/图片1份，
  节点的音频 input 没有 `accept` 声明。后者不证明 MP3 实机接收，须独立上传验收。
- Auth source: 既有 Chrome-owned login 和公开 Page 音频绑定；认证文件、Cookie、storage 不读取。
- Replay: 扩展既有单文件 intake，不新建另一上传后端。PCM WAV 原校验/回执指纹保持；
  MP3 先做完整字节摘要和有界 Layer III 帧结构校验，再复用 empty/append、durable intent、
  一次 native file input、卡片及原稿回读。源码/隔离浏览器/实际供应商接收分列。

## 本期实现与边界

MP3 文件仍须为项目内常规文件、无符号链接、绑定完整 SHA256；客户端上限20MiB和120秒，
不是供应商公布的限制。支持 MPEG 1/2/2.5 Layer III、CBR/VBR、单/双声道及稳定采样率。
可跳过有界 ID3v2.2/2.3/2.4 头部和尾部 ID3v1，但不输出标签内容。
自由码率、保留字段、ID3v2 footer、截断帧、杂字节、变动采样率/声道均是明确错误。
时长按帧样本数计算，包含编码器 padding，不当作解码时长或生成报价。
MP3 intake 只证明帧结构与摘要，`decoder_verified=false`；交付完整解码见
[本地产物合同](XYQ_MEDIA_DELIVERY_CONTRACT.md)。

现有 WAV 文件返回字段、默认 empty 回执和 append 指纹保持兼容。MP3 不替换旧引用、
不插入提示词 token、不开菜单、不给生成或音色效果作成功声明；未知输入结果保留操作锁。
共享 audio source 改动会改变依赖闭包 pin，须生成独立新快照并核对受影响定义。
旧生成包保留；升级已审阅注册时保留完整旧版，并逐文件核对实际改动。
其余入口、生产 ATM/vault 和用户级 Skill保持，不静默替换。

## 验收状态

2026-10-07（先前源码阶段，后续确认与实机尝试见末节）：源码、隔离回归及显式 CLI 零上传预检完成，当时额外1秒合成 MP3 追加上传确认尚未收到回复。
既有单份 WAV 的批准已消耗，不作为新文件许可。没有本次网页上传或生成。

- 首次 MP3 源码快照 `generated/xyq-web-mp3-reference-stage/`，18个媒体包、工具ID/schema/权限保持；
  共享 audio intake 及其描述/上传注释共3个源码文件变化，依赖 pin 导致14个定义更新，
  4个基础定义保持。旧 history 快照90个文件与已安装78个源码文件逐字节保留。
  本页 `generated/xyq-*` 阶段目录都是本机构建输出，未提交到仓库；当前27项按[重建步骤](XYQ_MEDIA_RUNTIME_CONTRACT.md#从源码重建并安装27项)重建。
- 音频 source pin `d3d275345fd5c9579e3b9efbf0388f5a75260a7cb5b82be3795c6f9144caab10`；
  显式上传 pin `2821912c20e80916442b288000fac47d3a922f1dc38001b55d3a343c402fdf16`。
  全部传递 pin 见最终核对回执；先前合同中的 pin 是各自保留的历史快照。
- 新增30 Node/12 Python；最终248 Node、434 Python全部通过，零失败/跳过。
  既有 WAV legacy fingerprint/默认 empty/append、未知锁、参数/报价/绑定保护断言保留。
  5个固定 pin 测试随已审阅公共 audio closure 更新，未移除任何原保护断言。
- 5份本地真实 FFmpeg 合成 MP3（8/16/22.05/44.1/48kHz，单/双声道，CBR/VBR）
  经 Node intake 和独立完整解码器核对；标签内容不输出。它们不是供应商产物。
- 原生隔离浏览器证明一次文件输入前已留存 intent/lock、新卡片回读、原 WAV/token/图片保留、
  同键历史复用零重传、满槽预检停止、截断文件零输入和未知结果保留锁。
  测试网页的接收逻辑是夹具，不宣称真实供应商 MP3 接收。

回归 `/private/tmp/atm-xyq-mp3-all-node-20261007.txt`、
`/private/tmp/atm-xyq-mp3-all-python-20261007.xml`（另有txt）；
基线 `/private/tmp/atm-xyq-mp3-baseline-20261007.json`，最终核对
`/private/tmp/atm-xyq-mp3-final-verification-20261007.json`（0600）。
本轮没有升级生产 ATM、已安装 OpenCLI 闭包、第三方 App或用户级 Skill。
文档更新后发布/CLI检查16通过；首轮未指定Chrome的1个跳过回执保留，指定原同一官方
Chrome后r2零跳过，未修改测试断言或浏览器策略。
回执 `/private/tmp/atm-xyq-mp3-postdocs-20261007-r2.xml`；
新源码经CUA仅读原音频表单，完整SHA仍64b537、单个WAV/token和空FileList保持，
`/private/tmp/atm-xyq-mp3-ui-preservation-20261007.json`（0600）。
本阶段收尾核对 `/private/tmp/atm-xyq-mp3-completion-check-20261007.json`（0600），
仅源码/隔离验收完成，完整媒体目标和实际供应商生成交付保持进行中。

帧尺寸/采样数量规则与 [FFmpeg 的 MPEG 音频头实现](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/mpegaudiodecheader.c)
交叉核对；独立实现客户端有界校验，没有复制供应商接口或导出登录态。

## 最新：一条现有注册升级及真实 CLI 预检

后续发现上传 loader 的说明仍写 WAV，已把 description/settings help 明确为 PCM WAV/MP3。
只修改该 JS 的两段元数据；音频 intake pin仍d3d275，原WAV/MP3校验和上传逻辑保持。
最终显式上传 pin `c70aa32bcf00f1f12e8e9d13aa73d70fd8b628e637d93ae18ebe3bea85623c13`。
新18包 `generated/xyq-web-mp3-cli-stage/`（本机构建输出，未提交）相比首次MP3阶段仅上传定义pin变化。

`~/.opencli/clis/xyq-audio-upload-bound/` 已升级：先逐字节保留旧9个源码文件，
再编辑4个reviewed模块和root loader，共5文件；其余69个已安装源码文件、13条注册保持。
实际 registry 仍14条，仅该上传入口的描述/settings help变化，没有新增权限/参数。
loader SHA `b8ed03a8c527df6d614fd55a9fb96c43070b145730539ae7bc2602ad65df1931`。
旧版目录 `/private/tmp/atm-xyq-mp3-cli-upgrade-20261007/backup/`（9文件），
同目录 plan.json/receipt.json（0600）。官方App二进制保持，未升级生产ATM或用户级Skill。
其它已安装入口继续使用其各自旧pin；新18包不是全部已部署或全媒体完成声明。

生成CLI→全新隔离ATM（保留旧只读定义+新上传定义）→已安装App→精确测试音频表单：
before/reject/after三个job completed。负例传入本地完整解码过的1秒合成MP3，
但故意使用全零 expected_form_sha256；返回 upload_rejected/draft_changed/preflight，
upload_accepted=false、native_file_input_sent=false、steps=[]、outcome_uncertain=false。
没有上传intent/active.lock，没有文件传输；confirm=true仅负例schema，不是文件上传批准。
预检job `0bd6dc12-34ed-4c8e-b86a-91668f647636`，同request-key复用同job和结果。
三个job产物JSON/路径/字节数/SHA核对通过；前后旧读取器与独立当前源码CUA的完整原稿一致，
音频SHA64b537、单个WAV/token保持；原空首页音频SHA cabd0fa4保持。

当前完整Node248和受影响Python97全部通过、零失败/跳过；首阶段434的共同intake源码保持。
真实CLI仅验收MP3通过本地intake后的旧摘要预检停止，不宣称成功附件/音色效果/生成。
实机产物 `/private/tmp/atm-xyq-mp3-cli-preflight-e2e-20261007/`；最终verification.json，
独立前后 `/private/tmp/atm-xyq-mp3-cli-cua-before-20261007.json`、
`/private/tmp/atm-xyq-mp3-cli-cua-after-20261007.json`，截图
`/private/tmp/atm-xyq-mp3-cli-preflight-preserved-20261007.jpg`（0600）。

初次准备失败是助手手抄FFprobe摘要错误；原始已验证media manifest的摘要与本机二进制一致。
修复为读取并校验那份原manifest，不重新接受当前二进制的新hash，不重建隔离状态或重新绑定。
失败时未编码或调用浏览器预检，已有两定义/绑定核对后继续未执行的文件准备；诊断留在
实机目录preparation-diagnostic.json。doctor首轮-f报unknown option，按本机--help改用plain doctor；
Daemon/extension/connectivity均OK，第三方更新提示未触发安装。真实MP3附件批准仍待回复。

## 最新：用户确认后的实机尝试与选择器桥修复

用户回复“确认”后，仅对已核对音频测试节点执行一次本地1秒合成 MP3 append，
文件8973字节、完整本地解码通过，无真人声音；原生成按钮未点击。
使用既有生成CLI、隔离ATM和已安装App，旧c70aa32定义，固定request-key
`xyq-mp3-live-append-20261007-once`，job
`876bc7f1-97fa-4f04-beb2-e0ce25921829` 返回 `submission_unknown/cli_failed`。
intent/active.lock已留存，未改请求键重传或清理锁；ATM保留原stderr抑制合同。
底层具体错误字串未进入公开job，不声称确定零传输。

独立真实网页回读仍只有原WAV及其结构化token，完整form SHA64b537保持，
Seed Audio1.0/44.1kHz及6430积分观察保持，没有新增MP3卡片。
公开Page的原生只读诊断确认精确input定位、一次DOM根及同根重查nodeId一致、
输入前表单/target ready、前后原稿一致。该诊断不执行文件输入。
实机回执 `/private/tmp/atm-xyq-mp3-live-append-e2e-20261007/`，
包括 upload-observed-job.json、readonly-native-diagnostic.json、cua-before.json、
cua-after-attempt.json、cua-after-repair.json及原WAV保持截图。

根因证据：原适配器最后一步绕过公开上传API，向chrome.debugger桥裸发
DOM.setFileInputFiles；本机公开Page.setFileInput使用set-file-input命令。
[OpenCLI上游修复](https://github.com/jackwener/OpenCLI/pull/2125)记录该桥需要
文件选择器拦截及其事件backendNodeId。这个接口失配已确定；原错误被ATM抑制，
对本次具体浏览器拒绝字串的归因仍是基于上述证据的推断，不伪造原错误日志。

修复保持所有既有文件/节点/同根input重查/完整稿摘要/一次intent保护，
最终仅调用一次公开Page.setFileInput([approved_file], fixed_selector)，
由已安装扩展管理选择器，不另建上传后端、不注入页面File/DataTransfer、不改浏览器策略。
缺公开API在intent前停止；未知输入/回读错误保留锁，不自动重试。
intent后错误新增私有0600 `request-key.failure.json`：有界code/phase/步骤/原生尝试及
静态错误分类；没有原始桥错误、页面文本、文件内容或认证信息。
诊断写入冲突显式报告diagnostic_write_failed，保留原主错误。

新source pin `f33eecb64e8a6cb2b744235ea38e70b5d81b6847f0050a94a67141290d097d27`，
18包 `generated/xyq-web-audio-chooser-stage/`（本机构建输出，未提交），相比c70快照仅上传定义变化。
单个已安装入口升级，先完整备份旧9源码文件，仅改2reviewed模块及root loader；
其它69已安装源码、全部14注册元数据及App保持；未安装生产ATM或更新用户级Skill。
新loader SHA `540975f51248db01df16f7174dfb68a9895359539dfd99dbefc3e2d20a3bd545`。
回执 `/private/tmp/atm-xyq-audio-chooser-upgrade-20261007/`，含plan/receipt及backup。

最终254 Node/97受影响Python通过，零失败/跳过；新增选择器单次调用、缺API零输入、
失配节点零输入、未知错误保留、输入后回读及诊断IO冲突断言，原guard未删除。
首轮Node的252通过/2失败是MP3测试backend尚缺公开选择器API，已仅更新夹具和调用断言，
原失败回执保留。原生Chrome用隔离夹具模拟公开API，不证明扩展或供应商成功接收。
回归 `/private/tmp/atm-xyq-chooser-fix-node-20261007-r2.txt`、
`/private/tmp/atm-xyq-chooser-fix-python-20261007.xml`（另有txt）。

新生成CLI→新隔离ATM→已安装App的全零旧摘要预检通过，job
`45a856c0-f62a-4f36-b25c-6515f4a13d19`：upload_rejected/draft_changed/preflight、
steps=[]、零原生输入、没有新intent；原未知请求的锁与intent逐字节保持。
此负例不是原未知请求的重执行，也不是选择器实机附件验收。
回执 `/private/tmp/atm-xyq-chooser-preflight-e2e-20261007/verification.json`。
完整目标仍未完成：先协调原未知上传，再分别验收真实附件、引用/音色效果、
内容与预算绑定的单次生成、确切项目任务及实际文件下载；不依据一次笼统确认扩展消费范围。

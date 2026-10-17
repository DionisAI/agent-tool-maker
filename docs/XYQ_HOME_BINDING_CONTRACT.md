# 小云雀首页显式绑定 CLI

## Strategy note

- Strategy: UI_SELECTOR; Contract: visible-ui.
- Evidence: 当前安装库的公开 Page 构造器区分 browser / adapter surface；
  显式绑定音频读取已实测通过。首页模式/偏好合同已由真实 CUA 验证。
  本入口复用那些 DOM 工作流，并使用公开 nativeClick / nativeKeyPress 做原生输入。
- Auth source: Chrome-owned login，无认证文件、Cookie、存储读取或登录态导出。
- Replay: 本阶段先做隔离协议/原生测试，再分别记录实际 CLI 和生成工具包验收。

## 范围与调用方式

当前编译器 `--bound-home` 为既有 form_state / form_choices / form_prepare / mode_choices /
mode_prepare 五个工具选择显式 `*-bound` 注册入口；工具 ID 不变，定义摘要改变。
本文记录原四入口的默认菜单实测快照；新增准备合同和当前安装状态见
[XYQ_HOME_PREPARE_CONTRACT.md](XYQ_HOME_PREPARE_CONTRACT.md)。当前五入口已加载，新准备的零输入链路通过，参数值写入另验收。
缺省编译与原入口保持原样，不在失败后自动切换后端。
其它工具仍走各自原合同；本选项不意味着整套工具都有绑定路由或已安装。

Agent 将已核对的空首页置前，一次绑定独立 `site:xyq-home` browser 会话。
下述输入范围和实测状态为原四入口安装快照；新参数准备桥按独立准备合同扩展。
项目音频读取的 `site:xyq-web` 会话保持独立；不导航、不创建新页面、不读取其它项目。
读取和每次原生输入都核对精确 HTTPS origin 与 /home 路径。
输入仅允许模式触发器、模式选项和偏好触发器，以及关闭已核对自有菜单的 Escape。
无提示词/参数值填写、模型选择、上传、生成、任务中心、购买或发布。
mode_prepare 继续绑定完整空稿摘要；form_choices 继续验证开关菜单前后草稿相同。
不自动重试、重绑定或回滚；失败保留阶段/完成步骤/清理诊断，操作结果未知时先读当前页面。

这是同系统用户可信代码模式，不是敌对代码隔离；页面由浏览器持有登录。
源码 pin 覆盖全部导入闭包和注册入口；安装原代码、编译包、模拟与真实验收分列。
绑定在会话/daemon/用户切页变化后需重新核对；历史 job 复用不证明当前页面。

## 默认菜单实测状态（r3历史快照）

四个入口的真实首页默认菜单链路已通过；完整媒体生成交付仍在推进。
既有空稿许可仅默认图像/视频参数菜单及恢复原音频，没有新的内容输入、上传或生成许可。

- 原已安装实测快照 source pin：`c6cb485f03a7d28fb348d3c06dd620529dfe1a75a3b3202d4405ed73777e1d42`。
  `generated/xyq-web-home-bound-stage-r3/` 仍为16个既有媒体工具，四个定义显式换路由，
  其它定义/原 source pin 保持。原有阶段目录与安装源码快照均保留。
- 当时安装在 `~/.opencli/clis/xyq-home-bound/home.js` 与 reviewed/ 导入闭包；
  当前运行代码为新五入口pin，旧完整快照保存在 `/private/tmp/atm-xyq-home-prepare-installed-before-20261007/`。
  两个原音频读取 loader 未变；没有加载上传/生成入口。生产 ATM/vault 未改动。
- 初次 bind 目标不是首页，严格 URL 校验停止，没有读取那页内容。用户置前后，
  bind 精确匹配 /home；这与页面内容是否可读分开。
- 当时已有创作模式菜单展开，页面把首页背景标为 aria-hidden；读取器先前等待后
  返回 page_not_ready。新 preflight 仅读 origin/path、现有层与背景 mask，
  立即返回 dialog_open，并保留整个菜单/网页属性。实际已安装 CLI 返回该明确错误，
  没有关闭菜单、切换模式、输入、上传或生成。该阶段要求用户收起菜单后继续；
  本轮恢复时独立 DOM 读确认 mask消失、layers=0、原稿SHA一致，再开始新阶段。
- 首轮生成 CLI → 隔离 ATM → App 的只读 job 保留为 submission_unknown，
  `cli_failed / outcome_uncertain=true`，不计为链路通过。原回执
  `/private/tmp/atm-xyq-home-binding-e2e-20261007/failed-state.json` 保留。
  这是纯读取失败，不是已提交媒体或费用；当时尚未运行模式写入 job。
- 该实测快照回归 Node **161 passed /0 skipped**；Python **174 passed /0 skipped**
  （53非浏览器、121原生隔离）。原生输入验证 trusted click；错页、遮挡、既有菜单、
  非自有 Escape、非法目标、非空稿/错摘要和不确定输入失败均保留清晰错误。
  新掩罩菜单回归验证即时错误、零输入、整个 DOM 保持；没有放松可见性检查。
  `/private/tmp/atm-xyq-home-binding-all-node-20261007-r3.txt` 与
  `/private/tmp/atm-xyq-home-binding-all-20261007-r3.xml` 是回执。
  本轮未修改适配器或重跑这些套件，新增的是实际生成 CLI 验收。

后续验收脚本 `/private/tmp/xyq-home-binding-e2e-20261007-r3.py` 分阶段显式执行，
使用新临时 ATM 状态/已核对 r3定义；已有回执禁止再执行同一阶段，不自动换后端/重试。
原未知读取与本轮阶段回执分开。r3八阶段全部 completed：

| 阶段 | 工具 | 实际结果 |
|---|---|---|
| state / modes | form_state / mode_choices | 音频空稿ready；自有模式菜单发现并关闭 |
| image / image-choices | mode_prepare / form_choices | 图片prepared；Seedream 5.0 Pro默认菜单ready |
| video / video-choices | mode_prepare / form_choices | 视频prepared；Seedance 2.5默认菜单ready |
| audio / final | mode_prepare / form_state | 音频prepared；原稿ready并复用同一最终job |

每一步通过生成 tool.py、安装 ATM（新临时state）、已安装 OpenCLIApp执行；
每阶段后独立 CUA 核对表单/菜单/空稿状态，完成后再推进下一阶段。
默认图片实际9个模型标题、比例和1K/1.5K/2K/4K；视频实际9个模型标题、
参考生成/视频编辑/视频延长/首尾帧、比例、480P/720P/1080P、4–30秒原生range、
随机/自定义Seed按钮。只读默认菜单，all_options=false，未选择其它模型或参数值。

首次 image阶段的验收helper错误期望ready，实际工具按合同正确返回prepared，
ATM job已经completed且只执行一次mode_input。修正helper为按操作核对状态；
通过 jobs get读取既有job、校验产物SHA/字节/结果并与独立CUA一致后协调回执，
没有重跑图片模式输入。后续阶段显式持久化observed-job再作断言，失败证据继续保留。
每阶段有独立request-key和job，最终相同request-key返回原job；没有扩大付费许可。

本轮回执目录 `/private/tmp/atm-xyq-home-binding-e2e-20261007-r3/`（JSON为0600）；
独立最终CUA回执 `/private/tmp/atm-xyq-home-cli-final-cua-20261007.json`。
恢复截图 `/private/tmp/atm-xyq-home-cli-restored-final-20261007.jpg`（真实JPEG/0600），
原音频Seed Audio1.0/44.1kHz，完整SHA
`cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf`，
文件0/0已知、引用0、生成禁用、layers=0、模式/偏好菜单关闭、积分6396。
原已有菜单截图 `/private/tmp/atm-xyq-home-binding-menu-open-20261007.jpg` 保留为历史。
其它模型参数、Seed值准备、素材、音色效果、预算内生成、任务与下载仍单列。

上阶段源码/安装/包锁/回归核对回执（历史，真实链路当时pending）：
`/private/tmp/atm-xyq-home-binding-final-verification-20261007-r3.json`（0600）。
该核对确认16包有效、非首页四个定义与上一阶段完全一致、原音频 loader保持、
根/包内 Skill一致，保留原未知读取。
本轮最终核对 `/private/tmp/atm-xyq-home-cli-final-verification-20261007.json`（0600）
另验证八个真实completed job/定义/请求键/产物、3次模式输入、同job复用、
独立原稿恢复与6396积分；16包锁和其它12个定义保持，完整媒体目标仍未完成。

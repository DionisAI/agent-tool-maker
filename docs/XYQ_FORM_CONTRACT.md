# 小云雀首页表单准备契约

## Strategy note

- Strategy: UI_SELECTOR
- Contract: visible-ui
- Evidence: 2026-10-07 主 Chrome 已登录首页，真实 DOM 的模型控件是
  `button[aria-pressed]` + `model-picker-item-title`，AX 则显示 checkbox。
  参数 radio 的组名可能由 `home-direct-parameter-label` 提供，而非 aria-label。
- Auth source: browser-owned; no credential capture, auth file reads or state export.
- Replay: 真实 UI 音频采样率的准备/恢复与隔离原生 DOM 测试分别记录；桥接 CLI 验收单列。

## 范围

`form_state` 读取当前创作首页草稿摘要；`form_choices` 只开关自己的参数菜单；
`form_prepare` 在当前模式设置模型、语义参数组、时长、画布或提示词。
本合同不包含模式切换、营销/短剧、上传、生成、清除素材、购买、发布或项目创建。
选项来自当前可见模型菜单，不向 CLI 接受 CSS、JavaScript、任意 URL 或自动生成按钮名。

准备必须携带 `expected_draft_sha256`。摘要覆盖 agent、模式、偏好、提示词结构、
引用/附件、文件输入和画布。摘要不是报价或消费批准。
已存在的弹层保持原样并报告 `dialog_open`；点击前验证唯一语义目标和遮挡/禁用态。
文件状态未知时报 `reference_state_unknown`，而非假定未上传。富文本引用存在时不整体替换提示词。
每个设置使用原生输入、随后读取真实状态；模型引起的其它参数变化单列 `implicit_changes`。
错误附有操作阶段和已完成步骤；不自动回滚或重新提交，尤其不反复发送未知结果的点击。
非请求的提示词/素材/文件状态变化立即停止。退出只关闭本次打开的参数菜单，保留主要错误及清理状态。

## 验收

源代码、协议假页、原生隔离 Chrome、真实网页 UI、已安装 ATM CLI 分开。
本合同的准备结果永远 `paid_submitted=false`、`upload_started=false`，当前价格仍 `not_final`。
本期范围以 `XYQ_MEDIA_CONTRACT.md` 为准，逐项证据见 `XYQ_WEB_COVERAGE.md`。

真实网页已验证采样率切换/回读/恢复与原生 Escape 关闭。
隔离 test-only RPC 执行同一 JS 工作流，验证模型/radio/时长/画布/提示词及错误边界。
CUA 重建 DOM 的 FileList 可以是未知；不合成零文件计数来打开写入路径。
实际 OpenCLIApp 安装和桥接 CLI 调用依旧单列，用户级 Skill 没有在本批重装。

## 媒体模式菜单的背景读取

`mode_choices` / `mode_prepare` 的模式菜单合同与上述偏好设置准备分开。
真实首页的 Radix 模式菜单展开时，将仍有布局的背景标为 `aria-hidden=true`。
旧工作流在开菜单后继续使用普通可见性读取，结果为 `page_not_ready`，清理也受同一问题影响；
该次仅打开菜单，未选择模式、上传或生成，随后通过原生 Escape 收起自己的菜单。

修复只允许已打开该菜单的工作流传入严格布尔 `owned_mode_menu=true`：
唯一菜单、唯一触发器、互相对应的 aria-controls / aria-labelledby / ID、展开状态必须一致；
其它可见弹层报 `mode_context_changed`。仅该触发器所属的精确背景 mask 可参与草稿快照，
独立内部 aria-hidden、hidden 元素和其它背景继续排除。DOM 属性保持原样，无隐藏层点击或强制点击。
菜单选项和原生输入仍绑定具体菜单及唯一命中目标。普通读取入口没有这个例外。

隔离 Chrome 覆盖模式选择、私有草稿发现/关闭、错误菜单关联、额外弹层、嵌套 mask
及零 DOM 变更。后续真实源码 mode_choices 经 CUA 复测通过：打开/读取/收起自己的
模式菜单，四个标题为 Agent模式、视频生成、图片生成、音频生成，音频仍选中。
空首页草稿完整 SHA `cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf`
前后一致，文件计数0/0已知、无参考，无内容输入/模式选择/上传/生成。
额外读取 readModeMenuDOM 明确返回 mode_closed，而非用偏好菜单状态推断模式菜单已关闭。
这是源码经 CUA 的原生菜单路径，不是安装后 CLI 或模式准备验收。
临时图片/视频模式及默认参数菜单的实机核对另获空稿范围确认后已执行，详见下节。
回执 `/private/tmp/atm-xyq-home-mode-choices-live-20261007-r2.json`（0600，初轮保留）。
最新源 pin、回归和编译目录见 XYQ_WEB_COVERAGE.md 的模式菜单修复阶段。

## 默认图片/视频参数实机复核与偏好状态修复

用户明确允许当前空首页临时切换图片/视频、读取默认模型菜单、最后恢复原音频。
当前源码的 mode_prepare 已按该范围通过；未选择新模型/参数、输入内容、上传或生成。

真实偏好 trigger 的 aria-expanded=true、aria-controls 指向已显示的
role=dialog / generation-preferences-panel-positioner，而 trigger data-state 仍 closed。
旧实现因此报 menu_not_open，清理也误判；独立核对后以原生 Escape 关闭自己的菜单。
修复使用明确 aria-expanded 布尔值及该精确受控面板的可见性、open 状态、
唯一模型/偏好 section 关联；缺面板保持 pending，错误关联明确失败。
无 aria-expanded 的既有 data-state 契约保留；没有修改网页属性或强制点击。

form_choices 最终经 CUA 原生输入通过：
- 默认图片 Seedream 5.0 Pro：9个实际模型标题；比例智能、16:9、21:9、9:16、4:3、3:4、1:1；
  图片分辨率1K、1.5K（当前带限免提示）、2K、4K。
- 默认视频 Seedance 2.5：9个实际模型标题；参考生成/视频编辑/视频延长/首尾帧、相同比例、
  480P/720P/1080P、原生 input[type=range] 时长4–30秒（当前30秒）。
  发现 Seed 随机生成/自定义生成两个 aria-pressed 按钮，当前随机选中。
- sliders 兼容真实原生 range 与既有 role=slider；pressed_buttons 仅读实际标签/布尔状态，
  未知 pressed 状态报错，不推断分组、Seed值或自动启用写入。

默认选项发现仍 all_options=false；其它模型的动态参数、自定义 Seed输入、参数值真实写入
及安装后 CLI 分开验收。原生假页时长准备成功不代表本次实机修改时长。
最终回到 Seed Audio 1.0 /44.1kHz，完整 draft SHA 仍 cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf，
文件0/0已知、无内容/素材、模式及偏好菜单均关闭，积分6396。
回执 /private/tmp/atm-xyq-default-media-receipt-20261007-r3.json（0600）；
恢复截图 /private/tmp/atm-xyq-default-media-restored-final-20261007-r3.jpg（真实JPEG；早期错扩展名副本保留）。
最新源码、编译及隔离测试真源为 XYQ_WEB_COVERAGE.md 末节。

### 后续生成 CLI 实机验收

首页显式绑定四入口已通过生成 CLI → 隔离 ATM → 已安装 App → 同一空首页的八阶段链路：
状态/模式发现、图片默认菜单、视频默认菜单及完整恢复音频。默认菜单结果与上述CUA观察一致；
独立最终读确认原draft SHA、文件0/0、引用0、菜单关闭、积分6396。
此通过范围不含form_prepare、其它模型/参数值、上传、生成或媒体交付。
详细状态、验收helper断言错误协调及0600回执见 XYQ_HOME_BINDING_CONTRACT.md。

新增显式bound form_prepare复用本合同，原生焦点/选区/逐字输入桥与固定LF编辑命令
已通过隔离测试；新入口现已加载，生成CLI的仅摘要零输入链路通过，三次前/后读取与准备job完成。
实际参数写入另验收；原四入口完整源码快照保留。
源码/安装版本、number选区未知、失败诊断与实机门槛见 XYQ_HOME_PREPARE_CONTRACT.md。

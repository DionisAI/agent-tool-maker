# 小云雀首页媒体显示报价

## Strategy note

- Strategy: UI_SELECTOR; Contract: visible-ui.
- Evidence: 实际首页composer的`home-direct-generation-credit-estimate`/`credit-amount`，
  唯一`amount`，视频另有划线`originalAmount`；现有完整草稿摘要、模式/模型/参数摘要。
- Auth source: Chrome-owned login，公开Page固定site:xyq-home/browser/persistent，
  保持严格或首选profile路由，不读取Cookie/token/storage或认证文件。
- Replay: 仅DOM评估，缺失/忙态/未知与稳定显示数值分别返回；真实页面观察、隔离测试、
  生成CLI→隔离ATM→App分别记录，不把显示预估作为最终账单或付费批准。

## 读取合同

新增`xyq.web.home_quote`，settings只接受expected_draft_sha256，read-only/execute_code，
无菜单、输入、切换模式、上传、生成、导航和重绑定。编译默认17包，原16条定义保持。
报价绑定原完整prompt/tree、文件/附件、模式、偏好标签和画布状态；三组价格与草稿快照
交错核对，模型/草稿/价格/submit状态变化明确报错，不自动换后端或把错误转成空报价。

原生价格异步加载期间可能暂时缺失，即quote_unavailable/price_missing，永远不是0积分。
显式aria-busy或提交忙态为quote_pending；仅已核对的标记/数量/槽位/visible关联被接受。
主amount与aria-label数值一致；originalAmount需要实际划线显示，独立返回，不能拼成600780。
支持观察到的无单位数字与`数字/秒`，后者保持单位，不乘提示词时长或猜输出长度。
未知格式只输出摘要，不回传任意价格文字。

- quoted_estimate/displayed_estimate_only：当前请求的无单位显示金额，仍是预估。
- quoted_rate/unit_rate_only：显示每秒费率，不是总价。
- quote_pending/quote_unavailable：暂无可用金额，不是免费。
- total_credits/output_duration_seconds始终null；spend_ceiling_verified、charge_scope_verified、
  final_billing_verified始终false。没有本次付费批准，也不据此自动提交。

## 现场观察

2026-10-07，同一获批空首页的默认模式：
- 图片5.0 Pro/1K：amount=6，标签积分消耗6。
- 视频SD2.5/30秒/720P：amount=600，originalAmount=780且划线，标签积分消耗600。
- 音频SeedAudio1.0/44.1kHz：amount=0.33/秒，标签积分消耗0.33。

首次图片/视频读数在加载中为空；切回音频首次完整比较也因临时报价缺失而失败，
保留`/private/tmp/atm-xyq-home-quote-restore-first-20261007.json`，原草稿SHA当时已经一致。
之后明确等待实际价格控件出现，稳定观察与最终完整音频原稿均核对；没有重复提交任何生成。
原完整SHA cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf，
余额6396，零提示词/参数值写入、上传、生成和消费；默认模式临时切换后全部恢复。
真实快照：`/private/tmp/atm-xyq-home-quote-image-stable-20261007.json`、
`/private/tmp/atm-xyq-home-quote-video-stable-20261007.json`、
`/private/tmp/atm-xyq-home-quote-observed-restored-20261007.json`；
截图`/private/tmp/atm-xyq-home-quote-restored-20261007.jpg`（0600）。

## 源码、隔离测试与真实生成CLI验收

新闭包10文件pin `4d14f22835161254af05445445c9f4ed0fd838c9d4ca27ba1868e6a0629832cc`。
`generated/xyq-web-home-quote-stage/`默认17包，原16条定义SHA全部保持。
新增`~/.opencli/clis/xyq-home-quote-bound/quote.js`单独加载，loader SHA
`76015328996528e08101f15bfe3f41740812459320a800602b9d99d5e3be5689`；
原12条注册/闭包、App、生产ATM/vault和用户级Skill保持。
安装计划/回执 `/private/tmp/atm-xyq-home-quote-install-plan-20261007.json`、
`/private/tmp/atm-xyq-home-quote-install-20261007.json`（0600）。

最终208 Node / 285 Python（79非浏览器、206原生隔离），全部通过、零跳过。
新增12 Node/29 Python覆盖三种模式、rate/折扣、缺失/忙态/未知、错槽位/重复节点/划线、
菜单/错误页面、草稿/价格/submit竞态、输入摘要、同请求键复用且不读取vault。
原生供应商请求全部由夹具响应或终止，body保持、零生成；没有改浏览器策略。
Focused首轮2项隐私断言失败是RPC测试输出夹带旧form reader的raw成本观察；
测试回执改为只返回所需基线digest，新报价本身已只回传合法数字或摘要，隐私断言保留。
全套首轮1项失败是旧首页测试只枚举原16条绑定ID；添加新home_quote明确预期，
原16条路由和定义比较全部保留。初轮日志/XML留存，最终回归为
`/private/tmp/atm-xyq-home-quote-all-node-20261007.txt`、
`/private/tmp/atm-xyq-home-quote-all-20261007-r2.xml`。

生成tool.py→新隔离ATM（仅3定义）→已安装App→同一已批准空首页通过9个阶段：
before状态、音频报价、图片默认模式/报价、视频默认模式/报价、恢复音频、final状态/报价。
仅3次mode_input，无模型/参数值/提示词/文件输入；图片显示6，视频当前600/划线780，
音频0.33/秒，均完整草稿绑定。final-quote job
`f32d6942-7594-44f5-b9ee-c2c7b8c69761`，同请求键返回同job/result。
before/final及独立CUA的完整音频原稿相同，报价SHA
`6fd62ef76e71c4ef08185541126f47bcfe605d2ff24425c4f48afeade655fe6f`保持，
余额6396、空稿/附件0/菜单关闭，零上传/生成/消费。

真实job/产物目录 `/private/tmp/atm-xyq-home-quote-e2e-20261007/`；
独立源码只读 `/private/tmp/atm-xyq-home-quote-real-source-20261007.json`，终态
`/private/tmp/atm-xyq-home-quote-cli-cua-after-20261007.json`，截图
`/private/tmp/atm-xyq-home-quote-cli-restored-20261007.jpg`（含首页/余额，排除项目列表）；
最终核对 `/private/tmp/atm-xyq-home-quote-final-verification-20261007.json`（0600）。
实际通过仅对应空稿默认模式的显示报价，不宣称参数值写入、其它模型、单次硬预算、
付费生成、任务/下载或完整媒体目标完成；已有范围确认待回复，未借用其它供应商付费许可。

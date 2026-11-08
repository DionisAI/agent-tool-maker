# 小云雀音频显示费率报价合同

2026-10-07。`xyq.web.audio_quote` 是当前项目音频 footer 的**纯只读估算费率查询**。
它保持参数与素材，零菜单操作、上传或生成。网站登录保持浏览器所有权。
当前媒体范围见 XYQ_MEDIA_CONTRACT.md；准备/参考合同见 XYQ_AUDIO_CONTRACT.md。

## 真实网页锚点

只读观察获批 `ATM-XYQ-CLI-test`：Seed Audio 1.0 / 44.1kHz、一个合成 WAV 音频参考、
一个结构化引用。音频 footer 内的 `span[title="预计消耗积分"]`、`aria-busy="false"`
显示 **`1积分/3s`**。同一 footer 有 `button[data-action="audio-generate-submit"]`。
没有点击生成或为报价上传。此显示是估算费率，既不是一次生成总价，也不是已验证的输出时长。

## 输入与读取协议

- 确切 `project_id` / `canvas_id` / `node_id`，数字字符串；当前 /project URL 及
  唯一音频节点、唯一已选音频 footer 都须对应。沿用 unique_audio_node_only 关联合同。
- `settings` 只接受一个自有字段：64位小写十六进制 `expected_form_sha256`。
  摘要绑定当前模型、采样率、提示词树、结构化引用、素材卡片和实际 FileList/控件。
- 顺序为 form → price → form → price → form；所有 form 都须符合输入摘要。
  价格、加载状态或提交禁用/忙态变化报 `quote_changed`；草稿变化报 `draft_changed`。
- 已有其它层报 `dialog_open`，未知 FileList 报 `reference_state_unknown`。
  价格锚点重复、异常 aria-busy 或超界文字报 `quote_layout_changed`。
  隐藏 footer/价格保持隐藏，DOM 属性不变。无点击、导航、文件写入、认证/存储读取。

## 输出与金额语义

- `quoted_rate` / `quote_status=unit_rate_only`：返回原显示及 `credit_amount`、
  `per_seconds`、`estimated=true`。例如1积分/3s保留1与3，不舍入为0.33再反推账单。
- `quote_unavailable` / `unknown`：缺价格或格式不在已审阅的“数字积分/数字s”合同内；
  原文只返回 SHA，不输出异常/可能夹带私有内容的价格文字，更不当作免费/0分。
- `quote_pending` / `pending`：价格或提交忙态；隐藏之前的费率，等待明确的新读取。
- 所有结果均 `total_credits=null`、`output_duration_seconds=null`、
  `spend_ceiling_verified=false`、`final_billing_verified=false`、`requires_duration_quote=true`。
  提交按钮启用仅作为观察返回，不代表生成或预算已获准。
- `quote_sha256` 绑定完整 form SHA、显示价格、加载与提交状态；
  此摘要是快照标识，不是供应商锁价承诺、付费批准或完成回执。
  文件/提示词原文不输出，生成/上传标记始终为 false。
- `observed_at` 是本次源码快照时间，费率摘要不包含时间。同一个 ATM request-key
  返回保留的历史 job，不重新读取网页；需要新报价观察时使用新的只读请求键。
  这只适用于纯读取，任何上传/生成的稳定请求键继续保留，未知提交先核对再处理。

单次总价、受预算约束提交、实际输出时长/账单、任务状态及可验证下载仍分别待实现和验收。
仅凭显示费率不提交付费生成；未知结果保持未知，不换 key 或后端重提。

## 验收

源码、Node 协议、隔离原生 DOM、假子进程、真实源码只读及安装后 CLI 分开。
原普通读取入口的最近一次实机检查为独立 owned surface 的 origin_mismatch；保留原入口和失败证据。
显式绑定表单读取已通过，新费率路由也已独立通过下述实际链路；该路由的 App 内人工 handoff
不再是待办。生产 ATM 安装和生成交付仍分别待验收。

## 显式绑定费率路由：2026-10-07 实机通过

- 编译器显式 `--bound-audio-quote` 只调整既有 `xyq.web.audio_quote` 的路由、pin 与说明。
  缺省 audio-quote 保持，工具总数仍16；支持与 `--bound-home` 组合，不在失败后换后端。
- 新 `audio-quote-bound.mjs/.js` 复用原报价合同及 audio-bound 的公开 Page/evaluate-only
  browser 路由。固定 `site:xyq-web`，沿用严格/首选 profile 元数据；参数先于 Page 构造校验。
  无 bind/unbind、导航、菜单、输入、CDP、上传或认证读取；错误保持明确且诊断避开私有内容。
- 完整依赖闭包10文件，source pin
  `8c9ca1dbac5ed34d71afd5b2413c90e3c2c3fbb0b6c8ad2d827cb1c6579a499b`。
  原 quote、audio-bound 和已加载 home-bound 的源码/pin 保持。
- 单个新只读注册 `~/.opencli/clis/xyq-audio-quote-bound/quote.js`，辅助源码在 reviewed/；
  loader SHA `73fa767c4be3a8179317d251239b2aaf9fca2feaad61425b62b3a608e09254be`。
  原两个音频读取、五个首页入口及第三方 App 保持，未加载上传/付费入口。
  安装计划和0600回执：`/private/tmp/atm-xyq-quote-bound-install-plan-20261007.json`、
  `/private/tmp/atm-xyq-quote-bound-install-20261007.json`。
- 新16包 `generated/xyq-web-audio-quote-bound-stage/`，相对于原首页准备阶段仅费率定义变化。
  仅两个只读定义安装在新 `/private/tmp/atm-xyq-quote-bound-e2e-20261007/state`，生产 vault/ATM保持。
  生成CLI → 隔离ATM → 已安装App → 原已绑定测试项目：before、quote、after 三个job completed；
  quote job `b7f54aaf-d068-48d5-9c45-d079fe6536a7`，同request-key复用同job而非重新取价。
- 实机结果 `quoted_rate/unit_rate_only`，1积分/3s，完整form SHA
  `64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97`。
  独立CUA前后完整表单、费率摘要相同，参考卡片与结构化引用保持；原首页积分6396。
  费率证据为 DOM/CLI 回执，截图保存面板状态，捕获图中费率文字未清晰呈现，不作为文字视觉验收。
  `total_credits=null`、时长未知、预算/最终账单未验证；零输入、上传、生成与消费。
- Node176、Python201（60非浏览器/141原生隔离），全通过且零跳过；
  新增8Node、5非浏览器及6原生隔离，假程序同键执行一次，新只读键才重新观察。
  回归 `/private/tmp/atm-xyq-quote-bound-all-node-20261007.txt`、
  `/private/tmp/atm-xyq-quote-bound-all-20261007.xml`。
  独立DOM前后回执 `/private/tmp/atm-xyq-quote-bound-cua-before-20261007.json`、
  `/private/tmp/atm-xyq-quote-bound-cua-after-20261007.json`，实机job/产物在上述e2e目录。
  最终源码/包锁/产物/同键复用核对 `/private/tmp/atm-xyq-quote-bound-final-verification-20261007.json`。

通过的是估算费率纯读取。实际参数写入、其它模型、音色效果、单次总价/预算内提交、任务与下载
继续单列，完整媒体目标保持进行中。

# 小云雀单次生成合同与验收

## 实现边界

Strategy 为 UI_SELECTOR；固定首页表单、报价和原生提交控件来自已观察 DOM。
浏览器维护认证；无 Cookie、Token、profile、内部端点或网络重放。
`generation.mjs` / `generation.js` 加在原媒体闭包上；编译器默认仍是18项，
显式 `--include-delivery` 追加 `xyq.web.generate`、`xyq.web.generation_status`，
这些默认路由的历史20包保留在 `generated/xyq-web-generation-stage-r2/`。
当前生产安装使用独立 `xyq-media` 命名空间的20包
`generated/xyq-media-runtime-stage-r2/`，含本页两项；完整源码 pin、绑定、
LOCAL 调度修复与分层验收见[媒体运行时合同](XYQ_MEDIA_RUNTIME_CONTRACT.md)。

`generate` 只提交已准备的完整草稿；没有自动填词、上传或重建项目。
调用绑定 expected_draft_sha256、quote_sha256、稳定 request_key，以及明确的
human_confirmed / estimated_cost_confirmed。ATM 和适配器各自检查付费/写入/代码许可。
报价应为当前单次估算、按钮可用、金额在预算内；每秒单价音频返回
total_quote_required，待取得总价合同。网页估算不承诺最终扣费上限：
spend_ceiling_verified / final_billing_verified 均为 false。

项目 `.atm/xyq-generation` 的私有 intent/active.lock 在唯一原生提交前 fsync；
再次核对报价和控件命中后才点击。一次点击后看到 project/canvas 路由只是提交证据，
provider_task_id 为 null，task_completed 为 false。协议/确认丢失保持 submission_unknown
和操作锁；同键复用、换键冲突均无第二次输入。失败只留有界错误码，避免原始桥接文本。

`generation_status` 仅查询一份原本地提交回执，provider_checked=false。
它不是供应商任务查询器，project/canvas ID 也不是媒体 task ID。
网页实际任务/结果查询、下载事件与完成文件需要各自的 DOM 合同和验收。

## 当前证据

- 新增7项 Node 协议测试；13项 Tripo/XYQ 新协议用例先通过。
- 新增15项 Python 工厂、真子进程和原生隔离夹具测试通过；相关86项回归通过。
- 最新 Tripo/XYQ Node 范围共506项通过，零失败/跳过；不是全仓库 CI。
- 原生隔离夹具验证一次点击、持久 intent、失去确认后原锁保留，以及零输入保护。
  夹具没有调用供应商，也不代表真实付费生成已验收。
- 已批准的小云雀任务中心只读观察：可见5条通知，按钮是查看项目/查看对话，
  没有媒体 task ID 或下载控件。它是通知入口，不将通知标题当作任务状态。
- 用户另批准打开“我的世界光影风格图”已有会话，仅核对结果 ID/类型/状态/下载控件，
  下载一个已有文件。现已观察图片卡与810×1080预览/下载控件，三个新增只读结果工具
  已安装并通过真实生成 CLI 链路，见[结果合同](XYQ_RESULT_CONTRACT.md)。原唯一下载
  等待超时，点击是否送达/文件落盘保持未知，没有重复点击；未读取完整提示词或生成。
  首页完整表单读取被审查暂停的历史请求和所有未知上传锁保留。
- 后续[图片下载交付合同](XYQ_DOWNLOAD_CONTRACT.md)的两项工具和常用ATM运行时已安装，
  单次原生隔离文件链路与原未知标记本地查询分别通过；不是实际供应商下载。
  原未知手动下载保护保留。
- 2026-10-08 新媒体运行时的相关538 Node/63 Python通过；原生SDK/实际App的
  LOCAL原夹具回执查询和同键复用通过。生成回执硬链接截断根因修复已部署。
  真实音频只读复验报告 origin_mismatch，未自动换页；部署不代替真实付费生成验收。

真实付费图像/视频/音频生成、预设与上传音色效果、供应商任务关联、下载落盘及
[完整解码校验](XYQ_MEDIA_DELIVERY_CONTRACT.md)仍分列待验收；当前范围不包括复杂白板/时间线。

# 小云雀会话图片结果查询

## Strategy note

- Strategy: UI_SELECTOR；Contract: visible-ui。
- Evidence: 用户批准的“我的世界光影风格图”会话，`/home` 的 integrated-agent 路由；
  `.ag-ui-assistant-message .ag-ui-x-biz-image-part` 图片卡与 `aside[class*="artifactPanel-"]`
  预览面板、图片上下文、文件名标题、返回资源列表和下载按钮均已现场观察。
- Auth source: 浏览器所有；不读认证文件、Cookie、存储或内部端点。
- Replay: 两次稳定只读元数据读取；没有导航、完整提示词读取、上传、生成或下载点击。

## 固定工具

| ATM ID | 输入 | 作用 |
| --- | --- | --- |
| `xyq.web.results` | thread_id | 当前已渲染会话图片卡/预览的资源列表 |
| `xyq.web.result_inspect` | thread_id、result_id | 精确资源的加载状态、尺寸与当前预览/卡片信息 |
| `xyq.web.result_download_quote` | 上述 ID、expected_result_sha256 | 已打开预览的文件名、尺寸与可用下载控件计划 |

三个工具仅需 execute_code，没有 external_write 或 paid；`download_quote` 只是沿用
工具链的“先核对后执行”命名，quote_kind 明示不是价格，也不会启动下载。
来源/路由为固定 site:xyq-home/browser，保留原 contextId/preferredContextId，不自动绑定、
换页、打开预览或替换旧入口。精确 thread_id、tab_name 与 agent_name 必须各出现一次。

当前资源 ID 来自已观察图片路径的 32 位十六进制段；只接受所见 p3 图片主机、
路径及 resize 变体，丢弃所有查询参数，不返回完整或签名 URL。
同一图片卡和预览合并为一个资源，优先返回预览尺寸；不同卡片数另记。
`result_id_kind=visible_media_resource`，provider_task_id/provider_task_status 为 null。
loaded 只证明浏览器图片像素已载入，不证明生成任务关联、计费或完成文件。
all_results=false：仅当前渲染图片，不是全部会话/账号任务，也没有视频/音频覆盖声明。

空态报告 no_rendered_image_results，而非全账号没有任务；加载中与损坏图片分别报告。
其他来源、未知预览结构/文件名、独立弹层、重复控件、错页、改动中的元数据明确报错。
桥接响应有严格字段/类型/大小检查；规范字段顺序后计算摘要，避免不同桥接对象序列化
导致假冲突。下载计划还要求准确摘要、已加载图片、唯一且启用/未被覆盖的原生按钮。
真实点击、下载事件与落盘/完整解码另走[下载交付合同](XYQ_DOWNLOAD_CONTRACT.md)，不在这些读取工具内推断。

## 2026-10-08 实现与验收

源码 `examples/opencli/xyq-web/results.mjs/results.js`；编译器新增显式 `--include-results`。
默认18项保持；原 --include-delivery 的20项保持；两者追加后为23包：
`generated/xyq-web-results-stage-r1/`。结果闭包 pin：
`99e0f848f994e3f030f257d9b7894660e70f96c311a28a1ae158810f40eb3dda`。
这三个新工具已追加到生产 ATM，OpenCLI 独立加载器为 xyq-results-bound；
旧定义和8个旧加载器保持，App/pipx/用户级 Skill/vault 未升级或重置。
安装计划、源码快照和回执：`/private/tmp/atm-xyq-results-install-20261008-r2/`。
原18/20项编译不代表它们全已生产安装。

- 新增11项 Node 测试；Tripo/XYQ Node 回归共517通过，零失败/跳过。
- 新增22项 Python 测试（含原生 Chrome 夹具与实际假子进程）；相关90项通过，零失败/跳过。
- 首次原生夹具5失败：测试 HTML 缺少 UTF-8，中文下载按钮变成乱码。
  修复夹具编码，原断言/安全检查保持；r1失败记录保留，最终用 r3完整回归。
- 真实生成 tool.py → 既有 ATM → 已安装 App → 获准会话，三个读取工具均通过；
  同查询键复用同 job，只有代码许可，paid_granted=false。
- 观察资源 `6da3979fd6e78317646bf1c350be2202`：卡片360×480，预览810×1080，
  文件名 minecraft_shader_cat.png，唯一下载控件启用且命中检查通过。
  截图仅包含结果面板：`/private/tmp/atm-xyq-result-preview-20261008.png`。
- 先前唯一手动下载尝试等待超时并重置连接，点击是否送达仍未知。没有再次点击。
  按资源 ID/文件名的只读事件等待超时，不解释为供应商下载失败；默认目录精确文件
  未发现，不代表其他位置不存在。原 intent 保留，新增 download_unknown 核对回执。

真实链路与原未知下载回执在 `.atm/xyq-result-delivery-validation-20261007/`。
查询与下载控件验收已完成；供应商 task 关联、下载落盘、实际文件解码、视频/音频结果
以及真实生成/音色效果继续分别待验收，不把 job completed 当作媒体交付。

随后新增单次图片下载/本地状态两个独立编译工具，原三个读取闭包和生产安装保持。
528 Node/120相关Python及真实隔离 Chrome 文件交付通过，不是供应商下载验收。
本轮用户再次指定此会话，当前渲染媒体只见一张360×480图片，无 video/audio 元素；
这是当前 DOM 片段，不是全会话历史结论。旧未知下载已登记元数据保护，没有再点下载。

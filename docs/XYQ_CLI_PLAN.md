# 小云雀媒体生成 CLI：实现路线

日期：2026-10-07。最新方向：**专注图像、视频、音频生成的网页功能对齐**，
包括音色选择、自有音色/参考素材上传、动态参数、任务和下载；Pippit 命令表仅作对照。
范围真源见 [媒体合同](XYQ_MEDIA_CONTRACT.md)。白板、故事板、3D 导演台和复杂时间线暂缓。
七个媒体基础工具已实现并生成包，实际安装和媒体业务交付尚待验收。
下文保留先前完整网站研究作为背景，不再把所有工作区作为本期完成门槛。
逐项证据见 [覆盖表](XYQ_WEB_COVERAGE.md)。

## 1. Tripo 已有实现是什么

当前 `tripo.studio.*` 是本项目编写的网页适配器，不是 Tripo 开发者 API SDK。

```text
Agent / 生成的 tool.py
  → ATM 工具定义、schema、代码摘要、权限、request-key 和 job
  → 固定网页适配器
  → 本机 OpenCLIApp 浏览器桥 → 已登录的 Chrome
  → Tripo Studio 可见 DOM / 原生输入 / 下载
```

独立服务器路线使用同一份适配器和权限合同：

```text
服务器 Agent → 服务器 ATM → 本机 Unix socket
             → 服务器自己的持久 Chromium → Tripo Studio
```

- 源码真源：`examples/opencli/tripo-studio/`。
- 编译器：`scripts/build_tripo_studio.py`；输出 manifest 和调用 ATM 的 Python CLI 包。
- 服务器驱动：`studio_runtime.py`，固定 Tripo origin、持久上下文、私有 Unix socket、单操作互斥。
- 浏览器持有登录，适配器读取网页业务数据并操作明确控件；认证材料不进入工具输出。
- 查询、表单准备、付费提交分开。付费路径先持久化回执，再执行一次点击；模糊结果保留锁并先核对上游。
- `submitted` 不是模型完成，模型完成不是下载完成，文件取得也不是 Unreal 导入完成。

当前有 31 个业务操作定义，但 [UI 覆盖合同](TRIPO_UI_PARITY.md)与[服务器验收](TRIPO_SERVER.md)
仍逐项记录缺口。工具数量不是全网页覆盖证明。

## 2. 小云雀已有基础

当前本机发现：

- npm 包：`@pippit-dev/cli` **1.0.38**。
- npm 入口：`/Users/xinhuang/.nvm/versions/node/v24.12.0/bin/pippit-tool-cli`。
- 包来源元数据：`https://github.com/Pippit-dev/cli`。
- 已运行版本、帮助及离线 Canvas 目录/说明；**没有运行登录、余额、上传或生成**。
- 离线 Canvas 目录 schema 版本 2，**47 个语义命令、8 个类别**。

八类为 asset、canvas、checkpoint、generation、role、scene、scene3d、timeline。
47 是“可发现的命令数量”，不是 47 项真实业务验收结果。

[上游 CLI](https://github.com/Pippit-dev/cli)及本机帮助显示原生生图/生视频、媒体处理、
会话、短剧和营销入口。Canvas 语义命令通过 npm JS/SDK 层执行，纯 Go 二进制帮助
不证明该运行时就绪；此次确实加载了离线目录与两个 query 的 schema 摘要。

## 3. 两条后端路线

### 已确定：媒体生成网页优先，不由官方 CLI 定义范围

```text
Agent → ATM xyq.web.* 工具 / 生成 CLI
          → 受审阅的业务网页适配器
          → 当前机器的已登录浏览器
          → 小云雀网页的实际功能
```

官方 CLI/SDK 可以作为实现参考，或在未来某项明确业务中作为独立后端；
“Pippit 已支持”与“网页功能已覆盖”分别记录。当前首批代码没有 Pippit 依赖。
**同一次提交失败时不自动切换后端重提**，以避免重复消费。

网页路线由浏览器保持登录；CLI 的独立授权是另一种认证路径。
远端使用自己的浏览器 profile，认证仍不进入 ATM 常规 Key 同步。
远端登录步骤、系统安全凭证库及具体供应商行为需要独立验收。

### 网页后端的实现边界

结构参照 Tripo，但小云雀拥有会话、画布、短剧、故事板及媒体编辑等不同工作区。
需在实际 UI 中观察每项控件/状态/报价，再建立适配器；当前公开教程不是选择器证据。
现有 Tripo server runtime 固定 origin 和 bundle，直接替换 URL 不构成通用浏览器后端。
只有确实需要复用服务器路线时，再提取最小共享驱动并保留 Tripo 回归。

## 4. 完整覆盖清单

| 业务域 | 当前发现的官方能力 | ATM 接入与验收需求 |
|---|---|---|
| 身份/积分/模型 | status、登录/退出、积分、model list/describe | 人类授权；本地凭据存在与服务器认证有效分开；参数从真实模型配置发现 |
| 图片 | generate-image、参考素材及模型参数 | 上传独立确认，报价/预算合同，单次提交、进度和图片交付 |
| 视频 | generate-video，参考/编辑/延长/首尾帧、Draft 转成片参数 | 不猜枚举；保留原任务标识、区分 Draft/成片、媒体验证 |
| 媒体处理 | 超分、擦字幕 | 文件范围、摘要、费用及输出媒体检查 |
| 通用会话 | submit-run、get-thread、list-thread-file | thread/run 分离；续接沿用原会话；等待人类问答不是完成 |
| 短剧 Agent | +submit-run、+upload-file、会话与产物查询 | 剧本→资产→故事板→视频各阶段独立验收；保留后端问题和确认 |
| 营销 Agent | upload、generate、query、balance | 请求 schema、等待确认状态、新 run 关联、成片交付 |
| 个人画布 | create/get/upload/allocate/apply 及语义操作 | 真实 ID、版本/权限、先查询后变更，再回读验证 |
| 角色/场景/布局/连线 | create_biz_node、资料更新、布局与连线操作 | 保留既有内容，不把创建节点当作媒体生成 |
| 3D 导演台 | scene3d.query/apply | 对象/机位/关键帧文档编辑；截图/渲染另列缺口 |
| 多轨时间线 | timeline.query/apply | latest expectedRevision、时间单位、输出配置；最终视频导出另验收 |
| 检查点 | 创建/列表/比较/恢复 | 按账号/画布隔离；恢复是写入；本地检查点不是跨机器账户备份 |
| 网页扩展能力 | 教程描述的编辑/工作区动作 | 与 CLI/SDK 逐项比对，真实 UI 观察后决定是否需要 DOM 补齐 |

当前 Skill 明示的领域缺口包括：**故事板镜头增删排序/脚本保存/指定镜头生成**、
**3D 截图/渲染**、**多轨最终视频导出**。低层 patch 或提示词更新不冒充这些业务操作。
缺口应对当前 CLI 和 UI 重新核对，Skill 是本机文档证据，未代表当前网站实际状态。

网页覆盖参考：[教程中心](https://xyq.jianying.com/tutorials)、
[创作画布手册](https://xyq.jianying.com/tutorials/creation-agent-canvas)、
[短剧画布手册](https://xyq.jianying.com/tutorials/short-drama-agent-canvas)。
公开资料只建立候选清单，真实浏览器验证后再标为可执行。

## 5. ATM 层的必要合同

- 固定工具映射、类型化 schema 和 origin；排除任意 argv、任意 URL 和任意低层 patch 透传。
- 权限至少分查询、编辑/上传、付费、发布；删除先核对可恢复机制及用户范围。
- 摘要覆盖**实际 native binary、Node/JS 入口和 Canvas runtime 依赖**。
  仅绑定 npm symlink/launcher 的摘要会漏掉下游二进制或 SDK 被替换的情况。
- 缺失运行时明确失败；执行过程中不通过官方 launcher 自动安装/升级依赖。
- 显式 Key 环境覆盖与 CLI 登录账户分开识别；不静默切换到账户或计费来源。
- 付费前绑定原始指令、素材摘要、模型/参数、报价和预算；报价未知时报告未知。
  若官方 CLI 缺少费用预检或预算原子约束，单独标出该缺口，消费硬上限尚无保障。
- request-key、输入指纹、持久化提交意图、上游 task/thread/run ID、单操作锁。
  网络超时或进程失败可能已经提交，先核对任务而非重试/换后端。
- 区分 ready/pending/needs_login/needs_input/submitted/completed/failed/submission_unknown。
- 下载留在明确项目路径，保留 SHA256、类型及媒体检查；CLI 退出码不是创作交付验收。

## 6. 当前分阶段落地

1. **媒体基础**：登录/积分、生成模式、模型/动态选项与草稿绑定准备。
2. **音色与参考**：定位结构化音色入口、已有音色选择、自有音色/参考素材上传与引用。
   用隔离素材验收代码；真实文件绑定新的明确批准。
3. **生成交付**：图像/视频/音频报价、稳定请求键单次提交、任务状态、下载与媒体验证。
   用具体模型、素材和预算批准真实测试，不沿用 Tripo 的批准。
4. **同域功能补齐**：对照实际网页的生成/编辑/延长/首尾帧等参数逐项回归、源 pin 和真实复测。
5. 复杂工作区和远端运行另列后续阶段，不扩展本期媒体生成验收范围。

交付名保持 `atm`；业务入口是 `xyq.*`，需要时由 ATM 生成项目内 `tool.py`。
最终验收表逐项区分“已定义 / 假测试通过 / 真实只读 / 真实写入 / 真实付费 / 完整媒体交付”。
首批实现是只读基础，不把完整 CLI 当成已经实现。

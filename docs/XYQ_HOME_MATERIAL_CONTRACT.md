# 小云雀首页素材发现：只读 CLI 合同

2026-10-08。新增两项已安装的只读工具；这是素材入口发现，不是上传实现、音色效果
或完整生成验收。当前生产目录共27项 `xyq.web.*`，范围见 [媒体合同](XYQ_MEDIA_CONTRACT.md)。

## 工具与执行边界

| 工具 | 输出与前提 |
|---|---|
| `xyq.web.home_material_state` | 首页完整草稿 SHA、当前素材输入的声明格式/多选/启用/文件数量；菜单须关闭 |
| `xyq.web.home_material_choices` | 读取已经打开且精确关联的素材菜单；不读被遮罩的完整草稿，`draft_bound=false`、草稿 SHA 为 null |

两项均为 `paid=false`、仅 `execute_code`、空对象输入；适配器只有 evaluate 能力。
固定使用已由人同意的 `site:xyq-home`，继承公开 profile 路由；没有自动绑定、导航、
开关菜单、文件选择、资产选择、上传、生成或下载。CLI 菜单查询与 CUA 打开/关闭菜单分列。
重复请求键复用原 job，返回的是历史快照，不是当前菜单或草稿重新核对。

源码：`examples/opencli/xyq-web/material-home.mjs`、`material-home.js`。
编译器：`scripts/build_xyq_material.py`；包：`generated/xyq-home-material-stage-r1/`。
独立12文件闭包 pin：
`7b14a687050cbff4716f9e5afb238608bdc0d299bfc104cd93cd8808ac8d01a5`。
加载器：`~/.opencli/clis/xyq-home-material/material.js` 与 `reviewed/`；原生命名空间
`xyq-material`，UI/browser=true/read。旧20项媒体闭包 `06d659...11fd23` 保持。
唯一用户安装命令仍为 `atm`。

## 实际 DOM 与失败边界

- 精确 origin `/home`，唯一 `#title-section-prompt-container` / prompt-composer /
  上传素材按钮 / uploadInputArea；不是在全页猜测一个 file input。
- 当前上传区域恰有两个输入：multiple/accept 的本地上传，以及“替换素材文件”的单选输入。
  ZIP/技能与独立视频输入在该区域外，替换输入不解释为新的本地上传。
- 菜单必须是唯一可见层，trigger/menu 的 controls/labelledby 双向关联，open 状态一致。
  只读该自有 Radix mask；保留网页属性，独立 mask、其它对话框或结构变化报明确错误。
- 菜单标题是单个纯文本 span，条目数/长度/语法有界；当前三个标签映射业务 kind，
  后续新标签标为 unreviewed，避免当作可执行动作。
- 声明 accept 只接受有界扩展名/MIME 语法；字段超集、URL、重复、竞态报明确错误。
  闭合状态前后核对完整稿 SHA；打开菜单前后核对素材元数据，不伪造完整稿绑定。
- 文件状态未知保留 null；不读文件名或文件字节。输出没有完整提示词、认证信息或素材 URL。

## 当前网页观察与真实 CLI

当前空首页为音频生成 / Seed Audio 1.0 / 44.1 kHz，草稿 SHA：
`cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf`。
本地上传声明图片 JPG/JPEG/PNG/WebP/BMP/GIF、视频 MP4/MOV、音频 WAV/MP3；
另有文档格式，实际完整列表由 DOM 返回。菜单为“本地上传 / 资产库 / 预设提示词”。
这是当前网页的格式声明；大小、时长、数量限制、服务器接收与音色效果仍另行验收。

生成 tool.py → 常用已安装 ATM → 已安装 OpenCLIApp → 真实绑定首页：

- 素材状态 job `77e55668-7906-4318-a24e-a93e327580c2` completed，完整稿绑定、文件数量0。
- 素材菜单 job `0b6487c8-12eb-467d-834c-9b6db4ab188b` completed，三个实际条目；无完整稿绑定。
- CUA 仅打开并关闭精确素材菜单，关闭后完整表单与之前逐字段一致；两项同键同 job 复用通过。
- 获准会话“我的世界光影风格图”的结果查询 job
  `91a30664-c985-42f2-ba25-4b43b3144257` completed：当前渲染图片1、视频0、音频0。
  资源 ID 不是供应商 task ID，`all_results=false`；该观察不涵盖完整会话历史。
- 返回首页后 job `0a5e05f6-922d-4310-b60a-9a2b34522e9f` completed，完整原稿仍逐字段一致。
  浏览器 back 曾回到 blank，已用此前核对的首页地址恢复；一次可见等待超时保留为加载诊断，
  后续 DOM 与实际 CLI 读回通过，没有输入字段或重绑。

原绑定尝试被自动审查暂停，之后用户明确批准“仅本轮小云雀只读绑定”才执行。
本轮结束用官方 unbind，回执为 `unbound=true / site:xyq-home`，网页/登录/草稿保留。
独立音频项目的 `site:xyq-web` 绑定与此前 origin_mismatch 仍待处理，首页修复不代替它。
直接 App 无 shim 的本地元数据调用曾输出空文件，不计验证；正式 `__opencli_shim list`
核对1361注册，1359既有项保持，新增两项。没有重启 App 或安装第三方更新。

## 验收与保留

- 相关 Node：549 passed / 0 failed / 0 skipped，其中新模块11项。
- 新 Python：14 passed / 0 failed / 0 skipped；含 manifest/pin、Router→真实子进程（假 App）、
  同键复用以及全网络拦截的原生 Chrome DOM 正反例。Router 测试不称为 tool.py 测试；
  上述真实 tool.py 链路另有实际 job 收据。
- 222目录定义，220既有定义、131既有 XYQ 源文件与8份原保护回执保持；
  新12源码和根加载器与审阅摘要一致。App/vault/旧上传与下载锁保持。
- 仓库收据：`.atm/xyq-home-material-validation-20261008/verification.json`；
  临时安装收据：`/private/tmp/atm-xyq-home-material-install-20261008-r1/`。

本轮零文件上传、零生成、零下载、零付费提交。真实首页上传、预设音色/引用效果、
非默认模型全量参数、视频/音频结果与下载仍待验收；原 MP3/图片下载未知状态保留。
相关测试通过不等于全仓 CI 全绿；未发布、提交或合并。

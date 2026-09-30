# Agent Tool Maker · v0.2 路线图

目录覆盖不是供应商全功能实现。CLI/API 协议测试与真实账号/桌面验收分开记录；所有云端生产账号 live_tested=false。

原调研 **66** 项全部映射：{'native_partial': 56, 'handoff_only': 9, 'mcp_bridge': 1}。仓库包含 **157 个动作入口**；动作数不是平台数。

## 本版 / 下一阶段 / 后续

| 阶段 | 待做能力 | 验收门槛 |
|---|---|---|
| 0.3 · 实际账号验收 | OAuth 登录和刷新 | 不复制明文令牌到 Agent 对话；撤销、失效和刷新失败均可复现。 |
| 0.3 · 实际账号验收 | 跨平台 CLI / SaaS 实测矩阵 | 先 Cloudflare、OpenCLI、Buffer、Figma；记录 OS、版本、权限和消费，不以模拟代替生产。 |
| 0.3 · 事件与长任务 | Webhook 收件、签名校验、幂等与重放 | Tally/Stripe/Resend 的重复或伪造事件不能引发重复发布/交付。 |
| 0.3 · 事件与长任务 | 长驻进程与挂起工作流管理 | Tunnel/MCP 进程启动、停止、恢复和崩溃回收可观测。 |
| 0.4 · 垂直工具包 | Marvelous Designer / CLO / FreeCAD | 许可软件 + 版本匹配脚本 + 可编辑工程和导出文件真实验收；实物另外确认。 |
| 0.4 · 垂直工具包 | 社交发布与外包采购 | 账号/素材/时间或合同/金额有独立批准；超时先对账，不盲目重发/付款。 |
| 后续 · 强权限边界 | 受限执行侧车与可信批准界面 | 不能由同一不可信 Agent 自己给自己升权；明确操作系统威胁模型。 |
| 后续 · 可选托管平台 | 统一余额、Crypto、报价和预算预留 | 合法供给、并发预留、最大成本、退款和对账先于商业开放；BYOK 永久可用。 |

## 66 项逐项对应

### 01 需求与信息收集

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| OpenCLI | 已实现有限动作<br>`opencli.list`, `opencli.doctor`, `opencli.hackernews_top`, `opencli.bilibili_hot`, `opencli.zhihu_hot`, `opencli.browser_state`, `opencli.xiaohongshu_search`, `opencli.xiaohongshu_note`, `opencli.xiaohongshu_comments`, `opencli.twitter_search`, `opencli.reddit_read` | 更多站点动作按安装版本逐项生成适配器；真实登录、站点返回和发布操作验收。 |
| Exa | 已实现有限动作<br>`exa.search` | 真实搜索配额与结果来源验收；高级搜索、分页和资料更新策略。 |
| Firecrawl | 已实现有限动作<br>`firecrawl.scrape` | 真实网站抓取、登录/反自动化边界、分页和作业恢复；保留资料来源。 |
| Apify CLI / Actors | 已实现有限动作<br>`apify.run`, `apify.run_status`, `apify.dataset_items` | Actor 级输出和费用约束、运行轮询到结果的复用工作流；当前分别提供提交、状态与数据页。 |
| DataForSEO | 已实现有限动作<br>`dataforseo.search_volume` | 地域/语言与付费账户验收；扩展其他关键词接口与异步任务。 |
| Google Trends API | 交接入口，待外部执行<br>`google_trends.handoff` | 官方 API alpha 准入与账号验收；本版只产出浏览器任务单。 |
| YouTube Data API | 已实现有限动作<br>`youtube.search`, `youtube.comments` | OAuth 登录/刷新和上传流程；分页、权限与配额测试。 |

### 02 需求验证、办公与项目记录

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| Google Workspace CLI (gws) | 已实现有限动作<br>`gws.drive_files`, `gws.gmail_messages`, `gws.calendar_events` | 细粒度 OAuth 引导与续期、文档编辑和邮件发送；当前只有三个有限读取动作。 |
| Notion MCP | 已实现有限动作<br>`notion.search`, `notion.create_page`, `notion.mcp_tools`, `notion.mcp_batch` | 托管 MCP OAuth、工作区真实读写；版本特定文档结构验收。 |
| Linear MCP | 已实现有限动作<br>`linear.issues`, `linear.create_issue`, `linear.mcp_tools`, `linear.mcp_batch` | 托管 MCP OAuth、真实团队/权限回读和完整分页。 |
| Tally Webhooks | 交接入口，待外部执行<br>`tally.handoff` | 公共 webhook 接收器、签名校验、去重与响应持久化；当前只交接配置工作。 |
| Typeform Developer Platform | 已实现有限动作<br>`typeform.forms`, `typeform.responses`, `typeform.create` | 真实账户创建/回读、webhook 收件与表单展示验收。 |
| Pandoc | 已实现有限动作<br>`pandoc.to_markdown`, `pandoc.to_docx` | 跨平台与复杂版式验收。DOCX 动作采用固定无过滤器命令并要求 execute_code，不宣称 Pandoc 沙箱隔离。 |

### 03 外包与人工工作交接

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| Upwork | 已实现有限动作<br>`opencli.upwork_search`, `opencli.upwork_detail`, `upwork.handoff` | 当前 OpenCLI 仅搜索/读取；官方 API 准入、报价/授标/付款均未自动实现。 |
| Freelancer API | 已实现有限动作<br>`freelancer.active_projects`, `freelancer.handoff` | 真实 API 权限及分页；选人、授标、里程碑与付款的分别审批。 |
| Fiverr | 交接入口，待外部执行<br>`fiverr.handoff` | 未依赖未经核实的通用 API；目前只生成并跟踪人工任务与文件交付。 |

### 04 设计与原始素材制作

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| Figma MCP | 已实现有限动作<br>`figma.file`, `figma.mcp_tools`, `figma.mcp_batch` | 托管 MCP 认证与版本协商、真实文件写入和可编辑结构验收。 |
| fal | 已实现有限动作<br>`fal.generate` | 模型级 schema/价格同步、真实付费请求、下载与费用对账。 |
| ElevenLabs | 已实现有限动作<br>`elevenlabs.tts`, `elevenlabs.web` | 真实音色权限、音频质量、用量与账单验收。 |
| Higgsfield | 已实现有限动作<br>`higgsfield.generate`, `higgsfield.web` | 真实 API/网页两个计费路径独立验收；不自动跨账号或跨余额回退。 |
| Tripo | 已实现有限动作<br>`tripo.text_to_3d`, `tripo.web` | 真实模型任务、材质/拓扑与网页端 GLB 性能验收。 |
| 小云雀 CLI | 已实现有限动作<br>`xyq.image`, `xyq.video` | 在安装官方 CLI 并登录的设备上验证真实生图/生视频；不搬运原始网页登录凭证。 |
| ComfyUI | 已实现有限动作<br>`comfyui.queue`, `comfyui.submit`, `comfyui.history` | 已安装模型/节点的真实队列验收；模型资源和节点代码并不由 ATM 提供或沙箱化。 |
| Pexels API | 已实现有限动作<br>`pexels.web`, `pexels.photos`, `pexels.videos` | 真实 API 查询、分页与素材许可/来源留存；本版不自动下载所有检索结果。 |

### 05 修改、后期处理与资产验收

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| FFmpeg / FFprobe | 已实现有限动作<br>`ffmpeg.probe`, `ffmpeg.audio_to_mp3`, `ffmpeg.trim`, `ffmpeg.thumbnail` | 增补字幕、拼接、混音等经过独立测试的动作；音视频内容质量另行判断。 |
| ImageMagick | 已实现有限动作<br>`imagemagick.resize`, `imagemagick.webp` | 更多固定编辑操作、资源配额、跨平台与异常图片测试。 |
| Remotion | 已实现有限动作<br>`remotion.compositions`, `remotion.render` | 安装对应版本与运行真实项目；模板、字体和许可由项目维护，不自动安装运行陌生代码。 |
| Photopea Scripting API | 交接入口，待外部执行<br>`photopea.web`, `photopea.handoff` | 浏览器内脚本桥接与 PSD 图层验收；本版交接，不自动执行用户脚本。 |
| whisper.cpp | 已实现有限动作<br>`whisper.transcribe` | 模型安装与真实语音转写、字幕时间轴/语言质量验收。 |
| Blender | 已实现有限动作<br>`blender.inspect`, `blender.render` | 安装 Blender 后验证两个打包脚本；模型优化、动画、材质及 GPU 渲染矩阵。 |
| glTF Transform | 已实现有限动作<br>`gltf.inspect`, `gltf.optimize` | 实际 CLI 与模型检查/优化结果；不把 GLB 体积变小当成视觉无损证明。 |

### 06 服装、工业与硬件

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| Marvelous Designer | 交接入口，待外部执行<br>`marvelous_designer.handoff` | 需要有许可且已安装的桌面软件和匹配版本 Python API；原生脚本自动执行、工程输出、试穿/打样未实现。 |
| CLO | 交接入口，待外部执行<br>`clo.handoff` | 需要已许可桌面环境；自动导出工程、BOM/纸样及实物打样验收。 |
| FreeCAD | 交接入口，待外部执行<br>`freecad.handoff` | 安装并验证 FreeCAD Python/控制台，参数化脚本、FCStd 与制造文件导出；本版桌面交接。 |
| KiCad CLI | 已实现有限动作<br>`kicad.drc`, `kicad.gerbers` | 安装匹配 KiCad 后用真实板卡进行 DRC/Gerber 验收；实板安全与电路效果另行评审。 |

### 07 开发、调试与验收

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| GitHub CLI (gh) | 已实现有限动作<br>`github.repo`, `github.issues`, `github.runs`, `github.pr_checks`, `github.create_issue` | 真实 gh 登录与指定仓库权限、CI 回查；暂不提供自动 merge 或任意 shell。 |
| Docker | 已实现有限动作<br>`docker.ps`, `docker.build` | 真实 Docker 守护进程与受控构建；不把 Docker socket 当作安全沙箱。 |
| Playwright CLI / MCP | 已实现有限动作<br>`playwright.test`, `playwright.mcp_tools`, `playwright.mcp_batch` | 真实应用端到端测试与账号授权；MCP 仅协议桥，不假设自带浏览器登录。 |
| Chrome DevTools MCP | MCP 协议桥接<br>`chrome_devtools.mcp_tools`, `chrome_devtools.mcp_batch` | 连接已批准的调试浏览器，发现真实工具并加入白名单后验收；未内置浏览器实例管理。 |

### 08 部署与软件分发

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| Cloudflare Wrangler | 已实现有限动作<br>`wrangler.deployments`, `wrangler.build`, `wrangler.preview`, `wrangler.deploy`, `wrangler.d1_list`, `wrangler.d1_local` | 真实账号预览/生产部署、费用、HTTP 与业务回读；数据存储需独立回滚方案。 |
| Cloudflare Tunnel / cloudflared | 已实现有限动作<br>`cloudflared.tunnels` | 当前只列出现有命名 Tunnel；长驻进程监督、启动/停止/健康检查和共享 URL 生命周期尚未实现。 |
| Cloudflare DNS API | 已实现有限动作<br>`cloudflare.dns_list`, `cloudflare.dns_create` | 真实受限域名 token 的记录创建/传播回查；未实现域名购买或全账户 DNS 任意修改。 |
| Vercel CLI | 已实现有限动作<br>`vercel.list`, `vercel.preview`, `vercel.production` | 账号与项目实测、部署 URL 验收、日志/回滚；生产和预览权限分开。 |
| Supabase CLI | 已实现有限动作<br>`supabase.projects`, `supabase.migrations`, `supabase.db_push`, `supabase.function_deploy` | 生产迁移恢复演练、真实 Function 回查；读取动作不导出服务密钥。 |
| Expo EAS | 已实现有限动作<br>`eas.build_list`, `eas.build` | 当前提交构建与查看构建，不包含应用商店提交/签名自动管理；提交不等于构建或上架完成。 |
| Godot command line | 已实现有限动作<br>`godot.export` | 真实引擎、导出模板和可运行游戏验收。 |
| itch.io butler | 已实现有限动作<br>`butler.status`, `butler.push` | 实际上传渠道和可见性验证；上传命令完成不等于发布内容获人工认可。 |

### 09 内容发布与营销

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| Buffer CLI / MCP / API | 已实现有限动作<br>`buffer.channels`, `buffer.posts`, `buffer.schedule`, `buffer.schema` | 真实连接频道、排期与已发布状态回读；CLI schema 漂移和失败后的对账。 |
| Postiz / Postiz Agent CLI | 已实现有限动作<br>`postiz.integrations`, `postiz.posts` | 当前读取集成和帖子；媒体上传、平台特有发布参数、排期写操作仍在计划。 |
| TikTok Content Posting API | 交接入口，待外部执行<br>`tiktok_posting.handoff` | 需要合规应用授权/审核及公开可见性条件；本版只交接，不自动上传发布。 |
| WP-CLI | 已实现有限动作<br>`wordpress.posts`, `wordpress.draft` | 真实站点草稿/读取；主题插件与数据库高风险维护未开放。 |
| Ghost Admin API | 已实现有限动作<br>`ghost.posts`, `ghost.draft` | 真实站点草稿回读、图片上传与公开发布的独立授权。 |
| Google Ads API | 交接入口，待外部执行<br>`google_ads.handoff` | 开发者 token/OAuth 准入、报表与广告草稿；本版不运行广告或变更预算。 |

### 10 收款、交付、客服与协作

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| Stripe API / CLI | 已实现有限动作<br>`stripe.products`, `stripe.checkout_test`, `stripe.events` | 仅测试 Key 的 Checkout 创建；webhook 验签和交付、真实收款/退款全部需额外实现和验收。 |
| Shopify CLI | 已实现有限动作<br>`shopify.theme_list` | 本版列出主题；主题构建/上传与应用发布需要真实店铺授权验收。 |
| Shopify Admin GraphQL API | 已实现有限动作<br>`shopify.products`, `shopify.product_draft` | 本版产品读取与 DRAFT 创建；库存、公开上架、订单履约与退款分开实现。 |
| Printful API | 已实现有限动作<br>`printful.products`, `printful.order_draft` | 仅目录和未确认订单草稿；禁止自动确认生产/付款，实物履约单独验收。 |
| Resend | 已实现有限动作<br>`resend.send` | 已验证发信域、明确收件人及真实邮件到达；退信、退订/收件事件未实现。 |
| HubSpot APIs | 已实现有限动作<br>`hubspot.contacts` | 当前只读取联系人；真实 CRM 写入、分页与团队工作流验收。 |
| Slack APIs | 已实现有限动作<br>`slack.history`, `slack.send` | 真实工作区/频道最小权限与消息回读；不自动收集任意历史。 |
| Telegram Bot API | 已实现有限动作<br>`telegram.me`, `telegram.send` | 真实 Bot/chat 授权及消息回读；入站 webhook 和回调审批身份尚未实现。 |

### 11 数据反馈与持续运行

| 工具 | 本版状态与动作 | 尚未实现 / 待验证 |
|---|---|---|
| PostHog | 已实现有限动作<br>`posthog.query`, `posthog.mcp_tools`, `posthog.mcp_batch` | 实际埋点覆盖与查询验收、托管 MCP OAuth；查询成功不代表数据完整或分析正确。 |
| Sentry MCP | 已实现有限动作<br>`sentry.issues`, `sentry.mcp_tools`, `sentry.mcp_batch` | 真实项目错误、MCP 工具兼容、修复后复测；不会自动关闭 Issue 或宣称错误消失。 |
| Google Search Console API | 已实现有限动作<br>`search_console.sites` | 当前只列站点；搜索表现查询、分页和数据窗口检查尚未实现。 |
| YouTube Analytics API | 已实现有限动作<br>`youtube.analytics` | 真实频道 OAuth 与报告权限、覆盖窗口及分页；不提供竞品内部数据。 |
| n8n | 已实现有限动作<br>`n8n.workflows`, `n8n.activate` | 已有工作流读取/激活；签名入站接收和长流程调度依赖实际 n8n 部署，不是 ATM 的后台承诺。 |

## 路线图不是承诺

所有阶段以验收门槛而非日期排序。网页版、桌面和人工任务单不会自动操作网页/软件或雇人；提供真实文件后，只记录文件级验收和宿主声明。生产账号、平台审核、许可软件与应用商店审批不能由模拟测试替代。

验收证据见 `TEST_REPORT.md`、`../reports/pytest.json`；具体动作、参数、权限和官方来源见 `TOOL_CATALOG.md` 与 `atm describe`。

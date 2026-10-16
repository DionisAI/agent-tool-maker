# 小云雀既有图片下载与本地交付

## Strategy / 边界

Strategy: UI_SELECTOR + LOCAL；Contract: visible-ui / decoded-local-file。
下载控件来自[会话图片结果合同](XYQ_RESULT_CONTRACT.md)观察的预览；认证仍由浏览器所有。
仅精确 thread_id / result_id 的当前 PNG 预览，不导航、打开预览、读完整提示词或认证数据。
上传、生成、积分消费、供应商任务查询和视频/音频下载均不在这个图片下载实现内。

| ATM ID | 输入 | 权限 | 阶段 |
| --- | --- | --- | --- |
| `xyq.web.result_download` | 六字段 settings：thread_id、result_id、expected_result_sha256、quote_sha256、request_key、human_confirmed=true | execute_code + external_write；paid=false | 已安装；供应商交付待验收 |
| `xyq.web.result_download_status` | 原 request_key | execute_code；paid=false | 已安装；仅本地原回执与精确产物读取 |

常用 ATM 已增加 `delivery` / `media` 子命令，仍只有 `atm` 一个安装命令。
独立 `scripts/build_xyq_download.py` 固定已审阅桥接程序路径/SHA、下载目录、适配器和解码流水线 pin。
不向调用者暴露任意程序、下载根目录、URL 或认证注入参数。
**这两个定义与独立下载加载器现已安装；安装与实际供应商下载完成分列。**
原网页默认18项、追加生成20项、再追加结果读取23项保持；新下载两包单独编译。
三个生产结果读取工具的闭包 pin 保持 `99e0f848f994e3f030f257d9b7894660e70f96c311a28a1ae158810f40eb3dda`。

## 单次原生下载

`download.mjs` / `download.js` 使用固定 site:xyq-home/browser 的公开 Page API，
保留 contextId/preferredContextId；只有 evaluate、nativeClick、waitForDownload。
先验证完整结果/控件摘要、唯一启用且未被覆盖的下载按钮，再保存 fsync 的原请求和锁。
发送前再次核对摘要与命中位置；开始原始下载观察后，仅发送一次点击。
稳定 request_key 与规范字段顺序避免同一请求对象排序引起假冲突。
原生确认丢失仍等待原观察器；不因超时、同键或新键而再点一次。

下载事件必须报告 complete、规范绝对文件路径和明确的源 URL 资源关联：
当前只接受已观察的 HTTPS p3 图片主机/路径与相同32位资源 ID。
URL 仅在内部验证，签名查询参数和完整 URL 均不进入回执/输出。
仅文件名、blob URL、缺失源 URL 或其它资源事件返回 download_unknown 并保持原锁。
source_association_verified 不等于 freshness：download_freshness_verified 始终 false。
**真实 App 对该网页返回的下载事件 URL 形态尚未验收。** 合成夹具提供明确源 URL，
不据此推断真实网页一定走该路径；缺少关联证据时保留未知。
现已另用已安装 App 的公开原生 CLI 验证本机合成下载事件含 url/finalUrl，
见下节；这不是实际小云雀 CDN/Blob 下载的源关联验收。

## 文件交付 / 恢复

`website_download.py` 在启动桥接前写外层 intent / delivery-active.lock，并检查固定二进制 SHA。
固定 argv 与环境白名单，不注入 Key；桥接限时且不回传原始 stderr。
真正文件来源以持久原生回执为准，不把 stdout 的成功文字当作下载证明。
只读取固定下载目录内的一份精确文件；逐级 no-follow、普通单链接、64MiB 有界，
复制前后核对身份/大小/SHA，再重开源路径检查；不枚举其它下载或改动源文件。
独占创建项目 `.atm/xyq-result-downloads/<key-sha>.png`（0600），不覆盖已有或部分文件。
复用[本地产物校验](XYQ_MEDIA_DELIVERY_CONTRACT.md)核对 PNG 字节和完整 Pillow 解码、
文件身份及 SHA；实际解码尺寸单列，不把缩放预览尺寸当作原文件尺寸要求。

状态：dispatch_claimed → delivery_unknown / file_verified → delivered。
只有已关联原生事件 + 稳定完整解码文件才返回顶层 download_verified=true。
内嵌 artifact 是独立本地校验结果，其自身 download_verified=false；两层证据分别表达。
两个原锁完成后以 rename 留作 `.completed`，没有永久删除或未知锁清除。
外层确认丢失但原生回执已证实下载时，同键仅完成本地复制/解码，不再启动桥接。
部分锁收尾丢失时仅恢复本地校验及剩余 rename；明确保留 previous_failure 历史，
最终成功不再携带当前 failure_code/phase。未知原生事件、已有未验证文件均保持原状。
status 只查原回执与已完成精确文件，provider_checked=false；不是网页任务轮询。
provider_task_id=null，provider_generation_verified/task_association_verified=false。

已知的旧手动下载不伪造成新适配器原生回执：record-unknown 仅记录确切元数据，
同工作目录的该 thread/resource 使用任何新键都会在桥接前停止；没有自动到期/清除入口。
原“我的世界光影风格图”未知下载已登记在测试工作目录与当前仓库工作目录，
原 intent 未变；跨工作目录的标记不是全局账号去重证明。

## 2026-10-08 验收

最新两个编译包：`generated/xyq-web-download-stage-r3/`。
适配器 pin：`37db8c3f2221abcec61f59a9a48ea1f2c42b0716c6323414951f9a78b6c09164`。
流水线 pin：`e7b7f94a624272a855202773b707edab4b1e4cceb580c92788d355b43d4a416e`。
编译回执：`/private/tmp/atm-xyq-download-build-20261008-r3.json`。

- 新增11项 Node 协议测试；Tripo/XYQ Node 范围528通过，零失败/跳过。
- 新增20项 Python 本地/工厂测试及6项原生隔离 Chrome 测试；相关120项通过，零失败/跳过。
- 原生夹具全部请求由合成响应截获；覆盖单点击、确认丢失、blob 未知、禁用/覆盖零输入。
- 生成 tool.py → 隔离源码 ATM → 固定夹具桥 → 真 Chrome 点击/下载 → 安全复制/完整解码通过。
  81×108 PNG、一个原生点击、同键同 job、状态复验；未调用真实供应商或改变生产安装。
- 原唯一真实网页下载仍未知；本轮没有重复点击、上传、生成或付费。
- 用户本轮再次指定同一会话；仅读当前 assistant 媒体元素，见一张360×480已载入图片，
  未见 video/audio 元素。all_conversation_results=false，不推断未渲染历史或其它会话。

Node 回归：`/private/tmp/atm-media-download-node-full-20261008-r2.txt`。
最新 Python：`/private/tmp/atm-xyq-download-related-20261008-r6.xml` / `.txt`；
r4 误用测试选择器导致零测试，r5 未传 ATM_CHROMIUM 为89通过/31跳过；
修正名称并传入已核对的 Chrome 路径后完整回归，前述记录保留。
生成 CLI 夹具验证文件通过上述 XML 的 xyq_download_fixture_verification 属性关联。
该夹具回执与原 PNG 的逐字节副本保存在 `.atm/xyq-download-pipeline-validation-20261008/e2e/`，
对应 verification.json 另核对120/528回归、完整解码与产物 SHA；均明确 provider_called=false。
真实未知下载、保护与媒体读取证据在 `.atm/xyq-result-delivery-validation-20261007/`。
真实网页下载落盘/关联、视频/音频结果 ID/控件、真实生成和音色效果继续分列待验收。

## 已安装 App 的真实下载组件验收（同日后续）

依据[公开下载等待合同](https://github.com/jackwener/opencli/blob/main/skills/opencli-browser/SKILL.md#wait)，
该接口观察 Chrome 的下载生命周期。当前本机 SDK 类型中的 url/finalUrl 均为可选字段；
因此不把类型声明或假桥接字段当作本机实际证据，也没有放宽源 URL 的校验。

App0.1.38 / 内置CLI1.8.6 / 扩展1.0.24 保持原版本。独立 localhost 测试会话，
CLI先观察唯一随机文件名，再用当前控件 ref 点击一次，不认领/修改供应商标签页。
真实 App 返回 downloaded=true、state=complete、浏览器下载id150、url/finalUrl、
精确 filename、image/png、totalBytes246、danger=safe；这些 id 不是 provider task ID。
只读前后页分别显示0/1次点击，测试服务器只收到1次文件请求。
精确 Downloads 文件按普通单链接/no-follow/SHA检查，复制副本后完整 PNG 解码，
尺寸81×108、246字节，原文件保持；服务器明确退出，测试会话释放，不调整管理策略。
没有生成、上传、付费、凭证读取、生产包升级或下载适配器安装。

前两项探索保留：首次合成文件点击后出现 Chrome ERR_BLOCKED_BY_CLIENT，原App等待超时；
另一份独立文件通过文档化 CUA 下载观察器落盘，但并行App等待及之后的窄等待未见事件。
后者原因尚未确认；它不是实际供应商失败或全体 App 下载失效的证据。
没有重点击任何原合成文件或旧供应商请求。CUA长等待曾重置连接，恢复后先核对仍为0点击。
只有第三份独立文件的纯 CLI 组件链路作为 App 阳性验收，不混成同一个成功重试。

测试夹具 `tests/fixtures/xyq_app_download_http.py` 只监听127.0.0.1、10分钟限时。
ThreadingHTTPServer + 有界连接超时避免 Chrome 空闲预连接阻塞单线程服务器；
计数锁确保并发时也只有首个文件请求获200，其余409。新增真实HTTP并发/空闲连接用例，
以及已观察 App 事件字段形状的协议用例；真实 localhost URL仍返回 download_source_unverified。
最新529 Node /121相关Python全通过、零失败/跳过；业务代码/闭包/编译包pin保持。
回归 `/private/tmp/atm-xyq-sdk-download-node-20261008-r1.txt`、
`/private/tmp/atm-xyq-sdk-download-related-20261008-r1.xml` / `.txt`。

真实 App 回执、前后页、服务器终态、原 PNG副本/完整解码与截图：
`.atm/xyq-sdk-download-validation-20261008/verification.json` 及同目录；
三份独立测试原记录 `/private/tmp/atm-xyq-sdk-download-*.json`、
`/private/tmp/atm-xyq-sdk-download-probe-20261008-r2/`、`r3/` 保留。
旧手动下载和 Tripo 未知回执与安装前摘要一致；生产工具、旧源码加载器、vault和Skill均保持。
这是已安装 App 下载组件的验收，不是新生成 tool.py的生产安装，也不是供应商媒体交付。

## 后续：常用运行时与两项下载工具安装（2026-10-08）

本机离线构建最终 wheel；85个包内文件逐字节匹配当前源码，原依赖版本保持。
与旧安装仅 cli.py、data/SKILL.md 和新增 media.py、website_download.py 四文件不同。
先复制环境并排除旧包路径，再安装本地 wheel；不原位卸载或强制覆盖旧环境。
旧环境完整重命名保存在 pipx 管理列表之外的 runtime-backups；稳定 atm 路径及167字节
入口/SHA保持，vault/浏览器profile未读取、迁移或重置，租期没有扩展。
最终 wheel SHA `ff69ae53a2bfa42c66a89913ab2d208d7e31f2acbfb8e1e4304550e4bfc0c4aa`；
版本仍0.8.0；区分本次本地构建应核对文件/闭包摘要，而非仅看版本号。

隔离安装验收：旧运行时创建的假凭证库由新包解密；新 media 完整解码合成 PNG；
生成的 status tool.py→暂存安装ATM通过，同键同job；未知资源换新键在桥接前停止，
全部标记字节保持。真实供应商/浏览器输入均为零。

官方 maker.install 接口追加两个定义，固定绑定 atm，198个旧定义/87个旧XYQ源码文件不变；
六份原手动下载/Tripo未知或付费回执保持。新加载器 xyq-download-bound/download.js
仅增加 result-download-bound 一条原生入口，闭包保存在其 reviewed/；原三个图片读取pin不变。
已安装App的 --help 正确显示 pin/workspace/settings；没有执行下载函数或网页输入。
App/CLI版本保持；显示的1.8.8更新提示未执行。
两个用户级Skill审阅后经 atm setup 备份更新，前版与旧已审阅包一致，备份摘要逐一核对。

生成CLI→常用ATM→原未知标记的本地查询通过：job
`b851a90b-085c-4604-ae15-eaf95dd153dc`，同键复用同job和结果。
job completed仅证明查询完成；原 download_unknown、download_verified=false、
provider_checked=false、browser_input=false保持，没有新下载点击。

全仓初轮为1392通过/4失败/7跳过；其中旧about:blank管理台夹具漏加载品牌脚本，
HTTP保存实际成功而后续渲染报错，补齐真实HTML脚本依赖后17项相关验收通过。
另外三项Tripo打包快照/固定pin差异在旧安装已存在：旧已安装snapshot与仓库打包文件
逐字节相同，但与最新examples工厂不同。该修复未并入本轮；断言、Tripo源码/快照/付费锁保持。
全仓并非全绿，无提交、发布或合并。529 Node/121下载相关Python仍为独立通过证据。
安装后的最终复验另为529 Node/114项Python通过、零失败/跳过，含媒体/下载/Skill备份与README合同；
它与前述121项原生下载相关及17项UI验收分别记账，不相加或替代全仓结果。

完整安装/复验收据：`.atm/xyq-download-install-validation-20261008/verification.json`。
构建/暂存/切换原记录：`/private/tmp/atm-download-runtime-upgrade-20261008-r2/`；
工具计划与官方安装回执：`/private/tmp/atm-xyq-download-install-20261008-r1/`。
供应商图片落盘/源关联、视频音频结果合同、真实生成和音色效果仍待验收。

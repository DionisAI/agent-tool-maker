# 小云雀媒体 CLI：生产部署合同

2026-10-08。当前分支 `feat/media-cli-delivery-20261007`。生产 ATM 已追加20项
`xyq.web.*` 媒体定义；连同3项图片结果读取、2项图片下载与2项首页素材发现，共27项。
**安装、协议测试、原生夹具、真实网页和媒体交付是不同验收层级。**

## 执行与源码

- 编译器：`scripts/build_xyq_runtime.py`，最新包：`generated/xyq-media-runtime-stage-r2/`。
- 新原生命名空间：`xyq-media`；唯一用户安装命令仍为 `atm`。
- 加载器：`~/.opencli/clis/xyq-media-runtime/media.js`；32份字节一致的审阅源码位于
  `reviewed/`。根加载器只转换两个相对导入路径；闭包含声明和分派代码。
- 完整源码 pin：`06d6591e8239ed0efa216b242dac86a0900bc6d40df2392fc70809837111fd23`。
- 保留旧 `xyq-web` 等加载器及注册，没有静默替换旧浏览器入口。
  首页读取/参数/报价/提交使用既有 `site:xyq-home`；音频/项目历史使用
  `site:xyq-web`，继承公开 profile 路由。没有自动导航、bind/unbind 或错误后换页。
- `generation_status` 使用 LOCAL、browser=false，不构造 Page、不解析 profile，
  只读确切项目中的原始提交回执，不是供应商任务轮询。
- 所有20项保留原操作 schema、权限、付费属性和输入模板。上传仍有精确文件、
  摘要、项目/节点、稳定请求键及确认；生成仍有完整草稿、报价、预算及显式付费许可。
  没有读取认证文件、导出登录态、调用内部端点或迁移浏览器登录。

## 已安装20项

均以前缀 `xyq.web.` 调用：

| 类别 | 后缀 |
|---|---|
| 首页只读 | `account`, `surface`, `form_inspect`, `form_options` |
| 首页状态和参数 | `form_state`, `form_choices`, `form_prepare`, `mode_choices`, `mode_prepare` |
| 音频读取 | `audio_form_state`, `audio_form_state_bound` |
| 音频素材与设置 | `audio_reference_upload`, `audio_prompt_prepare`, `audio_choices`, `audio_prepare`, `audio_quote` |
| 报价/历史 | `home_quote`, `project_history_state` |
| 单次提交/原回执 | `generate`, `generation_status` |

网页动态选项决定可用参数，不将工具数量等同完整功能覆盖。音频参考上传/引用不等于
预设音色选择或生成声音效果。每秒音频单价不等于单次总价；总价合同仍待取得。
复杂白板、故事板、3D导演台和时间线维持暂缓。

## 修复与部署证据

1. 原生成回执更新在单链接校验前使用 O_TRUNC；新增红/绿测试证明硬链接文件
   会先被截断。现改为先打开、不截断，验证普通单链接文件后才 ftruncate。
   输入后的回执留存失败报告 `submission_unknown/receipt_retention`，保留原字节和锁，
   返回有界 `retention_failure_code`，没有自动重试。
2. 首次实机 LOCAL 状态查询暴露 SDK 调度签名差异：browser=false 调用
   `func(args, debug)`，而网页命令调用 `func(page, args, debug)`。适配器现区分两种签名。
   新注册函数红/绿测试、已安装 SDK 1.8.6 分派和实际 App 链路均验证此修复。
   原失败 job `feaa78ca-dee1-4b4b-a0ca-ea092d371539` 保留，没有改写为成功。
3. 修复前本轮新增的33份加载文件完整移到
   `~/.opencli/adapter-backups/xyq-media-runtime-20261008-r1`；20份旧定义完整备份。
   使用官方 maker 接口显式更新这20项，保留此前200定义、98源码文件和8保护回执。
   vault、App二进制、ATM入口及CLI绑定保持。
4. 最终相关 Node **538 passed / 0 failed / 0 skipped**；相关 Python **63 passed /
   0 failed / 0 skipped**，包含真子进程与全网络拦截的原生 Chrome 夹具。
   一轮沙箱 Chrome 启动失败保留为环境错误，不计为通过；相同断言在获准隔离启动后通过。
5. 原生注册的既有1339项逐字段保持，新增20项。SDK序列化 strategy 为小写 `local`；
   首轮验证辅助器误期待大写的诊断保留，产品代码未因这个大小写检查而调整。
6. 生成CLI → 常用已安装ATM → 实际App → LOCAL查询，读取字节一致复制的原生合成
   夹具原回执，job `c9c1db2e-021c-412d-852b-ddccb156ade2` completed；
   同键同job复用通过，原账本文件不变。结果为 submitted、provider_checked=false、
   task_completed=false、submission_repeated=false、lock_changed=false。
   **这个 completed 是查询完成，原夹具没有调用供应商。**
7. 新安装音频只读入口按此前获批的精确测试项目/画布/节点执行；job
   `0a817499-7bc6-4810-a111-3885172f05ce` 返回未知，原生只读诊断为 `origin_mismatch`。
   未自动导航、重新绑定或选择其它页面；本轮真实网页音频读取验收未通过。

部署收据：`/private/tmp/atm-xyq-media-runtime-install-20261008-r2/`；
相关测试：`/private/tmp/atm-xyq-media-runtime-node-all-20261008-r2.txt`、
`/private/tmp/atm-xyq-media-runtime-native-20261008-r4.xml`。
仓库内的审阅收据见 `.atm/xyq-media-runtime-validation-20261008/verification.json`。

## 保留的待验收项

- 独立音频项目当前绑定与原生读/写复验；模式及非默认模型的动态参数全量覆盖。
- 原未知 MP3 上传、原未知图片下载仍保持；代码升级不批准重传或再次点击。
- 真实图像/视频/音频付费生成、预设/上传音色效果、音频总价。
- 视频/音频的真实结果样例、供应商任务关联、下载源及完成文件完整解码。
  用户再次指定“我的世界光影风格图”；此前当前渲染仅见图片，不推断完整历史没有其它媒体。
- 旧全仓回归的三处 Tripo 快照/pin 差异单列保留；本次相关测试通过不代表全仓 CI 全绿。

参见[生成](XYQ_GENERATION_CONTRACT.md)、[图片结果](XYQ_RESULT_CONTRACT.md)、
[图片下载](XYQ_DOWNLOAD_CONTRACT.md)、[覆盖表](XYQ_WEB_COVERAGE.md)。

## 后续首页只读复验（2026-10-08）

用户明确允许仅本轮恢复 `site:xyq-home` 绑定后，生产 `form_state`、新增两项素材发现
与获准会话 `results` 均经生成CLI→常用ATM→实际App读取通过。首页完整草稿前后及
返回后相同，菜单关闭、同键同job复用。当前会话可见图片1，视频/音频0；不推断完整历史。
结束官方 unbind 返回 unbound=true，登录与原稿保留。没有自动处理 `site:xyq-web` 的旧
origin_mismatch，没有上传、生成、下载或新消费。两项独立素材工具不改变原20项闭包；
详细收据、549 Node/14新Python及菜单契约见[首页素材合同](XYQ_HOME_MATERIAL_CONTRACT.md)。

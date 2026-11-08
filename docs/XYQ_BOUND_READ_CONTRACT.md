# 小云雀显式已绑定页面读取

## Strategy note

- Strategy: UI_SELECTOR; Contract: visible-ui.
- Evidence: OpenCLIApp 0.1.38 / CLI 1.8.6 的普通 adapter 使用 surface=adapter，
  browser bind 使用 surface=browser。实际 bind 已核对测试项目，但原读取入口仍 origin_mismatch。
  已安装公开 Page API 在同名 browser 会话仅读同一表单成功，完整 form SHA 与源码读取相同。
- Auth source: Chrome-owned login; no Cookie/token/profile files or authentication export.
- Replay: exact project/canvas/audio-node DOM reader, ready, no input/navigation/upload/generation.

## 新入口

audio_form_state_bound 是显式入口，不替换 audio_form_state，不在失败后自动切换后端。
它使用公开 Page 构造 API 的 browser surface 和固定 site:xyq-web 会话，沿用调用者的
公开 profile 路由字段；实际 DOM 仍绑定精确 project_id / canvas_id / node_id。
先校验源码 pin 和输入，仅读原音频 DOM 合同。返回非秘密摘要，不读取存储/认证或整个账户。

由 Agent 将已核对测试页置前，再执行一次 OpenCLI browser site:xyq-web bind；
确认返回 URL 精确匹配项目/画布（完整 URL 不输出）。绑定不是登录态迁移，也不会绑定另一设备。
读取器自身从不 bind/unbind、导航、开关窗口、发送 UI 输入或自动重试另一个会话。
未绑定、错误页面或登录丢失时明确失败，交还明确的页面就绪步骤。

这是同系统用户可信项目模式，不是敌对代码隔离。只加载读取注册入口；没有上传/付费入口。
原普通 adapter 的独立 owned 会话及已安装旧 read loader 保留，未取消安全检查。
源码、假 Page 工厂、隔离原生页面、已安装 CLI 与 ATM bundle 路径分别验收。
绑定会话在用户切换目标/daemon重启后应重新核对；历史读取结果不证明当前页面。

## 当时的表单读取验收

此阶段已安装 OpenCLI 只有旧音频读取和新增 audio-form-state-bound 两个读取注册入口；
新入口位于 ~/.opencli/clis/xyq-web-bound/read.js，辅助源码独立保存在 reviewed/。
原 ~/.opencli/clis/xyq-web/read.js 和其旧 pin 保持原样，没有加载上传/付费注册入口。
当前 source pin b1a9df91e506bfb6b2c8a715752b00365730f2e3729efb033228abbc9918288f；
manifest SHA dd1f09a7db3afd0e2ca5da4d74cedccd47624daa9fd4c0a11ebdb1eda178b3ec。

实际 OpenCLIApp __opencli_shim 调用 exit0 / ready；生成 tool.py 调用已安装 ATM，
只在 /private/tmp/atm-xyq-bound-e2e-20261007/state 安装该 manifest 并绑定已核对 App。
生成 CLI → 隔离 ATM → App → 当前测试表单完成，同一 request-key 返回同一已完成 job。
没有初始化/读取现有生产 vault、导出认证、上传或生成。ATM job的 completed 这里只证明只读链路，
不是生成媒体。安装元数据的 authentication:not_verified 是绑定时静态标志，不替代实际表单读取。

完整 form SHA 64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97，
Seed Audio 1.0 /44.1kHz、一个 WAV卡片与一个结构化引用保持；独立 CUA 源码读回相同，截图6396积分。
最终0600回执 /private/tmp/atm-xyq-bound-generated-e2e-receipt-20261007.json；
截图 /private/tmp/atm-xyq-bound-read-final-20261007-r2.jpg。
普通 adapter 仍有独立页面；没有通过改第三方代码、强制改 Page 私有字段或转移浏览器状态让它伪成功。
因此之前 App内页面人工 handoff 不再是新显式只读路由的门槛，其余写入/生成/任务/下载仍待验收。

最终收尾核对通过：16包锁与当前源码 pin一致，已安装6份辅助源码逐字节相同，
新入口只有一个只读注册，原 loader摘要保持；根/包内 Skill一致。
Node149、Python156、零失败/跳过的回执已核对，生成 CLI结果 JSON的926字节及
SHA256与已完成 job产物一致，同键复用同job；最终截图确为JPEG。
独立核对回执：`/private/tmp/atm-xyq-bound-final-verification-20261007.json`（0600），
核对脚本：`/private/tmp/verify-xyq-bound-read-20261007.py`。此核对不新增实机输入。

后续已加载五个首页显式入口和第三个音频只读入口 audio-quote-bound；
原两个音频读取保留，参见 XYQ_HOME_PREPARE_CONTRACT.md 与 XYQ_AUDIO_QUOTE_CONTRACT.md。
后者完成同一精确测试表单的生成CLI只读费率验收，仍不含上传、生成或总价承诺。

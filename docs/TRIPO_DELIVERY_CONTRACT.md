# Tripo 后处理与交付验收

## 当前安装

2026-10-07，分支 `feat/media-cli-delivery-20261007`。
最新34个生成包在 `generated/tripo-studio-delivery-stage-r4/`，34项 ATM 定义和
OpenCLI 注册已回读一致。新增 texture_quote、texture、operation_status：前两项
复用已审阅 workspace Texture 合同，不另建 API 后端；状态查询仅绑定原项目回执。

首次安装先备份18份原适配源，增加2份 delivery 源、修改1份 extended 源。
实机文案修复另备份20份源，修改2份源、CAS更新28项传递摘要，另6项保持。
OpenCLIApp 二进制、旧未知上传请求及 vault 保持；没有升级全局包或用户级 Skill。
原文件备份及 CAS 定义历史都留存。安装不代表全部34项实机验收。

## 用户批准的70积分测试

仅源模型 `6e6198e0-0d74-4522-832f-46a5d49e1d3d` 蓝色测试立方体或其测试结果：
Retopo Quad/10000，40积分；Texture 8K，`solid blue matte surface`，30积分；各一次。
真实 quote 和 paid 输入共享精确报价摘要、模型、预算与稳定请求键，漂移就停止。
独立测试目录 `.atm/tripo-delivery-validation-20261007/` 仅用于这两项新获批操作；
主项目原图片上传未知请求与锁按原哈希保持，不以新目录重试旧上传。

生成CLI → 已安装ATM → OpenCLIApp → 真实网站的观察：
- Retopo提交一次，40积分；先看到processing，随后模型ready且Export可用，
  当前8468面/8399顶点。10000是请求值，不伪造为最终精确面数。
- Texture报价仍30、8K和固定测试提示词回读一致；仅点一次。
- 初版观察器漏掉真实HUD `Generating Texture...`，15秒等待后保留
  submission_unknown / paid_click / page_not_ready 及 active.lock，没有重提。
- 随后只读页面确实显示同一UUID的Generating Texture；余额20115→20075→20045，
  两次余额变化合计70。余额差是扣分观察，不是美元成本或完成纹理的证明。
- 根因修复为精确加入已观察文案，并排除 Assets tabpanel 内其它模型的processing。
  旧网格和Export可用不再覆盖正在生成纹理的状态；没有删断言或扩展成宽泛词匹配。
- 修复源对真实Texture页面回读 status=generating、processing=true；最新已安装
  生成CLI只读等待随后返回ready、8468面/8399顶点、Export可用。独立页面回读
  processing=false、8K、测试提示词一致、Generate Texture重新启用；截图为蓝色表面。
- 原Texture未知回执仍原样留存，不覆盖为成功。网页完成观察与原操作自动对账分列；
  保留锁期间不绕过导出守卫，最终GLB文件及质量/导入验收仍待。

同一UUID会被后处理原位更新，source_asset_id==asset_id不是新的结果UUID。
operation_status 保守返回 needs_output_reference；未知回执保留 submission_unknown，
都不释放锁或推定已完成。后续需要明确的版本/完成证据合同来做自动对账。
模型只读状态、单次提交、操作关联、最终文件与视觉质量是不同验收门槛。
Auto-rig没有执行：还需适合的人形测试模型、前置条件和单独报价确认。

## 回归与回执

506项 Tripo/XYQ Node、86项相关 Python 通过，零失败/跳过，包含两个真实文案回归。
这是限定范围，不是全仓库CI或全部供应商功能覆盖。
历史483项回执及首次错误保留；最新：
- `/private/tmp/atm-media-delivery-node-full-20261007-r3.txt`
- `/private/tmp/atm-media-delivery-python-full-20261007-r2.xml`
- `/private/tmp/atm-tripo-delivery-upgrade-20261007/receipt.json`
- `/private/tmp/atm-tripo-progress-parser-upgrade-20261007/receipt.json`
- `.atm/tripo-delivery-validation-20261007/verification.json`
- `/private/tmp/atm-tripo-texture-completion-ui-20261007.json`
- `/private/tmp/atm-tripo-texture-result-20261007.png`

原Texture未知回执在最终修复部署前后哈希一致。任何后续对账都应追加证据，
不覆盖原失败、不更换付费键、不重提测试；本次70额度已用完。

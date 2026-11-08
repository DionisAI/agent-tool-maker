# 小云雀音频上传的显式绑定

## Strategy note

- Strategy: UI_SELECTOR; Contract: visible-ui.
- Evidence: 已观察的唯一音频node/footer与专用音频file input、合成WAV素材卡片；
  复用 XYQ_AUDIO_CONTRACT.md 的本地PCM校验、empty/append、durable intent/lock及回读合同。
- Auth source: Chrome-owned login；公开 Page 固定 site:xyq-web/browser/persistent，
  严格/首选profile路由保持，无 Cookie/token/profile/认证存储导出。
- Replay: 新执行桥只开放 depth0 DOM根、确切音频input查询与一个已核对文件的原生file input；
  源码/隔离原生上传/真实拒绝路径/真实新上传分别验收，不重用已消耗的上传批准。

## 业务合同

显式 `--bound-audio-upload` 仅调整既有 audio_reference_upload 的路由、pin及说明；
缺省路由、工具ID、schema、execute_code+external_write权限与稳定请求键保持，仍16包。
可与首页/音频费率/参数的显式选项组合，无失败后换后端或重绑定。

原本地文件校验、完整form摘要、空稿/追加保护、命名冲突、3音频/1图像限制、
intent先于一次输入、未知结果保留lock与历史receipt复用均保持。
执行桥再次核对唯一节点/footer、专用input数量/类型/启用、FileList与文件SHA；
file input的DOM nodeId在原生提交前重新查询对应关系，错误/变化停止，不更改DOM。
仅允许一个项目内PCM WAV；未知文件格式、任意DOM/CDP命令、选择器、节点ID或文件列表
不进入CLI schema。无菜单点击、提示词/参数改变、生成、付费或导航。

## 输出状态与失败

- `attached`：新增卡片及原内容回读通过，不代表音色效果、持久化或生成。
- `reused=true/current_form_verified=false`：复用历史已完成上传receipt，不重新输入或声称当前草稿已核对。
- `upload_rejected`：仅已知预检冲突，原typed error必须明确处于preflight、零steps、
  outcome_uncertain=false。返回reason、phase、零输入/上传标记与upload_accepted=false。
  这是明确预检停止的条件结果，不是成功上传；ATM job completed仅表示该检查已完成。
- origin/node/桥/文件错误、协议异常和任何intent后的错误继续抛出；未知提交不转成正常预检停止。
  原普通入口错误合同保持。一般非零外部CLI退出在ATM仍可能报告submission_unknown并隐去stderr；
  保留这一保守合同，不全局改变其它CLI的错误处理或宣称供应商未执行。

## 根因修复与隔离回归

原生隔离首轮出现8项失败：桥重复调用DOM.getDocument，再比较两轮frontend nodeId，
同一个backend节点因此被误判为替换。实际CDP诊断为旧根1/input13，同根重查仍13，
新根22/input34，backendNodeId两轮均14。修复只在原捕获根上重查；真实clone替换输入框
仍明确停止，未知intent/lock保持，未放宽断言或更改浏览器策略。
诊断回执：
`/private/var/folders/h4/ky5k4mdj5gq2dxzb4jhvw_fr0000gn/T/pytest-of-xinhuang/pytest-297/test_native_document_root_ids_0/cdp-node-identity.json`。

最终196 Node / 256 Python（74非浏览器、182原生隔离），全部通过、零跳过。
新增10 Node / 25 Python，覆盖原生输入一次、append 1→2/2→3、图像/token保留、
历史receipt零输入、已知预检停止、真正替换节点、intent后变化和原生异常的未知结果/零重试。
供应商请求在隔离浏览器中由夹具响应或终止；假子进程同键只执行一次。
最终回归：`/private/tmp/atm-xyq-upload-bound-all-node-20261007-r2.txt`、
`/private/tmp/atm-xyq-upload-bound-all-20261007-r2.xml`；
初轮8失败及focused第二轮测试函数位置错误均保留，断言移回原测试后focused第三轮25通过。

## 实机验收范围与回执

2026-10-07：新闭包8文件pin
`5b84f42acb11b641bd025875399c79e743570cc1b820d2229f3da0dcda1bd4d5`；
16包位于 `generated/xyq-web-audio-upload-bound-stage-r2/`，相对音频准备阶段仅上传定义变化。
该目录是本机构建输出，未提交到仓库；当前27项按[重建步骤](XYQ_MEDIA_RUNTIME_CONTRACT.md#从源码重建并安装27项)重建。
`~/.opencli/clis/xyq-audio-upload-bound/upload.js`单独加载一条注册，loader SHA
`c442572df8782caafceeca331b286f02fbb0d1c8989a6ab87dcb2b2ec1a62ff3`；
原11条注册/所有已安装闭包、第三方App、生产ATM/vault和用户级Skill保持。
安装计划/回执为 `/private/tmp/atm-xyq-upload-bound-install-plan-20261007.json`、
`/private/tmp/atm-xyq-upload-bound-install-20261007.json`（0600）。

生成tool.py→新隔离ATM（2定义）→已安装App→原绑定ATM-XYQ-CLI-test：
before、旧摘要上传预检、after三个job completed；预检job
`7b80d7d4-6f86-4b3b-ae37-7576acac524c`返回upload_rejected/draft_changed/preflight，
steps=[]、outcome_uncertain=false、upload_accepted=false、native_file_input_sent=false；
没有active.lock/intent，同键复用同job。新1秒纯合成WAV只在临时目录校验，未传到网页，
全零expected_form_sha256故意与原稿不同；confirm=true仅此负例schema，不是新上传批准。
before/after及独立CUA的完整form SHA均
`64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97`，
prompt文档一致、原音频卡片/token保留、积分6396；零输入、上传、生成和消费。

真实回执/产物目录 `/private/tmp/atm-xyq-upload-bound-preflight-e2e-20261007/`；
独立前后为 `/private/tmp/atm-xyq-upload-bound-cua-before-20261007.json`、
`/private/tmp/atm-xyq-upload-bound-cua-after-20261007.json`；最终核对
`/private/tmp/atm-xyq-upload-bound-final-verification-20261007.json`（0600）。
这只验收真实零输入预检停止路径；实机原生附件、追加、持久化、音色效果仍待新文件许可及独立验收。
原已消耗的一份WAV上传批准不重复使用；未加载生成入口、未消费积分，完整媒体目标仍进行中。

随后 MP3 源码扩展复用此显式绑定与一次输入合同，见 [MP3 参考上传合同](XYQ_MP3_REFERENCE_CONTRACT.md)。
本页5b84 pin及已加载WAV源码保留；新源码2821 pin在独立18包暂存阶段，未替换已安装入口。
节点 audio input 的 accept=null不证明 MP3 接收；新文件许可与实机附件验收仍待。

最新显式注册已升级MP3，旧版9源码文件完整备份，最终pin为c70aa32，详见MP3合同末节。
生成CLI的真实MP3旧摘要预检通过，仍是upload_rejected/draft_changed而非成功上传；
其它13注册/生产ATM保持，真实文件输入与音色效果另行验收。

后续用户确认的一次 MP3 追加在 c70aa32 返回 submission_unknown，原锁和 intent 保留，
原音频稿未出现新卡片。现单入口为 f33eecb：原 depth0 根/精确节点/同根重查保护保持，
最后一步调用公开 Page.setFileInput([approved_file], fixed_selector)，由现有扩展管理
文件选择器拦截，而非裸 CDP 文件输入。无 DOM 字节注入或失败后换路由。
未知错误新增私有、有界的 request-key.failure.json，保留 code/phase/steps/输入尝试标记，
诊断写入失败也显式记录在错误元数据中；原 lock/intent 和成功回执语义保持。
254 Node/97受影响Python通过；已安装单入口、完整旧9源码备份，未重试未知真实操作。
完整证据和后续协调门槛见 MP3 合同最新末节。

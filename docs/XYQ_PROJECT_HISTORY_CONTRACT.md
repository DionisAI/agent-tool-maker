# 小云雀项目生成历史视图

## Strategy note

- Strategy: UI_SELECTOR; Contract: visible-ui.
- Evidence: 测试项目`/project`的唯一“生成历史”popover-trigger与受控dialog，
  “筛选生成历史”四个media tab及互相关联tabpanel，生成状态dropdown和明确empty状态。
- Auth source: 公开Page固定site:xyq-web/browser/persistent、Chrome-owned login，
  保持严格/首选profile路由；无认证文件、Cookie/storage读取或私有接口重放。
- Replay: 仅读当前精确项目/canvas的可见视图。查询不打开/关闭菜单、不切换筛选、
  不生成、付费、导航、上传或下载。行格式/行所属项目仍须真实记录验证，暂不推测解析。

## 事实与边界

2026-10-07，ATM-XYQ-CLI-test项目10500937705228、canvas10520952130316：
生成历史media tabs为全部/图片/视频/音频，当前全部；生成状态菜单为
成功/全部状态/生成中/失败，当前成功。当前active tabpanel唯一空态为
“暂无符合筛选条件的生成记录”。只证明当前筛选的可见记录为空，
不是全账户/全项目任务为空，不把成功通知或历史空态当作媒体任务完成证明。

URL和popover控件只证明当前项目UI上下文；尚无已核对的任务行project/task标记，
row_scope_verified=false。有真实行时应明确报unsupported_history_records而不是猜task ID或返回空列表。
全账户TaskCenter读取范围仍待回复，本入口不读取其它项目的任务或调用内部接口。
为继续真实任务ID/状态/下载核对，已单独询问新图片测试节点准备、由用户最终生成一次的范围。
网页显示预估与已验证扣费硬上限分列；本轮不提交生成。

## 查询合同

新增xyq.web.project_history_state，schema只有确切project_id/canvas_id，read-only/execute_code。
既有工具定义保持；返回当前媒体/状态筛选、互相验证的控件关系、closed/loading/empty视图状态。
闭合视图的记录数量是null，不是0；明确empty只给visible_record_count=0，
all_records=false、task_count=null。其它菜单、重复关联、错页/错项目/错canvas明确失败。
空态消息、scope及筛选在两次快照之间变化报history_changed；不会自动关闭别人的层或换绑定。
未知文件/生成产物行不读取名称、提示词、链接、状态/ID，不伪造任务完成或媒体交付。

## 实现与隔离验收

编译默认18个媒体包，目录generated/xyq-web-history-stage/；新增1个定义，
原17个定义的完整摘要/路由与各源码闭包保持。
history闭包8文件，pin为ef9de8acd17f8c999d5367440cadbfeb6e9f0f87be39863b0597bbd087d23ac5。
新增reviewed project-history-state-bound注册，loader SHA为
92a4fe29dc739efc7d64e16caa8fdf63395a00048f1ad44cd20efadcd92a4b0e。
原13条注册、已安装App及各原闭包保持；生产ATM/vault与用户级Skill保持原状。

最终Node218/Python316（84非浏览器、232原生隔离），零失败/跳过；
新增10Node/31Python，覆盖closed/loading/明确empty、动态筛选标签、精确页面/项目/canvas、
重复关联、其它层、未知真实行停止、竞态和回执复用。供应商请求仅隔离夹具响应或终止。
原生测试不等于真实媒体任务交付，也不修改浏览器策略。
回归：/private/tmp/atm-xyq-history-all-node-20261007.txt、
/private/tmp/atm-xyq-history-all-20261007.xml。

## 真实生成 CLI 只读链路

生成tool.py→新隔离ATM（仅1条history定义）→已安装App→精确测试项目，两阶段通过：

| 阶段 | job | 结果 |
|---|---|---|
| open | 0cd4b5be-e924-4e98-ac04-99f2944fc5ec | history_empty；全部媒体/成功；visible_record_count=0、task_count=null |
| closed | c952c05b-986f-4f0a-8be0-19f011a429d1 | history_closed；筛选与数量均null |

open同request-key复用同job/result，不重新查询。两阶段只授execute_code，paid_granted=false；
artifact逐一核对限定路径/字节数/SHA/JSON与job一致。CLI零输入，未开关面板/切筛选。
阶段之间由CUA仅关闭本次自有“关闭生成历史”按钮，随后独立源码读取与CLI closed结果一致。
open历史SHA为5ca0b2ca1e4b77fa06921b545af748403b8faa10d46ae869a011d0829b882ac1，
closed历史SHA为052bf48739b1985b7481b381edc79e92b697982621141b4cab929e14af3bc03e。

独立CUA终态与原音频表单完整一致，form SHA
64b537cf8c6252ef53b2aedd0c5783c5e1548a43530c427ffe63f354bf629f97；
原SeedAudio1.0/44.1kHz、1张合成音频卡、1个结构化引用及原稿保持。
空首页完整原稿亦保持，draft SHA
cabd0fa41945ddc23527d0aaa8fd0a85078c75678b8d43278bc99fc0cbd47ccf。
当前首页与项目均显示6430积分；上一阶段6396是历史读数，原因未查，不称本轮余额未变。
首次独立余额读取使用项目页“积分余额”标签查首页而超时；首页实际banner按钮是数字6430，
按观察到的控件读取后两页一致。此为验收观察器定位问题，没有改适配器或重复提交。
零上传/生成/下载/付费提交，有效任务行仍未解析，余额读数也不是账单证明。

真实产物：/private/tmp/atm-xyq-history-e2e-20261007/；
独立终态：/private/tmp/atm-xyq-history-cli-cua-after-20261007.json；
恢复截图：/private/tmp/atm-xyq-history-cli-restored-20261007.jpg；
最终核对：/private/tmp/atm-xyq-history-final-verification-20261007.json（0600）。

待验收：真实任务行所属项目、task ID/状态/产物、有效文件下载和媒体校验。
新图片测试节点准备/用户最终生成范围待回复；本轮未新建节点、写入新提示词或提交生成。
完整媒体目标保持进行中；历史视图只读验收不代表任务/下载已完成。

# ATM v0.7.0 测试报告

本轮以交付v0.6源码树为基线；当前版本聚焦凭证入口，而不是新增供应商目录。

最终测试数字由本轮final-all.xml生成，汇总见reports/v07/summary.json；没有把之前v0.6的588或早期开发结果当成本轮全通过。

## 最终结果（本轮实际运行）

- 完整源码回归：**673 passed，0 failed / error / skipped / xfail / deselected**。其中原有588项，新增85项。
- 该次JUnit记录时长 563.92 秒（仅历史回执，不是运行耗时承诺）。最终gate未启用覆盖率采样，不引用早期开发覆盖率。
- 独立Linux跨UID：**1 passed**；仍是旧registered-tool路径，新generic exec跨UID拒绝另有回归。
- 新入口源码与源码外wheel各完成同一验收脚本：一次PTY密码、两个独立客户端、无manifest的app.py、本地HTTP鉴权、单机双库加密同步、提前锁定、2秒加速自然过期。
- 源码外wheel **13项CLI检查**；**46个运行文件/资源**逐字节一致；最终gate前后 **88个运行时/测试/脚本文件**哈希不变。
- 假凭证、本地供应商替身；真实供应商及真实模型调用均0。源码外安装复用宿主依赖，原生keyring缺失。
- v0.7没有GitHub上传/PR/远端CI。原生浏览器导航、真实Claude/Codex宿主、两台机器、Windows及独立安全审计没有声明完成。

原始回执位于下载包 `reports/v07/`；历史失败及中断记录在 `reports/v07/development/`，不计为通过。

## 核心验收

`scripts/demo_secrets_first.py`实际使用PTY输入一次假口令，启动固定30分钟session。两个独立headless CLI进程（配置标签Claude/Codex，不是真实模型）调用没有ATM manifest的app.py，app从os.environ['FAL_KEY']取Key并访问实际本地HTTP fixture。

检测没有新建.env、无Key明文落入状态库、重复unlock不延长、lock后拒绝。向另一独立主密钥的本地库做加密同步后，第三个独立客户端进程也成功。过期使用2秒加速租期，不能称为30分钟soak；两个库在同一机器，不能称为两台真机。

## 安全测试

新套件覆盖 scoped discovery、开发/生产歧义、不按别名动态换Key、命令/项目/映射限制、文件SHA改变、symlink/..、执行控制环境变量、输出分块回显与常见编码遮蔽、内存输出上限、进程超时、幂等、撤销、期限、冲突、解密中权限或凭证变化、Owner与客户端角色分离、锁定竞态不得重新验证、session profile删除无降级、Web/CLI共用会话。

旧供应商、Maker、sync、Broker等回归保留。独立Linux跨UID验收仍测试旧registered-tool路径；genericexec跨UID另外被明确拒绝，不混淆两种能力。

## 浏览器与安装

实际Chromium运行DOM与HTTP测试桥，包括新的Web解锁和保存连接，再由受限程序使用。没有修改管理策略；原生URL导航是独立CI/允许环境验收，未在本轮容器执行。

Wheel在源码目录外target安装，并验证导入来源、CLI入口和运行资源逐字节一致；复用本机已装依赖，不声称干净网络环境安装。最终接受脚本也对安装后的wheel运行。

## 失败与修复记录

早期开发全量650通过后又加了检查，故不是最终gate。带coverage的后续全量在旧UI和旧factory用例失败，已停止，保留不完整日志。UI原测试单独通过，不能武断归因。factory隔离复测确认1秒语义测试预算误触发draft_timeout；只给非超时语义场景10秒，专用超时场景仍1秒对10秒sleep，并保留所有原有错误断言。

随后复查发现“认证通过后同时锁定”可能重新调用Vault.unlock，修正请求vault为无fallback快照，增加两个回归并重新开始完整gate。所有中间不完整运行均不计入最终通过数。

## 外部边界

真实供应商请求/消费0，真实Claude/Codex模型调用0。没有OS keyring锁屏/重启、实际Agent Skill加载、Passkey、Windows、两台公网机器或独立密码学/依赖审计。
本輪没有GitHub写入、PR或远端CI；不能沿用v0.4远端绿灯。交付补丁只是可验证的源文件变更。

补充检查复现：旧通用执行器把venv解释器符号链接解析成基础Python后，`sys.prefix`从临时venv变成`/usr`。现已保留调用路径并固定真实目标与pyvenv.cfg，加入真实venv专有依赖加载及链接目标变化回归。测试代码曾出现一个收集期字符串转义错误，已修正并compileall；收集失败记录不计入通过数。修复后重新冻结运行时和测试源文件。

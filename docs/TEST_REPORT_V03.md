# ATM v0.3.0 — 本轮测试报告

核查与运行日期：2026-09-30。基于远端main提交c535e57f；工作目录的初始Git tree与
c17e66a8c816ed7b4cacec9f2f2279e24de2ccfc一致，然后实施本轮修改。

## 本地结果

351 passed；0 failed；0 skipped；0 xfail；0 deselected。
完整运行156.80秒；行覆盖率88.08%（1825/2072）。Linux，Python3.13.5。
原有303项 + 本轮37项onboarding测试 + 11项跨进程回归。
上轮三个严格XFAIL已落实为必须通过的回归，不再以预期失败收尾。

覆盖：setup预览/应用/重复应用、已存密文保护、Skill冲突与备份、符号链接拒绝、
CLI改变/缺失/执行权限、CLI自有登录与可选Key覆盖、headless库解锁状态、
显式有效期、连接重复保存保护、四个独立协议账户探针、401/403/429/5xx/跳转、
不重试/不保存上游敏感资料、轮换后的历史结果失效、跨项目与跨进程复用。

真实运行FFmpeg/FFprobe、ImageMagick、Pandoc、Chromium。浏览器是合成页面；
多数云端协议使用MockTransport，CLI协议使用本地替身，不代表生产平台验收。
原生keyring只用了受控测试后端，不代表用户系统Keychain/Windows/Linux真实授权测试。

## wheel验收

构建agent_tool_maker_local-0.3.0-py3-none-any.whl，在另一环境安装，在源码外项目运行。
6个独立进程：init、setup预览、setup apply、重复apply、严格doctor、verify预览。
两个用户级Skill都包含绝对ATM入口和同一状态目录；重复apply为unchanged。
该环境复用宿主Python依赖；本次运行环境无法联网解析PyPI，并非空白机器依赖安装验证。
测试原始记录在下载源码包的reports/v03目录；仓库保留summary.json，CI另生成报告。

## 未声明完成

实际供应商调用0，消费0；没有实际发帖/部署/雇人。没有启动用户的Claude Code/Codex
客户端读取Skill，没有验证原生keyring在锁屏/重启后的行为，没有验证Windows。
OAuth自动刷新、后台解锁服务、远程桥接与可信人类批准侧车仍未实现。
4个账户GET探针只证明指定端点当时通过，不证明全部权限/生成成功/余额充足。

v0.3 CI配置拆分Linux契约矩阵、macOS真实本地工具、Linux浏览器和wheel冒烟。
CI的实际结果必须查PR对应提交，不把本地通过写成远端通过。

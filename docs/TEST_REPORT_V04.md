# ATM v0.4.0 — 默认客户端与本地网页管理测试报告

日期：2026-09-30。基于 PR #1 的 `a5346ed458ccb416b22e9b0e0b5c3bfdf6d119d3`，
初始 Git tree 已与 `73f4712c6f257ed445bfdb1d6813bc214bdb5965` 核对一致。

## 最终本地回归

**407 passed，0 failed，0 skipped，0 xfail，0 deselected。**
行覆盖率 **89.42%（2206 / 2467）**；运行 203.39 秒，Linux / Python 3.13.5。
在原有 351 项基础上新增 56 项。原有断言未被修改以隐藏失败。

新增覆盖默认 Claude/Codex 注册、只选一个或不注册 Agent、注册摘要批准与冲突、
解除注册时备份、工具停用的路由和执行阻断、工作流恢复、跨进程共享状态、
并发 compare-and-set、连接更新只影响选定凭证、真实 HTTP 认证与 Origin/Host 检查、
请求大小及重复头限制、无任意执行接口、令牌过期与日志不回显、凭证请求级解锁。

开发中修复了前端刷新后筛选条件丢失、凭证库初始化后旧状态竞态两个问题。
一次开发期全套运行遇到 Skill 幂等断言失败，当时 Skill 源文件仍在编辑；
该测试独立重跑及冻结源码后的完整回归均通过。原失败日志保留为开发记录，
不计入最终通过数，也未把断言改成 skip/xfail。

## 浏览器证据分层

1. **真实本地 HTTP**：启动实际管理服务器，使用 httpx 请求，覆盖读取、写入、
   注册、工具开关、凭证保存，以及认证、CSRF/Host 防护；并非模拟 Handler。
2. **真实 Chromium 组件交互**：使用实际 HTML/CSS/JS，真实 DOM 操作，
   默认注册、筛选停用、schema 弹窗、初始化库、加密保存和锁定均执行。
   浏览器 fetch 通过测试专用 Python HTTP 桥连接真实服务器。
   该层不声称原生同源请求、CSP 或 localhost 页面导航已验收。
3. **原生 localhost 导航**：本地受管 Chromium 返回 `ERR_BLOCKED_BY_ADMINISTRATOR`。
   没有修改或绕过浏览器访问策略。独立的
   `acceptance/test_console_navigation.py` 已加入 GitHub 浏览器 CI，
   必须读取该提交的实际结果，不能由上两层推导通过。

管理台截图来自第 2 层，使用临时测试状态与假凭证，不是你的真实账户。

## 首轮远端 CI 发现与修复

首次提交 e2dd9a1 的 CI 暴露两处问题，均保留原验收目标后修复：
- Python 3.11 的 namespace Traversable 不支持多参数 joinpath，导致静态页面返回400。
  改成逐层单参数读取，并补了首页/JS/CSS 三个兼容性回归测试。
- 原生浏览器测试的字符串 wait_for_function 与严格 CSP 冲突。改成等价的 locator
  状态断言，不启用 unsafe-eval、不放宽 CSP、不跳过原生导航。
- 同时修复浏览器提前关闭时重复发送响应的异常，新增四个断开连接回归。

最终远端结果见 PR #2 对应提交和下载包 reports/v04/ci-status.json，不将初次失败
隐藏为通过，也不把本地组件测试称为原生浏览器验收。

## 安装包

构建 `agent_tool_maker_local-0.4.0-py3-none-any.whl`，在源码外的独立 venv 安装。
通过默认 setup 预览、双客户端应用、重复应用、agents/connections 查询，
以及真实 `atm ui --no-browser` 子进程、静态资源、认证、网页修改后新 CLI 读取、
加密凭证保存、无交互重复 connect、退出令牌清理等验收，共 9 个记录步骤。
测试依赖复用已有宿主包，不冒充干净联网机器重新下载依赖成功。

## 没有宣称完成

商业供应商真实请求 **0**，实际消费 **0**；原生 keyring 使用受控测试后端，
未验证用户 Keychain、锁屏重启行为或 Windows。
没有运行真实 Claude Code/Codex 客户端加载 Skill，只验证注册与跨进程执行契约。
静态 Key 复用不代表 OAuth 自动刷新；后者仍未实现。
管理台只绑定 127.0.0.1，非云端服务、非同用户恶意进程隔离沙箱。
停用开关阻止新调用，不撤销已经提交给外部供应商的任务。

## 复现

```bash
python -m pip install -e '.[secure,test,browser-test]'
python -m playwright install chromium
# 完整套件还需 ffmpeg / ffprobe / magick / pandoc。
python -m pytest -q --cov=agent_tool_maker --junitxml=reports/full.xml
# 仅在宿主允许 localhost 导航的环境运行；禁止修改企业浏览器策略：
python -m pytest -q acceptance/test_console_navigation.py
```

下载包的 `reports/v04/` 保留原始日志、JUnit、覆盖率和安装包证据。
仓库保留 `summary.json`；CI 生成独立报告。

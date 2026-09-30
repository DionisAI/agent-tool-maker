# ATM v0.5.0 — 最终测试与交付报告

日期：2026-09-30。基于 `DionisAI/agent-tool-maker` PR #2 的 `b20775c9daf9285645d53254e4ccb27007c5076f`。
原始本地 Git tree 与远端 `047eddb287628dee045131414bf1e3c0b061b9e6` 完全一致。

## 最终结果

| 范围 | 结果 | 能证明什么 |
|---|---|---|
| 完整本地测试 | **484 passed，0 failed / error / skipped / xfail / deselected** | 全部旧版 407 项与新版 77 项通过 |
| 行覆盖 | **87.88%（3030 / 3448）** | 本次实际覆盖；不是供应商兼容率或安全保证 |
| 额外 Linux 跨系统用户验收 | **1 passed，0 skipped** | 授权 UID 能代调用真实 FFprobe，但不能读 Owner vault；另一个 UID 使用同一 bearer 被拒绝 |
| 源码外安装包 | **9 个独立 CLI 检查通过** | 安装的 wheel 可在源码外导入和运行 |
| 安装包双设备演示 | **通过** | 两个独立加密库、密文交付、冲突保留/显式解决、两个新客户端复用同一个真实 FFprobe job |
| 实际前台 Broker 进程 | **通过** | 两个新进程无需 Key/口令环境变量；租期自动结束、socket 删除、拒绝降级回直接库 |
| GitHub v0.5 CI | **未运行** | 本轮连接只有读接口，没有上传新版；不能引用 v0.4 的 CI 为新版背书 |

完整测试耗时 333.68 秒。平台 Linux/Python 3.13.5。当前 157 项供应商工具目录保持不变。
本轮生产供应商请求 **0**，消费 **0**。没有真实部署、发帖、付款或修改用户的远端凭证。

## 新增 77 项的范围

- `test_sync_v05.py`：38 项。独立本地主密钥、公钥指纹配对、按服务范围、收件方验证、签名与密文篡改、合并顺序、重复包、旧包、删除 tombstone、并发更新/删除、到期信息、冲突解决 compare-and-set、降级客户端状态漂移、文件交换和受限 watch。
- `test_broker_v05.py`：27 项。工具/目录/副作用/期限约束、token hash、授权撤销、UID、动作与执行程序配置 pin、轮换 Key 不重复授权、冲突/过期停止、任务归属与请求去重、无原始 Key 接口、无直接模式降级。
- `test_multidevice_web_v05.py`：8 项。真实 loopback HTTP、配对和密文导入导出、严格请求输入、授权预览/应用、配置变化后的旧批准拒绝。
- `test_multidevice_ui_v05.py`：1 项。实际 Chromium DOM 交互和新页面渲染，使用合成测试状态。
- `test_multidevice_cli_v05.py`：3 项。真实独立 CLI 进程、版本/注册/同步命令以及持久配置复用。

## 测试中发现并修正的事项

最初的 Web grant 预览仅包含动作 ID，没有把具体工具定义、执行程序绑定和服务 origin 一起放入批准摘要。
新增回归先证明此缺口，再将配置 pins 纳入摘要。预览之后执行程序改变，旧批准现在返回拒绝，必须重新预览。
修复前后记录保留为 `approval-pin-regression-before.log` 与 `approval-pin-regression-after.log`，最终完整测试在该修复之后重新运行。

同时补了冲突解决前的旧客户端写入漂移检查，以及前台 Broker 在没有任何请求时仍会按租期退出的真实进程检查。
早期测试 fixture 索引与 CLI 返回字段的错误分别按真实接口修正，并加强完成状态断言；没有把未通过项标为 XFAIL/skip。
早期运行被执行时限打断的日志不是完整测试证据；以 `full-test.log` 和本报告为准。

## 真实运行与模拟的分界

真实运行：FFmpeg/FFprobe、ImageMagick、Pandoc、Chromium 的合成页面交互、Unix socket、loopback HTTP、文件/SQLite 操作、独立进程；额外 Linux 测试在隔离临时目录中将子进程降为既有 UID 65534，不创建用户/组。

模拟部分：供应商 HTTP 响应和多数非本地第三方 CLI 协议。原生系统凭证库仅有受控测试后端，不能称为真实 Keychain/Secret Service 测试。
跨 UID 测试的 root 仅用于隔离测试运行器设置并降权，**不是建议生产 Broker 用 root 运行**。
批准的 CLI 代码仍以 Broker 所属用户执行，因此这个测试不证明任意恶意代码被沙箱隔离。

本地 Chromium 管理策略不允许 native localhost 导航；本次浏览器组件测试使用明确分开的测试传输，不更改策略、不宣称原生网络/CSP 验收。
上一版 GitHub 曾运行 native navigation；这一版尚未推送，不能借用旧结果。新增 CI job 已写入 YAML，但未在线执行。

安装包复用了宿主已经安装的 Python 依赖，没有在空白联网机器重新下载解析依赖。运行时模块和资源的 wheel bytes 与源码逐项匹配，见 `runtime-manifest.json`。

## 复现

```bash
python -m pip install -e '.[secure,test,browser-test]'
# 安装所需本地程序与 Chromium；不要在缺依赖的情况下把 skips 当通过。
python -m pytest -q --cov=agent_tool_maker \
  --cov-report=json:reports/v05/coverage.json \
  --junitxml=reports/v05/junit.xml
python scripts/check_test_receipt.py reports/v05/junit.xml

# 不需要任何真实供应商账号；使用假 Key，临时加密库在退出时清理。
python scripts/demo_multidevice.py --out ./multidevice-receipt.json
```

`acceptance/test_broker_uid.py` 只在明确隔离的 Linux/root 测试运行器单独执行，不在普通开发者电脑上为了通过测试授予 root：

```bash
python -m pytest -q acceptance/test_broker_uid.py
```

## 尚未验证或尚未实现

真实 Claude Code/Codex Skill 加载；真实系统 keyring、锁屏和重启；Windows Broker；真实跨云机器网络与第三方同步盘；OAuth 自动刷新；KMS/TPM、完整独立安全审计；多账号别名；按 Agent 的递归 MCP/工作流授权；硬金额预算；全局即时撤销；恶意已授权设备和本地数据库完整回滚保护。

密文同步/权限控制已实现，不等于能保证已失陷端点、root、任意项目代码或未来私钥泄露时绝不泄密。
详见 [多端使用与安全边界](MULTI_DEVICE.md) 和 [协议说明](SYNC_PROTOCOL_V1.md)。

## 交付与远端状态

本轮未推送或合并，没有新建 PR。源码补丁基于精确的 PR #2 baseline tree，交付阶段验证补丁应用后的 Git tree 与最终源码一致。
[GitHub 更新步骤](GITHUB_UPDATE_V05.md)说明如何在你已登录的机器上提交，不强制覆盖或合并旧 PR。
完整下载包包含测试回执；仓库补丁只新增摘要和运行时文件清单，不把临时凭证库、client bearer、加密包或 socket 放入 Git。

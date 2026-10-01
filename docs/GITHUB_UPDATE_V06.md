# v0.6 提交说明

本版未推送 GitHub，未创建 PR，未运行新 CI；不要沿用旧版绿灯。
最后读取的远端 PR #2 为 `b20775c9daf9285645d53254e4ccb27007c5076f`，仍开放。

## 已使用 v0.5 源码

`agent-tool-maker-v0.6.0-from-v0.5.patch` 是对 v0.5 source tree
`d38944f8d8ba71bdfae225619839f347dea1046e` 的增量补丁。
在工作目录干净、确认起点之后，新建分支并预检：

```sh
git status --short
git switch -c feat/extensible-tools-v0.6.0
git apply --check /path/to/agent-tool-maker-v0.6.0-from-v0.5.patch
git apply --index /path/to/agent-tool-maker-v0.6.0-from-v0.5.patch
```

有自己的修改时先保留并审阅冲突。不要 `reset --hard`、覆盖凭证库或 force push。

## 远端仍在 PR #2

`agent-tool-maker-v0.6.0.patch` 是从 PR #2 的精确提交开始的**累计补丁**，
包含 v0.5 的多端/Broker 和本版 v0.6。已有 v0.5 时不要重复应用这个累计补丁。

```sh
git fetch origin
git switch -c feat/extensible-tools-v0.6.0 b20775c9daf9285645d53254e4ccb27007c5076f
git apply --check /path/to/agent-tool-maker-v0.6.0.patch
git apply --index /path/to/agent-tool-maker-v0.6.0.patch
# 安装开发依赖与必要程序，审查修改并运行完整测试后：
git diff --cached --stat
git commit -m "feat: extensible credentials, API/CLI factory and browser recipes (v0.6.0)"
git push -u origin feat/extensible-tools-v0.6.0
gh pr create --base feat/local-console-v0.4.0 --head feat/extensible-tools-v0.6.0
```

上述 base 与当前未合并 PR #2 对齐。若上游已经合并/变化，以最新分支结构重新审阅，
不要盲目改 main。

## 测试门槛

普通测试在 `tests/`；浏览器源生导航另在
`acceptance/test_recipe_native_v06.py`、`acceptance/test_console_navigation.py`。
它们必须在允许相应测试浏览器导航的环境验证。不得改变受管浏览器策略来获得通过。
原生导航验收不能替代真实供应商网站/授权；本版未调用真实模型或供应商账号。

安装包、增量与累计补丁均附 SHA-256。补丁应用验证结果和最终源码树见
`RELEASE_ACCEPTANCE.md` 与交付的 `reports/v06/provenance.json`。

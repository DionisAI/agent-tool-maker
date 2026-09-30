# 将 v0.5.0 应用到 GitHub

本轮 GitHub 连接只有读接口，**没有推送 v0.5，也没有创建新的 PR**。
交付补丁以 PR #2 的精确提交 `b20775c9daf9285645d53254e4ccb27007c5076f` 为基线。
PR #2 仍叠加于 PR #1；不要把新版本直接强推 main 或把旧 CI 绿灯当作新版通过。

在已登录 GitHub 的本机 clone 中执行。先保存工作区修改，并把下面补丁路径替换为实际下载位置：

```bash
git status --short
git fetch origin
gh pr checkout 2
git rev-parse HEAD
# 此时应为 b20775c9daf9285645d53254e4ccb27007c5076f；不同则先审查上游变化。
git switch -c feat/encrypted-sync-v0.5.0

git apply --check /absolute/path/agent-tool-maker-v0.5.0.patch
git apply --index /absolute/path/agent-tool-maker-v0.5.0.patch
git diff --cached --stat
# 按 TEST_REPORT_V05.md 在本机/CI 验证，不添加你的运行态与凭证。
git commit -m "feat: recipient-encrypted sync and scoped broker sessions (v0.5.0)"
git push -u origin HEAD

gh pr create --base feat/local-console-v0.4.0 \
  --title "ATM v0.5.0: encrypted multi-device sync and scoped sessions" \
  --body "Stacked on PR #2. Adds selective encrypted credential replication, explicit conflict resolution and bounded local Broker sessions. Local evidence is in docs/TEST_REPORT_V05.md; read this commit's actual CI before merging."
```

若 PR #2 已合并或其 head 已改变，不要强行应用或覆盖。让本机 Agent 检查新基线、重做差异，并运行回归。
补丁提供完整变更；发布 ZIP 可以独立安装，但无需覆盖 Git clone，也无需复制 vault 数据库。

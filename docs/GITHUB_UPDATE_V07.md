# 提交 v0.7 补丁（本轮未代为推送）

两份补丁选一份；**不要重复应用**。

| 本地基线 | 文件 |
|---|---|
| 精确 v0.6源码树 `4d0d096bf87062653cf43ebb341750c7f897a656` | `agent-tool-maker-v0.7.0-from-v0.6.patch` |
| GitHub PR #2 的提交 `b20775c9daf9285645d53254e4ccb27007c5076f` / 树 `047eddb287628dee045131414bf1e3c0b061b9e6` | `agent-tool-maker-v0.7.0.patch`，已包含v0.5、v0.6及v0.7 |

先检查 `git status --short`。有未提交工作就先保留，不 reset / force checkout。
本轮读取的PR #2仍未合并且是v0.4；主分支不是本累计补丁基线。使用已登录的GitHub CLI或本机Git流程。

基于PR #2的示例：

```sh
git fetch origin
# 查看后确认这一分支仍指向上面写明的基线；变化则停止，重新对照，不强制覆盖。
git rev-parse origin/feat/local-console-v0.4.0
git switch -c feat/secrets-first-v0.7.0 origin/feat/local-console-v0.4.0

git apply --check /absolute/path/agent-tool-maker-v0.7.0.patch
git apply --index /absolute/path/agent-tool-maker-v0.7.0.patch
git diff --cached --stat

# 在隔离开发环境完成本地测试；不用生产Key
python -m pytest -q
python scripts/demo_secrets_first.py --out /tmp/atm-secrets-receipt.json

git commit -m "feat: credential-first session and scoped program injection (v0.7.0)"
git push -u origin feat/secrets-first-v0.7.0
gh pr create --base feat/local-console-v0.4.0 --head feat/secrets-first-v0.7.0 \
  --title "ATM v0.7.0: secrets first, scoped exec and unified 30-minute unlock" \
  --body-file docs/PR_V07.md
```

不要把生成的owner/profile、真实Key、`.env`、SQLite、Cookie、socket或同步包加入提交。
这只创建待审PR，不自动合并前序PR或main，不改变私有可见性。
如果前序PR已合并/重写，先核对完整diff与目标分支，再选择rebase/cherry-pick，不盲套上述命令。

交付的补丁已在精确基线中实际执行 apply检查，结果树与交付源码相同。最终树在 `RELEASE_ACCEPTANCE.md`；不把“补丁可应用”说成“远端CI已通过”。

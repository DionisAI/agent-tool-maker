# ATM v0.8 — 一张本地窗口的验收

基线为已合并的 v0.7 main `0465b0c4548eb4d2863c9732b8462b312a833def`，
树 `cd0ca050360bd80d22387618bcddbaf2c5317d2a`；包含 PR #3 的批准快照安全修复。

## 本轮本地证据

- 新增 `tests/test_quickstart_v08.py` 的30项测试通过。实际HTTP、加密库、Unix socket、
  自动启动的有限期服务、两个独立CLI、编辑后的普通脚本、范围拒绝和锁定均实际执行。
- 分组完整回归：681项契约测试通过 + 29项浏览器组件/本地工具测试通过，合计710项。
  两组互斥并覆盖本地 tests/ 集合，无失败、跳过或预期失败。
- 回归后对默认安装提示作了文案修正：不再把人导向手工 vault init/connect。
  相关安装/新窗口/旧Skill回归另重跑68项通过；最终提交的全套CI须另行核对。
- 初轮完整契约检查曾有1项失败：新版Skill遗漏 make validate/make install 和
  submission_unknown 的恢复规则。补回说明，没有删除测试断言，复跑通过。

## 安全检查

真实新进程只有显式选择的环境变量，不获得库主密码；返回值/任务记录不含测试Key原文，
不创建项目.env。旧严格permit测试继续通过。跨项目/额外Key、未批准、错误口令、
过期/冲突、撤销、旧grant在下一次解锁复活、Host/Origin/bearer错误均被拒绝。
只安装atm；旧环境变量回退不生效；旧加密校验格式仍能解密。
详细代价与剩余边界见 QUICK_START_SECURITY.md。

## 必须分开的外部验收

本机受管理Chromium拒绝原生localhost导航（ERR_BLOCKED_BY_ADMINISTRATOR）。
保留该失败，不修改策略，不把HTTP或内存DOM测试称为原生窗口验收。
`acceptance/test_quickstart_native_v08.py` 已加入独立GitHub原生导航检查：
实际窗口、严格CSP、输入密码、两个新CLI、刷新和锁定，必须以本PR最终SHA结果为准。

未使用真实供应商、真实Claude/Codex模型或真实Key，消费为0。
未验证用户实际宿主加载、原生keyring、Windows、公网多机器或30分钟持续压力。
新的便捷模式信任本机同UID项目代码，不是沙箱；旧逐命令严格模式保留。

## 复现

```sh
python -m pytest -q -m 'not browser and not integration'
python -m pytest -q -m 'browser or integration'
python -m pytest -q acceptance/test_quickstart_native_v08.py
```

最后一项需要允许原生导航的浏览器环境。GitHub PR、精确提交的Actions状态与合并记录，
是发布状态的依据；本文件的本地通过数不替代远端CI。

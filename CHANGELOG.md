# 0.3.0 — persistent onboarding

- Add local preview/apply setup and user-level Codex/Claude Skill registration.
- Repeated setup/export/connect preserves existing credentials and identical files.
- Explicit replacement backs up Skills; changed CLI bindings never auto-rebind.
- Doctor checks binary hashes/permissions, vault availability and declared expiry;
  unlocking is opt-in and vendor authentication is not inferred.
- Add four fixed account GET probes with explicit network consent and historical
  credential-bound status. No generation, automatic retries or unknown-cost checks.
- Add optional expiry metadata; preserve legacy vaults. OAuth refresh remains planned.
- Add repository instructions, setup-once guide and fresh-process regressions.

# Changelog

## 0.2.0 · Agent Tool Maker · 2026-09-29

- ATR → ATM：Python 包/主命令/Skill/文档重命名，保留 `atr` CLI 别名与旧 vault metadata 读取。
- 157 个有限动作入口：120 native、14 MCP discovery/batch、23 外部交接；原 66 项调研全部对应状态与待办。
- 新增工具 Maker：声明式 API/CLI/交接与串行组合；规范化 SHA-256 显式批准安装；禁止静默覆盖内置动作。
- 有界 API/CLI adapter：输入 schema、路径限制、显式权限、credential reference、固定 argv、入口 hash、结果记录。
- MCP stdio 与 Streamable HTTP JSON/SSE 子集；真实工具发现、参数校验、白名单与同会话批次。
- 小红书、X、Reddit、Upwork 的有限 OpenCLI 读取；办公、后期、部署、项目、营销和反馈动作。
- 桌面/人工任务明确挂起，真实文件交回才完成文件级验收。
- 可搜索路线图 HTML/JSON/Markdown，明确 OAuth、长驻进程、桌面脚本、平台审核、供应商实测和钱包后续门槛。
- 回归中修复旧 Blender stub 测试；针对真实 Pandoc DOCX sandbox 默认模板冲突，明确改成需要 code 许可的固定转换动作，不宣称隔离。

所有供应商生产账户验收仍单独待做；不把合同测试等同生产兼容性。详细测试结果见 `docs/TEST_REPORT.md`。

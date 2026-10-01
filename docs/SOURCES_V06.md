# 本版实现依据（2026-09-30 核查）

以下是功能契约的官方来源，非“已经运行这些账户”的证明。

- Playwright Python authentication： https://playwright.dev/python/docs/auth
  storage_state可复用登录；含敏感状态，不能入公开或私有Git仓库。会话过期仍取决于站点。
- Playwright Python codegen： https://playwright.dev/python/docs/codegen
  已有操作录制生成代码能力；本版没有把codegen自动录制全部集成成无人值守探索器。
- Claude Code CLI： https://code.claude.com/docs/en/cli-reference
  print/JSON schema、tools限制、strict MCP配置、safe mode、无会话持久化。
- Codex non-interactive： https://developers.openai.com/codex/noninteractive
  exec、read-only、ignore-user-config、ephemeral、output-schema、output-last-message。
- Codex特性定义： https://github.com/openai/codex/blob/main/codex-rs/features/src/lib.rs
  shell_tool开关。关闭shell与search不等于对所有未来版本功能提供进程级沙箱保证。
- pipx CLI： https://pipx.pypa.io/stable/reference/cli.html
  inject --include-apps可暴露被注入依赖的应用入口。

新OpenAPI/API/网页示例使用保留的example域名，故意不是生产供应商的已验证说明。

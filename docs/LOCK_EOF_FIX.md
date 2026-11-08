# 锁定瞬间的 broker EOF 修复

## 范围与根因

修复分支：`fix/lock-eof-status-20261001`。基线提交：
`449e07bd43468960fa5ed613725149c43e027c38`。本次为本地修复，不表示发布或合并。

`atm lock` 关闭本地会话时，另一个连接可能已连接成功，却在收到响应前遇到 EOF。
`broker.call` 原先将空字节交给同步 JSON 解析器，误报 `invalid_sync`。
因 `quickstart.ready` 未将这个同步错误视为连接关闭，锁定后的立即检查输出异常。

改动仅在 broker 传输边界识别空响应：

- EOF 返回 `broker_unavailable`，沿用现有上层的锁定/待解锁处理。
- `run` / `exec` 的丢失响应保持 `outcome_uncertain=true`；没有自动重试，继续使用原请求标识核对任务。
- 非空错误 JSON、重复字段、远端授权错误继续按原协议拒绝，不一概当作已锁定。
- 没有改变授权、期限、凭证加密格式、环境变量限制或浏览器政策。

## 回归与验证边界

- 新增真实 Unix socket 传输测试：修复前四种操作均失败为 `invalid_sync`；最小修复后四项通过。
- 扩展测试覆盖非空错误 JSON、重复字段、结构化远端错误和正常响应。
- 即时锁定回归不加 sleep/join：检查 `needs_unlock`、新 CLI 的退出码 3、未执行程序、未读取凭证，以及直接执行调用被拒绝。
- macOS 既有测试使用了不存在的 `/bin/false`。原版也复现失败；夹具改为查找实际 echo/false，保留 `grant_stale` 断言。
- 本地回归使用规范化的 `/private/tmp` 目录、隔离状态和假凭证。可选 Playwright Python 依赖用于既有健康状态测试；没有安装浏览器二进制。

最终回归和用户安装回读结果见下方验收记录；真实供应商、原生 keyring 和原生浏览器不属于此次传输修复的验收。

## 本地复现

```sh
TMPDIR=/private/tmp PYTHONPATH="$PWD/src" python -m pytest -q \
  tests/test_broker_transport.py tests/test_quickstart_v08.py \
  tests/test_broker_v05.py tests/test_secrets_v07.py
TMPDIR=/private/tmp PYTHONPATH="$PWD/src" python -m pytest -q -m 'not browser'
```

## 验收记录

- 最终源码的全部非浏览器测试：712 通过、2 跳过、11 未选择，耗时 173.34 秒。两项跳过原因为本机未安装 pandoc；11 项浏览器测试未运行，分别记录。
- 首轮扩展回归保留了两个既有失败：macOS `/bin/false` 路径夹具和未安装可选 Playwright Python 依赖。已用未修复原版分别复现，校正测试环境后重跑，没有放宽断言。
- wheel 内 broker 与已测试源码逐字节一致；仅有 `atm` console entry point。
- broker SHA-256：`9390c0510f5d280934eec9d7306afb2090012dc1e0d71f88d6c7fa448af72398`。
- 已安装运行时验收：19 通过，耗时 5.31 秒。包含 11 项传输测试、4 项立即锁定新 CLI 测试，以及安装测试期间原先四次失败的复现脚本。运行时未加载源码目录。
- 已安装 broker 与测试源码逐字节一致；`pip check` 通过。用户命令仍为 `atm`，版本保持 0.8.0 的本地修正版，两份 Skill 的内容与前缀均 unchanged。
- 在线重装在本机代理连接上持续等待，因此停止了该次安装；将未完成目录移入 Trash，复用完整备份中的已验证依赖，从上述 wheel 离线完成更新。旧应用及替换文件均保留在 Trash，另有完整临时恢复副本。
- 默认凭证库回读仍为 backend null、凭证名列表空、会话 locked；没有初始化、移动或重置该库，没有真实供应商调用。

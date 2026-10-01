# ATM v0.6.0 — 测试与交付边界

日期：2026-09-30。扩展机制迭代，基于 v0.5 source tree `d38944f8d8ba71bdfae225619839f347dea1046e`。
本轮确认远端 PR #2 仍开放于 `b20775c9`，v0.5 尚未推送；本版也没有上传/运行新 GitHub CI。

## 最终完整复跑

**588 passed，0 failed，0 skipped，0 xfail，0 deselected。**
计时 404.63 秒，行覆盖率 **87.01%**（3672/4220）。
Linux / Python 3.13.5。包含原484项以及新增0项。
测试开始前记录的全部运行时/测试文件哈希，在结束后保持一致；不是一边修改核心代码一边引用旧结果。

| 新增测试文件 | 数量 | 重点 |
|---|---:|---|
| `test_extensions_v06.py` | 0 | 未知Key、跨进程/跨设备、OpenAPI、CLI打包和CAS更新 |
| `test_web_recipe_v06.py` | 0 | 加密网页会话、scope、DOM/下载、登录/失败状态、无自动重试 |
| `test_factory_v06.py` | 0 | Claude/Codex真实测试子进程、受限参数、输出校验、超时无降级 |
| `test_extensions_web_v06.py` | 0 | 真实本机HTTP工坊、鉴权、独立凭证槽、批准摘要 |
| `test_extensions_broker_v06.py` | 0 | 新类型Broker授权、定义变化失效、固定摘要 |
| `test_extension_ui_v06.py` | 0 | 实际Chromium工坊DOM + HTTP组件桥接 |

## 真实与模拟分开

真实运行：FFmpeg/FFprobe、ImageMagick、Pandoc、本机HTTP/Broker和Chromium DOM及下载。
供应商HTTP大多用MockTransport；新API测试独立检查请求方法、URL、认证和参数，
不是只拿生产编译器输出和它自己做比较。Claude/Codex通过协议替身测试子进程，**未调用真实模型**。

当前受管Chromium禁止原生URL导航，本轮不改变管理策略、不放宽CSP。
网页配方组件测试明确使用内存DOM适配器，console明确使用Python本机HTTP测试桥。
这些检查不证明真实网站的登录、按钮、网站改版兼容性或网络策略已经通过。
新增 `acceptance/test_recipe_native_v06.py` 在允许原生浏览器导航的环境验收，已接入CI定义但**尚未远端执行**。
不能沿用v0.4 CI绿灯。

## 安装包与独立程序

在源码目录之外的独立环境安装wheel，**13项检查通过**：未知Key保存后新进程不重问、
OpenAPI导入、资源读取、CLI打包、Python `-I`运行生成的CLI、真实FFprobe、重复请求、
Web资产、鉴权和Web/CLI共享状态。wheel中 **43 个运行时文件/资源与测试源码逐字节一致**。
依赖显式复用宿主已安装包；不是空白机器从PyPI重新解析安装的验收。

额外 `acceptance/test_broker_uid.py` **1项通过**，复验Linux跨系统用户拒绝与允许。
演示 `scripts/demo_extensions.py`：6项检查通过，三个实际CLI包产出，
FFprobe真实执行、同请求复用；API和网页只dry-run。假Key和临时库结束后删除。

## 发现并修复的问题

生成的首版CLI依赖同一Python环境，现改为标准库脚本调用明确安装的ATM命令，
并用Python `-I` + 源码外wheel测试。API参数引用和可选query/boolean编码已独立验收；
畸形模型JSON和OpenAPI返回安全错误，不被误认成成功；网页会话expiry类型经规范化后
作为AES-GCM附加认证数据；导航被管理策略拒绝时直接报告，无绕过路径。
UI新增导航的装饰字符影响精确可访问名称，已标记aria-hidden并保留原行为断言。
最初尚未冻结资源的探索性完整运行出现过旧UI测试超时，稳定后独立及最终全套通过，
没有通过删除断言或宽松跳过来掩盖失败。

## 不宣称完成

真实供应商调用0，真实Claude/Codex模型调用0，消费0。真实宿主Skill加载、原生系统keyring、
Windows、真实网站、多端公网同步、OAuth刷新、任意网站探索循环、代码沙箱和独立安全审计没有验证/实现。
浏览器脚本可被封装，但不是官方API。结构校验/哈希一致≠业务验收；未知价格不是0。

浏览器会话只留本机；下载64MiB在交付前检查，不是磁盘硬配额。
已有157个内置动作保持不变；扩展不意味着所有上游API/CLI版本都兼容。

## 复现

```sh
python -m pip install -e '.[secure,test,web]'
python -m playwright install chromium
# 真实本地套件需要FFmpeg/FFprobe、ImageMagick magick、Pandoc
python -m pytest -q --cov=agent_tool_maker --cov-report=json:reports/v06/coverage.json --junitxml=reports/v06/junit.xml
python scripts/demo_extensions.py --out ./extension-demo
# 仅在允许浏览器相应导航的环境：
python -m pytest -q acceptance/test_recipe_native_v06.py
```

原始证据位于下载包 `reports/v06/`；仓库保留summary和测试源码。

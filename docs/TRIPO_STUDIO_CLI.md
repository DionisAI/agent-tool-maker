# Tripo Studio 网页 CLI

## 范围与执行方式

这是网页 DOM 适配器，不是开发者 API。Studio 与 API 的积分独立：
[Tripo 官方说明](https://www.tripo3d.ai/help/api-plugins/tripo-studiotripo-api)。
不修改现有 `tripo.generate`，也不导出 Cookie、Token、Chrome profile 或读取认证文件。
浏览器自己维护登录；失效后由人完成官方登录，不承诺通用自动续期。

路线：主 Agent 观察真实 DOM → `examples/opencli/tripo-studio/` 专用适配器 →
`scripts/build_tripo_studio.py` → 固定 manifest / Python CLI / 哈希锁 → ATM →
已安装的 OpenCLIApp 1.8.6 + Chrome 扩展 1.0.24 → Studio 页面。

选择 `UI_SELECTOR` / visible-ui 契约。无内部端点、请求签名重放、网络抓取或
PAGE_FETCH。标题、积分和卡片来自实际观察的 DOM。CSS 与英文界面有漂移风险，
页面错误、缺登录、未加载和契约变化分别失败；未观察到的空列表不伪造成功。

## 已提供工具

| ATM 工具 | 权限 | 实际行为 |
|---|---|---|
| `tripo.studio.account` | code | 登录状态、页头积分；无身份信息 |
| `tripo.studio.assets` | code | 已加载模型卡片，limit 1–100；不自动翻页 |
| `tripo.studio.quote` | code + write | 必要时切文字模式，读取当前报价和设置；不填词、不提交 |
| `tripo.studio.generate` | code + write + paid | 明确确认后，一次私密文字生成；返回新资产页 ID |

只读资产输出 `coverage=currently_loaded_cards`、`all_assets=false`。
`preview_task_id` 从可见缩略图路径取得，与资产详情 ID 不同；`task_status=null`。
不返回图片签名 URL、邮箱、Cookie 或 Token。非英文/其他缩略图布局需要重新观察。

生成包位于 `generated/tripo-studio/{account,assets,quote,generate}/`，每包含
`tool.py`、manifest、输入示例、README 与 bundle-lock。只需要 Python 标准库和
已安装 ATM；浏览器依赖不内嵌。唯一由本项目安装的命令仍是 `atm`。

## 人的体验

Agent 检查 bridge doctor、已注册定义、源文件摘要和真实可执行文件绑定，
直接调用已安装工具。需要登录时仅打开本地官网交给人；不把安装/授权命令清单
交给人，不读取 profile/token 文件，不改浏览器策略。

付费前向人展示实际提示词、模型、Private、报价和积分上限。
获得本次确认后才设置 `human_confirmed=true` 并给 ATM paid/write/code 权限。
代码里有预算字段不代表人的付款确认；`--confirm` 也不是隔离机制。

生成输入：prompt（1–1000 字符）、max_credits（1–10000 整数）、quote_sha256、
request_key、human_confirmed（必须 true）。输入里的 request_key 与 ATM 调用
使用同一个稳定值。未完成输入的 `{}` 示例不会产生收费调用。

## 付费状态与证据边界

- 先读取报价、保留已有草稿，核对 Private/模型/parts/8K；填入明确批准的文字后
  再检查提示词、按钮、报价指纹和积分上限。
- 不重载已打开表单；从站点的可见 Workspace 链接正常导航。曾观察到冷打开路由
  呈现临时错误页；错误不算报价成功，也不隐式重发 Generate。
- `.atm/tripo-studio-paid/` 只存非秘密本地回执。在唯一收费点击前排他创建并
  fsync `dispatch_claimed` 回执；同项目 active.lock 阻止并发。完成锁用 rename
  留档，不永久删除。进程崩溃/未知结果保留回执与 active.lock，人工对账后处理。
- 同 request_key / 相同输入复用既有 submitted 回执，不进行导航、填词或点击；
  输入不同报冲突。结果未知时新 key 也被 active.lock 拦住，不自作重试。
- `submitted` 仅表示观察到新资产路由。ATM 外层 `completed` 是 CLI/JSON 完成，
  **不是生成模型完成**，也没有自动导出。
- 上限是当前可见报价的客户端检查，不是供应商服务端计费承诺；跨项目/用户
  手动同时操作不由本项目 lock 隔离。信任同系统用户的代码，不声称恶意代码隔离。

## 重新生成（Agent/开发者）

```sh
PYTHONPATH=src python scripts/build_tripo_studio.py --stage all --out NEW_DIRECTORY
node --test tests/tripo_studio_core.test.mjs tests/tripo_studio_paid.test.mjs
PYTHONPATH=src python -m pytest tests/test_tripo_studio_cli.py -q
```

先审阅源文件再安装适配器，校验 normalized manifest SHA，再安装/更新 ATM
定义。绑定的是 OpenCLIApp 的实际可执行文件（不是只校验 shell shim），
manifest 额外固定适配器文件摘要。升级需要重新审阅。哈希是完整性检查，不是
作者签名；浏览器扩展与依赖仍属被信任程序。

编译器排他保留输出目录，逐文件原子写入，最后写完整性锁。失败目录保留供诊断，
缺锁的半成品包被 check-bundle 拦住；不调用永久删除清理。

## 本地验收 2026-10-02

- 只读真实 CLI → 已安装 ATM → Chrome：account 已登录、20,155 积分；assets
  返回 20 个当前已加载卡片。未读取 Key 或导出登录态。
- 真实报价：H3.1 – Best Quality、Private、parts=false、8K=false、40 积分。
- 人明确批准单个蓝色立方体，最多 40 积分一次；生成 CLI 实际提交成功，
  资产 ID `6e6198e0-0d74-4522-832f-46a5d49e1d3d`。
- 原生浏览器回读余额 20,115，差额 40；模型已在 3D 视图显示，Export 控件
  可用，Faces 11,550 / Vertices 6,701。已保存 `paid-result.png` 验收截图；未导出。
  这是本次人工界面验收，生成 CLI 本身仍只返回 submitted，不自动等待模型完成。
- 自动化：24 个 Node 合成测试、7 个 Python 合同/真实假子进程测试通过。
  工厂/HTTP/子进程回归 55 passed。完整非浏览器回归 776 passed、2 skipped
  （未安装 pandoc）、11 deselected；浏览器适配器另做上述真实 Chrome 路径验收。
- 四个生成包均通过完整性检查，已安装定义和适配器源码逐项一致；已有
  Claude/Codex 用户 Skill 已同步新工具说明，原运行时路径不变，旧版备份保留。
- 分支 `feat/tripo-studio-cli-20261002`，未提交/推送/发布；保留既有 OAuth/锁定修复。
